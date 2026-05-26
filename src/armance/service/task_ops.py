"""/task /report /judge /export /deliverable handlers — extracted from
service/handlers.py.

These five handlers are independent of the chat shells and the workflow
engine, so they move out cleanly. The chat router and the meta-agent
chat handlers (Armance/Malik/Kim) stay in handlers.py until the workflow
engine unification (P1.1) lands.
"""
from __future__ import annotations

import glob
import logging
from pathlib import Path

from armance.nls import t
from armance.service.agents.specialist_runner import run_specialist
from armance.service.export import export_all, export_target
from armance.service.loop_context import AgentStatus, LoopContext

logger = logging.getLogger(__name__)


def _set_status(ctx: LoopContext, name: str, state: str) -> None:
    for s in ctx.statuses:
        if s.name == name:
            s.state = state
            return
    ctx.statuses.append(AgentStatus(name=name, state=state))


# ---------------------------------------------------------------------------
# /task <domain> <prompt>
# ---------------------------------------------------------------------------


async def cmd_task(args: list[str], ctx: LoopContext) -> str:
    if len(args) < 2:
        return t("task.usage")
    domain = args[0]
    prompt = " ".join(args[1:])
    from armance.core.models.task import Task
    reports_root = ctx.armance_root / "reports"
    task = Task(prompt=prompt, domain=domain, mode="light")
    agent_name = ctx.state.current_agent or domain
    _set_status(ctx, agent_name, "working")
    try:
        agent_obj = next(
            (a for a in ctx.agents if a.domain == domain and a.name == agent_name),
            next((a for a in ctx.agents if a.domain == domain), None),
        )
        if agent_obj is None:
            _set_status(ctx, agent_name, "error")
            return t("task.no_agent_for_domain", domain=domain)
        user_text_lower = prompt.lower()
        if "caveman" in user_text_lower:
            if "full" in user_text_lower:
                task_caveman = "full"
            elif "ultra" in user_text_lower:
                task_caveman = "ultra"
            elif "none" in user_text_lower:
                task_caveman = "none"
            else:
                task_caveman = "ultra"
        else:
            task_caveman = "none"

        report = await run_specialist(
            agent_obj,
            task,
            ctx.armance_root,
            ctx.cfg,
            reports_root=reports_root,
            caveman_level=task_caveman,
            event_bus=ctx.event_bus,
        )
        _set_status(ctx, agent_name, "completed")
        ctx._last_output = report.content
        return report.content
    except Exception as exc:
        _set_status(ctx, agent_name, "error")
        logger.exception("task failed")
        return t("common.error", error=str(exc))


# ---------------------------------------------------------------------------
# /report
# ---------------------------------------------------------------------------


async def cmd_report(args: list[str], ctx: LoopContext) -> str:
    if not ctx._last_output:
        return t("report.no_output")
    from armance.service.report import Report, write_report
    agent_name = ctx.state.current_agent or "armance"
    agent_obj = next((a for a in ctx.agents if a.name == agent_name), None)
    domain = agent_obj.domain if agent_obj else agent_name.split("_")[0]
    reports_root = ctx.armance_root / "reports"
    report = Report(
        agent_name=agent_name,
        domain=domain,
        prompt_truncated="(manual report)",
        content=ctx._last_output,
    )
    path = write_report(report, reports_root)
    return t("report.saved", path=str(path))


# ---------------------------------------------------------------------------
# /judge @file ...
# ---------------------------------------------------------------------------


