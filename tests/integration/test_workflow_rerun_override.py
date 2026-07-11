"""Lot I — partial re-run with human output override.

Guards: the overridden upstream step is NOT re-executed (its specialist runner
is never called — asserted via a spy), a NEW run_id is minted, the parent run
is untouched on disk, the new manifest carries `derived_from` with the override
entry, and the downstream step receives the override text. The override file is
read SERVICE-side (the skill), core does no new I/O.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from armance.config import Config, ProviderConfig
from armance.core.models.agent import Agent
from armance.service.skills.rerun_with_override import (
    RerunWithOverrideSkill,
    parse_rerun_args,
)


@pytest.fixture
def cfg() -> Config:
    return Config(
        providers=[ProviderConfig(name="openrouter", api_key="t")],
        default_provider="openrouter",
        default_model="openai/gpt-4o-mini",
    )


@pytest.fixture
def armance_root(tmp_path: Path) -> Path:
    root = tmp_path
    (root / "agents").mkdir(parents=True)
    (root / ".armance" / "workflows").mkdir(parents=True)
    return root


def _write_workflow(root: Path) -> None:
    (root / ".armance" / "workflows" / "abc.yaml").write_text(
        "name: abc\n"
        "steps:\n"
        "  - id: step_a\n"
        "    kind: task\n"
        "    role: analyst\n"
        "    depends_on: []\n"
        "  - id: step_b\n"
        "    kind: task\n"
        "    role: analyst\n"
        "    depends_on: [step_a]\n"
        "    prompt_template: |\n"
        "      Refine: {{step_a.output}}\n"
        "  - id: step_c\n"
        "    kind: task\n"
        "    role: analyst\n"
        "    depends_on: [step_b]\n"
        "    prompt_template: |\n"
        "      Format this into slides: {{step_b.output}}\n"
    )


def _ctx(root: Path, cfg: Config):
    from armance.service.loop_context import LoopContext
    from armance.service.session import Session, SessionState
    from armance.service.llm_service import TokenLedger

    state = SessionState.new()
    session = Session(state, root)
    analyst = Agent(
        name="Ana", role="analyst", persona="p",
        provider="openrouter", model="openai/gpt-4o-mini", system_prompt="a",
    )
    return LoopContext(
        armance_root=root, cfg=cfg, state=state, session=session,
        ledger=TokenLedger(), statuses=[], agents=[analyst],
    )


def test_parse_rerun_args() -> None:
    plan = parse_rerun_args("abc run-parent --override-step step_b=edited.md --from-step step_c")
    assert plan["workflow"] == "abc"
    assert plan["parent_run_id"] == "run-parent"
    assert plan["overrides"] == {"step_b": "edited.md"}
    assert plan["from_step"] == "step_c"


def test_read_overrides_service_side(armance_root: Path) -> None:
    (armance_root / "edited.md").write_text("HUMAN EDITED B", encoding="utf-8")
    skill = RerunWithOverrideSkill(armance_root)
    got = skill.read_overrides({"step_b": "edited.md"})
    assert got == {"step_b": "HUMAN EDITED B"}


def test_build_plan_downstream_reruns(armance_root: Path) -> None:
    skill = RerunWithOverrideSkill(armance_root)
    deps = {"step_a": [], "step_b": ["step_a"], "step_c": ["step_b"]}
    parent = {"step_a": "A", "step_b": "B-orig", "step_c": "C-orig"}
    built = skill.build_plan(
        "run-parent", {"step_b": "B-EDIT"}, parent, from_step=None, deps=deps,
    )
    # step_a carried (upstream, unchanged); step_b provided from override;
    # step_c is downstream of the override → NOT provided → will re-run.
    assert built["provided"]["step_a"] == "A"
    assert built["provided"]["step_b"] == "B-EDIT"
    assert "step_c" not in built["provided"]
    assert built["derived_from"][0]["run_id"] == "run-parent"
    assert built["derived_from"][0]["overrides"] == [
        {"step": "step_b", "source": "override-file"}
    ]


@pytest.mark.asyncio
async def test_partial_rerun_end_to_end(armance_root: Path, cfg: Config) -> None:
    _write_workflow(armance_root)

    # ── Parent run: run the full workflow with a stub runner. ──────────────
    from armance.service.handlers import _cmd_workflow_run

    def _report(text: str):
        r = MagicMock()
        r.content = text
        r.tokens_in = None
        r.tokens_out = None
        r.cost_usd = None
        return r

    async def _parent_runner(agent, task, *a, **k):
        # Echo the prompt so downstream steps carry recognisable text.
        return _report(f"OUT[{task.prompt[:40]}]")

    with patch("armance.service.handlers.run_specialist", new=AsyncMock(side_effect=_parent_runner)):
        ctx = _ctx(armance_root, cfg)
        await _cmd_workflow_run(
            "abc", None, ctx, skip_preflight=True, user_prompt_override="do the thing",
        )

    exports = armance_root / "exports" / "abc"
    parent_run_id = sorted(p.name for p in exports.iterdir() if p.name.startswith("run-"))[0]
    parent_manifest_before = (exports / parent_run_id / "manifest.json").read_text()

    # ── Human edits step_b's output by hand. ───────────────────────────────
    (armance_root / "b_edited.md").write_text("HAND-EDITED B OUTPUT", encoding="utf-8")

    # ── Partial re-run: override step_b, re-run downstream (step_c). ────────
    spy = AsyncMock(side_effect=lambda agent, task, *a, **k: _report(f"OUT[{task.prompt[:60]}]"))
    with patch("armance.service.handlers.run_specialist", new=spy):
        from armance.service.handlers import _cmd_workflow
        ctx2 = _ctx(armance_root, cfg)
        await _cmd_workflow(
            ["rerun", "abc", parent_run_id, "--override-step", "step_b=b_edited.md"],
            ctx2,
        )

    # A NEW run was minted (parent untouched on disk).
    run_ids = sorted(p.name for p in exports.iterdir() if p.name.startswith("run-"))
    assert len(run_ids) == 2, run_ids
    new_run_id = [r for r in run_ids if r != parent_run_id][0]
    assert (exports / parent_run_id / "manifest.json").read_text() == parent_manifest_before

    # The overridden step_b was NEVER handed to the specialist runner: every
    # spy call prompt must be a downstream (step_c) prompt, never step_b's.
    prompts = [call.args[1].prompt for call in spy.call_args_list]
    assert prompts, "downstream step_c must have re-run"
    assert all("Refine:" not in p for p in prompts), "step_b (Refine:) must NOT re-run"
    # step_c re-ran with the HUMAN-EDITED step_b output injected.
    assert any("HAND-EDITED B OUTPUT" in p for p in prompts)

    # New manifest carries derived_from + the overridden step marked `provided`.
    new_manifest = json.loads((exports / new_run_id / "manifest.json").read_text())
    assert new_manifest["derived_from"][0]["run_id"] == parent_run_id
    assert new_manifest["derived_from"][0]["overrides"] == [
        {"step": "step_b", "source": "override-file"}
    ]
    by_id = {s["id"]: s for s in new_manifest["steps"]}
    assert by_id["step_b"]["status"] == "provided"
    # step_b's persisted output is exactly the human text.
    b_out = (exports / new_run_id / "step-step_b.md").read_text()
    assert b_out == "HAND-EDITED B OUTPUT"
