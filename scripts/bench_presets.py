"""Replayable preset benchmark — LIVE script (network required).

Replays each bench case of a preset through the REAL Armance system
(recruitment + workflow engine + Creuset), then has a blind cross-family
judge compare the Armance output against the versioned frontier
reference (`reference.md`). Produces `bench-report.md` with per-case
scores and a delta against the previous run (non-regression).

Usage:
    uv run python scripts/bench_presets.py <preset> [--smoke] [--case ID]...
        [--root DIR] [--judge-model <provider/model>]

- `--smoke`  : only cases flagged `smoke: true` (cheap, free models).
- `--root`   : project dir used as bench workspace
               (default: ./.bench/<preset> — reused across runs so the
               delta column means something).
- Requires `armance init` done globally (same precondition as qa_live).

Offline logic (loading, anonymisation, parsing, report) lives in
`armance.service.preset_bench` and is unit-tested; this driver only
wires the live calls.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from armance.config import ensure_armance_tree, load_config  # noqa: E402
from armance.core.models.workflow import load_workflow  # noqa: E402
from armance.service import preset_bench, preset_ops  # noqa: E402
from armance.service.checkpoint import CheckpointResponse  # noqa: E402
from armance.service.llm_service import (  # noqa: E402
    TokenLedger,
    call_with_ledger,
    get_client,
    set_ledger,
)
from armance.service.session import Session, start_or_resume  # noqa: E402
from armance.service.tui_bridge import (  # noqa: E402
    dispatch_input,
    load_user_agents,
    make_loop_context,
)


class AutoApprove:
    """Non-TTY checkpoint handler: approve everything (bench is unattended)."""

    async def prompt(self, checkpoint) -> CheckpointResponse:  # noqa: ANN001
        return CheckpointResponse(action="approve")


def _latest_run_output(armance_root: Path, workflow_name: str) -> str | None:
    """Final text of the most recent run: synthesis.md, else last step file."""
    wf_dir = armance_root / "exports" / workflow_name
    if not wf_dir.is_dir():
        return None
    runs = sorted(d for d in wf_dir.iterdir() if d.is_dir() and d.name.startswith("run-"))
    if not runs:
        return None
    run = runs[-1]
    synthesis = run / "synthesis.md"
    if synthesis.is_file():
        return synthesis.read_text(encoding="utf-8")
    steps = sorted(run.glob("step-*.md"), key=lambda p: p.stat().st_mtime)
    return steps[-1].read_text(encoding="utf-8") if steps else None


async def _ensure_team(ctx, preset) -> None:  # noqa: ANN001
    """Recruit via Malik (the real path) if no user agents exist yet."""
    if load_user_agents(ctx.armance_root):
        print("  team already recruited — reusing")
        return
    roles = ", ".join(p.stem for p in preset.role_files())
    ctx.state.current_agent = "system-hr"
    reply, _ = await dispatch_input(
        f"Recrute une équipe couvrant exactement ces rôles : {roles}. "
        "Les fiches de rôles sont dans la library du projet. Recrute "
        "directement, sans me redemander confirmation.",
        ctx,
    )
    print(f"  Malik: {reply[:160]}…")
    if not load_user_agents(ctx.armance_root):
        raise SystemExit("recruitment produced no agents — cannot bench")


async def _judge(ctx, cfg, case, pair, judge_model: str) -> preset_bench.CaseScore:  # noqa: ANN001
    provider, _, model = judge_model.partition("/")
    if not model:
        raise SystemExit(f"--judge-model must be <provider>/<model>: {judge_model}")
    client = get_client(provider, cfg)
    prompt = preset_bench.build_judge_prompt(
        case, pair, case.rubric_path.read_text(encoding="utf-8")
    )
    response = await call_with_ledger(
        client, "bench-judge", [{"role": "user", "content": prompt}],
        model, ledger=ctx.ledger, provider=provider,
    )
    return preset_bench.parse_judge_reply(case, pair, response.text)


async def run_bench(args: argparse.Namespace) -> int:
    preset = preset_ops.find_preset(args.preset)
    if preset is None:
        print(f"unknown preset: {args.preset}", file=sys.stderr)
        return 1
    cases = preset_bench.load_bench(preset)
    if args.smoke:
        cases = [c for c in cases if c.smoke]
    if args.case:
        cases = [c for c in cases if c.id in args.case]
    if not cases:
        print("no matching bench cases", file=sys.stderr)
        return 1
    problems = [p for c in cases for p in c.validate()]
    if problems:
        print("bench cases incomplete:\n  " + "\n  ".join(problems), file=sys.stderr)
        return 1

    root = args.root or Path.cwd() / ".bench" / preset.name
    root.mkdir(parents=True, exist_ok=True)
    cfg = load_config(root)
    ensure_armance_tree(root, cfg)
    armance_root = root / ".armance"
    preset_ops.apply_preset(preset, root)

    state = start_or_resume(armance_root, resume=False)
    session = Session(state, armance_root)
    ledger = TokenLedger()
    set_ledger(ledger)
    ctx = make_loop_context(
        armance_root, cfg, state, session, ledger, checkpoint_handler=AutoApprove()
    )
    await _ensure_team(ctx, preset)

    from armance.service.handlers import _cmd_workflow_run

    scores: list[preset_bench.CaseScore] = []
    for case in cases:
        print(f"\n=== case {case.id} (workflow {case.workflow}) ===")
        wf_path = armance_root / "workflows" / f"{case.workflow}.yaml"
        load_workflow(wf_path)  # fail fast on schema drift before spending tokens
        t0 = time.monotonic()
        reply = await _cmd_workflow_run(
            case.workflow, None, ctx,
            skip_preflight=True,
            user_prompt_override=case.input_path.read_text(encoding="utf-8"),
            seed_inputs=[str(p) for p in case.attachments()] or None,
        )
        print(f"  run done in {time.monotonic() - t0:.0f}s — {reply[:120]}…")
        output = _latest_run_output(armance_root, case.workflow)
        if not output:
            print(f"  no run output found — case {case.id} skipped", file=sys.stderr)
            continue
        pair = preset_bench.anonymise_pair(
            output, case.reference_path.read_text(encoding="utf-8")
        )
        score = await _judge(ctx, cfg, case, pair, args.judge_model)
        verdict = score.verdict or "n/a"
        print(
            f"  judge: armance {score.armance_mean:.1f}/10 vs "
            f"reference {score.reference_mean:.1f}/10 → {verdict}"
        )
        scores.append(score)

    if not scores:
        print("no case produced a score", file=sys.stderr)
        return 1

    report_dir = armance_root / "exports" / "bench" / preset.name
    previous = preset_bench.load_previous_means(report_dir)
    report = preset_bench.render_report(preset.name, args.judge_model, scores, previous)
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
    report_path = report_dir / f"bench-report-{stamp}.md"
    report_path.write_text(report, encoding="utf-8")
    preset_bench.save_latest_means(report_dir, scores)
    print(f"\n{report}\n\nreport → {report_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Replayable preset benchmark (live)")
    parser.add_argument("preset")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument(
        "--judge-model",
        default="openrouter/deepseek/deepseek-chat-v3-0324:free",
        help="<provider>/<model> — pick a DIFFERENT family than the agents",
    )
    return asyncio.run(run_bench(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