async def cmd_judge(args: list[str], ctx: LoopContext) -> str:
    if not args:
        return t("judge.usage")
    paths: list[Path] = []
    for token in args:
        if token.startswith("@"):
            pattern = str(ctx.armance_root / token[1:])
            matched = glob.glob(pattern, recursive=True)
            if not matched:
                return t("judge.no_files_matched", pattern=token[1:])
            paths.extend(Path(p) for p in matched)
        else:
            p = Path(token)
            if not p.is_absolute():
                p = ctx.armance_root / token
            paths.append(p)
    if not paths:
        return t("judge.no_paths")
    _set_status(ctx, "judge", "working")
    try:
        from armance.service.agents.judge_agent import JudgeAgent
        from armance.service.report import read_report
        deliverables = [read_report(p).content for p in paths]
        view = "judge:" + "-".join(p.stem for p in paths[:3])
        agent = JudgeAgent(ctx.armance_root, ctx.cfg)
        synthesis = await agent.synthesise(view, deliverables)
        _set_status(ctx, "judge", "completed")
        return synthesis.content
    except Exception as exc:
        _set_status(ctx, "judge", "error")
        logger.exception("judge failed")
        return t("common.error", error=str(exc))


# ---------------------------------------------------------------------------
# /export <target|all>
# ---------------------------------------------------------------------------


async def cmd_export(args: list[str], ctx: LoopContext) -> str:
    if not args:
        return t("export.usage")
    target = args[0]
    repo_root = ctx.armance_root.parent
    try:
        if target == "all":
            paths = export_all(repo_root, armance_root=ctx.armance_root)
            return t("export.exported_list", paths=", ".join(str(p) for p in paths))
        out = export_target(repo_root, target, armance_root=ctx.armance_root)
        return t("export.exported_one", path=str(out))
    except Exception as exc:
        logger.exception("export failed")
        return t("common.error", error=str(exc))


# ---------------------------------------------------------------------------
# /deliverable <fmt> [from=<src>] [<name>]
# ---------------------------------------------------------------------------


async def cmd_deliverable(args: list[str], ctx: LoopContext) -> str:
    """Generate a deliverable from the last output or a named report."""
    if not args:
        return t("deliverable.usage")

    fmt = args[0].lower()
    if fmt not in ("pptx", "docx", "pdf", "md"):
        return t("deliverable.unsupported_format", fmt=fmt)

    source_spec = "latest_output"
    output_name: str | None = None
    for arg in args[1:]:
        if arg.startswith("from="):
            source_spec = arg[5:].strip()
        elif not arg.startswith("-"):
            output_name = arg

    source_content = ""
    if source_spec == "latest_output":
        source_content = ctx._last_output
    elif source_spec == "latest_judge":
        judge_dir = ctx.armance_root / "judge"
        if judge_dir.exists():
            candidates = sorted(judge_dir.glob("judge_v*.md"), key=lambda p: p.stat().st_mtime)
            if candidates:
                source_content = candidates[-1].read_text(encoding="utf-8")
    else:
        candidate = ctx.armance_root / source_spec
        if candidate.exists():
            source_content = candidate.read_text(encoding="utf-8")

    if not source_content:
        return t("deliverable.no_content", source=source_spec)

    from armance.core.models.deliverables import DeliverableError, parse_report

    try:
        tree = parse_report(source_content)
    except Exception as exc:
        return t("deliverable.parse_error", error=str(exc))

    exports_dir = ctx.armance_root / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    stem = output_name or f"deliverable_{ctx.state.id}"
    output_path = exports_dir / f"{stem}.{fmt}"

    renderer_name: str | None = None
    if fmt == "pptx":
        renderer_name = "render_pptx"
    elif fmt == "docx":
        renderer_name = "render_docx"
    elif fmt == "pdf":
        renderer_name = "render_pdf"

    try:
        if fmt == "md":
            output_path.write_text(source_content, encoding="utf-8")
        else:
            if renderer_name is None:
                return t("deliverable.no_renderer", fmt=fmt)
            from armance.core.models import deliverables as _deliv
            getattr(_deliv, renderer_name)(tree, output_path)
    except DeliverableError as exc:
        return t("deliverable.error", error=str(exc))
    except Exception as exc:
        logger.exception("deliverable render failed")
        return t("common.error", error=str(exc))

    rel = output_path.relative_to(ctx.armance_root)
    return t("deliverable.created", path=str(rel))
