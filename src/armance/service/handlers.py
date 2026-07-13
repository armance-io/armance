"""Slash-command handlers for the Armance TUI loop.

Each handler is ``async def _cmd_<name>(args, ctx) -> str``. The HANDLERS
dispatcher at the bottom of the file maps slash commands to handlers.

This module hosts the small slash handlers (/help /quit /switch /model
/effort) and the workflow sub-dispatcher (/workflow run|design|list|compare).

Per-meta-agent chat shells live in `armance.service.chat_handlers.*`.
Domain handlers live in dedicated *_ops.py modules: library_ops,
save_ops, role_ops, task_ops, mona_ops.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from armance.nls import t
from armance.service.agents.specialist_runner import run_specialist
from armance.service.chat_handlers.armance import cmd_context_chat as _cmd_context_chat  # noqa: F401  re-export
from armance.service.chat_handlers.common import set_status as _set_status
from armance.service.chat_handlers.malik import cmd_hr_chat as _cmd_hr_chat  # noqa: F401  re-export
from armance.service.chat_handlers.kim import (  # noqa: F401  re-export
    cmd_orchestrator_chat as _cmd_orchestrator_chat,
)
from armance.service.chat_handlers.specialist import cmd_chat as _cmd_chat  # noqa: F401  re-export
from armance.service.library_ops import (
    cmd_library as _cmd_library,
    dispatch as _library_dispatch,
    intercept_library_status as _intercept_rag_status,  # noqa: F401  re-export
)
from armance.service.loop_context import LoopContext
from armance.service.role_ops import (
    cmd_agent as _cmd_agent,
    cmd_agents as _cmd_agents,
    cmd_feedback_loop as _cmd_feedback_loop,
    cmd_iterate_from as _cmd_iterate_from,
    cmd_role as _cmd_role,
)
from armance.service.save_ops import cmd_save as _cmd_save
from armance.service.task_ops import (
    cmd_deliverable as _cmd_deliverable,
    cmd_export as _cmd_export,
    cmd_judge as _cmd_judge,
    cmd_report as _cmd_report,
    cmd_task as _cmd_task,
)
from armance.service.footprint_ops import cmd_footprint as _cmd_footprint

logger = logging.getLogger(__name__)




# ---------------------------------------------------------------------------
# /help
# ---------------------------------------------------------------------------

async def _cmd_help(args: list[str], ctx: LoopContext) -> str:
    from armance.service.help_text import build_help_text
    return build_help_text()


# ---------------------------------------------------------------------------
# /quit
# ---------------------------------------------------------------------------

async def _cmd_quit(args: list[str], ctx: LoopContext) -> str:
    # signal handled by run_tui
    return "[quit]"


# ---------------------------------------------------------------------------
# /switch <agent>
# ---------------------------------------------------------------------------

async def _cmd_switch(args: list[str], ctx: LoopContext) -> str:
    """Switch to an agent by name (case-insensitive, prefix-friendly).

    Resolution order:
      1. Exact filename match  (agents/<arg>.md)
      2. First-name match in already-loaded ctx.agents (a.name lower == arg lower)
      3. First-name prefix match  (a.name lower startswith arg lower)
      4. Any .md filename whose stem starts with arg (case-insensitive)

    Disambiguates by listing candidates if multiple matches.
    """
    if not args:
        return t("switch.usage")
    raw = args[0]
    name_lc = raw.lower()
    agents_dir = ctx.armance_root / "agents"

    from armance.core.models.agent import Agent
    from armance.service.tui_bridge import resolve_meta_agent

    meta = resolve_meta_agent(raw)
    if meta is not None:
        ctx.state.current_agent = meta
        ctx.session.save()
        return t("switch.switched_meta", name=raw.capitalize())

    path = agents_dir / f"{raw}.md"
    if path.exists():
        try:
            agent = Agent.load(path)
        except Exception as exc:
            return t("switch.load_error", name=raw, error=str(exc))
        ctx.state.current_agent = agent.name
        if not any(a.name == agent.name for a in ctx.agents):
            ctx.agents.append(agent)
        ctx.session.save()
        return t("switch.switched_agent", name=agent.name)

    exact = [a for a in ctx.agents if a.name.lower() == name_lc]
    if exact:
        chosen = exact[0]
    else:
        prefix = [a for a in ctx.agents if a.name.lower().startswith(name_lc)]
        if len(prefix) == 1:
            chosen = prefix[0]
        elif len(prefix) > 1:
            options = ", ".join(a.name for a in prefix)
            return t("switch.multiple_matches", name=raw, options=options)
        else:
            chosen = None

    if chosen is None and agents_dir.exists():
        candidates = [
            p for p in agents_dir.glob("*.md")
            if p.stem.lower().startswith(name_lc) and not p.stem.startswith("system-")
        ]
        if len(candidates) == 1:
            try:
                chosen = Agent.load(candidates[0])
            except Exception as exc:
                return t("switch.load_error", name=candidates[0].stem, error=str(exc))
        elif len(candidates) > 1:
            options = ", ".join(p.stem for p in candidates)
            return t("switch.multiple_matches", name=raw, options=options)

    if chosen is None:
        return t("switch.not_found", name=raw)

    ctx.state.current_agent = chosen.name
    if not any(a.name == chosen.name for a in ctx.agents):
        ctx.agents.append(chosen)
    ctx.session.save()
    return t("switch.switched_agent", name=chosen.name)


# ---------------------------------------------------------------------------
# /model
# ---------------------------------------------------------------------------

async def _cmd_model(args: list[str], ctx: LoopContext) -> str:
    from armance.service.checkpoint import Checkpoint
    if ctx.checkpoint_handler is None:
        return t("common.error", error="no checkpoint handler")
    provider_names = [p.name for p in ctx.cfg.providers] or ["openrouter"]
    p_resp = await ctx.checkpoint_handler.prompt(
        Checkpoint(id="model.provider", prompt=t("prompts.provider"),
                   kind="select", options={"choices": provider_names})
    )
    if p_resp.is_abort or not p_resp.content:
        return t("common.cancelled")
    m_resp = await ctx.checkpoint_handler.prompt(
        Checkpoint(id="model.model", prompt=t("prompts.model"), kind="text")
    )
    if m_resp.is_abort or not m_resp.content:
        return t("common.cancelled")
    ctx.state.current_provider = p_resp.content
    ctx.state.current_model = m_resp.content
    ctx.session.save()
    return t("model.set", provider=p_resp.content, model=m_resp.content)


# ---------------------------------------------------------------------------
# /effort
# ---------------------------------------------------------------------------

async def _cmd_effort(args: list[str], ctx: LoopContext) -> str:
    from armance.service.checkpoint import Checkpoint
    if ctx.checkpoint_handler is None:
        return t("common.error", error="no checkpoint handler")
    resp = await ctx.checkpoint_handler.prompt(
        Checkpoint(id="effort", prompt=t("prompts.reasoning_effort"),
                   kind="select", options={"choices": ["low", "medium", "high", "none"]})
    )
    if resp.is_abort or not resp.content:
        return t("common.cancelled")
    ctx.effort = resp.content
    return t("effort.set", choice=resp.content)


# /task /report /judge /export /deliverable live in armance.service.task_ops.


# ---------------------------------------------------------------------------
# /workflow run <name> [--enrich <session_id>]
# ---------------------------------------------------------------------------

_STAFF_AGENT_MAP = {
    "mona": "system-judge",
    "serge": "system-challenger",
    "criticalist": "system-challenger",
}

_STAFF_CANONICAL_NAME = {
    "mona": "Mona",
    "serge": "Serge",
    "criticalist": "Serge",
}


def _agent_is_healthy(agent: Any) -> bool:
    """Healthy = last probe didn't record an error. Never-probed agents
    count as healthy (innocent until proven bad)."""
    last_health = getattr(agent, "last_health", None) or ""
    return not last_health.startswith("error")


def _step_agent_candidates(role: str, ctx: "LoopContext") -> list[Any]:
    """Agents eligible to take a step of `role`, healthy first.

    - `mona` / `serge` / `criticalist` → the single staff agent (prefer the
      user-recruited Mona.md / Serge.md; fall back to the builtin template).
    - Anything else → roster agents of that role whose `last_health` is not
      an error. When none is healthy, fall back to the sick ones: the probe
      may be stale, and a real failure lands on the absence path anyway.
    """
    from armance.core.models.agent import Agent
    role = (role or "").lower().strip()
    if role in _STAFF_AGENT_MAP:
        # Prefer user-recruited version (carries user-chosen model + persona).
        canonical_name = _STAFF_CANONICAL_NAME[role]
        user_path = ctx.armance_root / "agents" / f"{canonical_name}.md"
        if user_path.exists():
            try:
                return [Agent.load(user_path)]
            except Exception:
                logger.warning("failed to load user %s agent", canonical_name)
        from armance import paths
        path = paths.global_agents_dir() / f"{_STAFF_AGENT_MAP[role]}.md"
        if path.exists():
            try:
                return [Agent.load(path)]
            except Exception:
                logger.exception("failed to load staff agent for role %s", role)
                return []
        return []
    matches = [a for a in ctx.agents if (a.role or "").lower() == role]
    healthy = [a for a in matches if _agent_is_healthy(a)]
    return healthy or matches


async def _mona_proxy_checkpoint(
    step: Any, prior_outputs: dict[str, str], ctx: "LoopContext",
    question: str | None = None,
) -> str:
    """In autonomous mode, Mona (VP) answers checkpoint questions on behalf
    of the CEO (user). The user isn't there to respond; Mona decides based
    on the project brief + workflow scope + upstream outputs."""
    from armance.core.models.agent import Agent
    from armance.core.models.task import Task

    from armance.service.chat_handlers.common import resolve_agent_path
    mona_path = resolve_agent_path(ctx.armance_root, "system-judge")
    if mona_path is None:
        return "[autonomous: mona unavailable, defaulting to 'proceed']"
    try:
        mona = Agent.load(mona_path)
    except Exception:
        return "[autonomous: mona load failed, defaulting to 'proceed']"

    upstream = "\n\n".join(
        f"### {sid}\n{out}" for sid, out in (prior_outputs or {}).items()
    )
    prompt = (
        f"You are Mona answering a human-checkpoint question as the VP, "
        f"on behalf of the absent CEO. Decide pragmatically.\n\n"
        f"CRITICAL: If the decision/question concerns an extremely important, critical, or high-risk element that you do not know or cannot decide without guessing/inventing, do NOT attempt to guess. Instead, you MUST delegate it to the user by starting your response exactly with `[ASK_USER] <Reason why you cannot decide and the question for the user>`.\n\n"
        f"## Project brief\n{ctx.state.project_brief or '(none)'}\n\n"
        f"## Checkpoint question (step id: {getattr(step, 'id', '?')})\n"
        f"{question or getattr(step, 'prompt', '') or '(none)'}\n\n"
        f"## Upstream outputs so far\n{upstream or '(none)'}\n\n"
        f"You are deciding WITHOUT the CEO present, so this decision is a "
        f"working hypothesis they must be able to review and contest. Unless "
        f"you delegate with `[ASK_USER]`, you MUST open your reply with the "
        f"exact marker `**Hypothèse (Mona) :**` (or `**Hypothesis (Mona):**` "
        f"if the configured language is English), state the decision in one "
        f"sentence, then give the reason and what would invalidate it. Keep it "
        f"to 1-3 sentences so the workflow can proceed."
    )
    task = Task(prompt=prompt, role="meta", mode="light")
    try:
        report = await run_specialist(
            mona, task, ctx.armance_root, ctx.cfg,
            reports_root=ctx.armance_root / "reports",
            event_bus=ctx.event_bus,
        )
        return (report.content or "[autonomous: empty mona reply]").strip()
    except Exception as exc:
        logger.exception("mona proxy checkpoint failed")
        return f"[autonomous: mona error: {exc}]"


def _role_staffing(wf, ctx) -> tuple[list[str], list[str], list[str]]:
    """Per-role health view of the workflow's required specialist roles.

    Returns ``(staffable_roles, sick_roles, sick_agent_labels)`` where a
    *sick* role has at least one roster agent but none healthy, and a
    *staffable* role has at least one healthy agent. Roles with no roster
    agent at all belong to neither list — the runner's absence path
    handles them step by step. `mona`/`serge` are staff, resolved at run
    time, and excluded.
    """
    required_roles = {
        (s.role or "").lower().strip() for s in wf.steps
    } - {"", "mona", "serge"}
    staffable: list[str] = []
    sick: list[str] = []
    labels: list[str] = []
    for role in sorted(required_roles):
        matches = [
            a for a in ctx.agents
            if not a.name.startswith("system-")
            and (a.role or "").lower().strip() == role
        ]
        if not matches:
            continue
        if any(_agent_is_healthy(a) for a in matches):
            staffable.append(role)
        else:
            sick.append(role)
            labels.extend(
                f"`{a.name}` ({getattr(a, 'last_health', '') or '?'})"
                for a in matches
            )
    return staffable, sick, labels


async def _cmd_workflow_run(
    name: str,
    enrich_sid: str | None,
    ctx: LoopContext,
    skip_preflight: bool = False,
    user_prompt_override: str | None = None,
    run_mode: str | None = None,
    depth: str = "quick",
    seed_docs: list[str] | None = None,
    seed_inputs: list[str] | None = None,
    provided_outputs: dict[str, str] | None = None,
    provided_sources: dict[str, str] | None = None,
    derived_from: list[dict[str, Any]] | None = None,
) -> str:
    # Lot I (partial re-run with human override): `provided_outputs` maps a
    # step id → the output to inject WITHOUT re-executing it (a human-edited
    # override, or an upstream output carried verbatim from the parent run).
    # `provided_sources` records where each came from (file basename or
    # `<parent-run>`), and `derived_from` is the parent+overrides provenance
    # written into the new run's manifest. Files are read SERVICE-side by the
    # caller (rerun_with_override skill) — `core` never touches disk.
    _provided = dict(provided_outputs or {})
    _provided_src = dict(provided_sources or {})
    from armance.service.checkpoint import Checkpoint
    # Check both .armance/workflows/ (Kim's dir) and legacy workflows/
    wf_path = ctx.armance_root / ".armance" / "workflows" / f"{name}.yaml"
    if not wf_path.exists():
        wf_path = ctx.armance_root / "workflows" / f"{name}.yaml"
    if not wf_path.exists():
        return t("workflow.not_found", name=name)
    from armance.core.models.workflow import load_workflow, execute_workflow
    wf = load_workflow(wf_path)

    # ── Seed documents (Lot B) ─────────────────────────────────────────────
    # Load existing material (e.g. a drafted tender) the steps want to
    # challenge/extend. Sources: every step's `seed_docs` (library files),
    # the extra `seed_docs` arg (web RunIn), and `--input` specs (ad-hoc
    # files). File I/O lives here in the service layer; the loaded text is
    # handed to execute_workflow via `inputs` under `seed.<basename>` keys —
    # `core` never reads the disk. `render_template` exposes them as
    # `{{seed.<basename>}}`; `_compose_default_prompt` injects a "## Seed
    # documents" section for steps without a template.
    from armance.service.seed_docs import (
        load_adhoc_seed_docs,
        load_library_seed_docs,
    )
    _lib_names: list[str] = list(seed_docs or [])
    for _step in wf.steps:
        _lib_names.extend(getattr(_step, "seed_docs", None) or [])
    workflow_inputs: dict[str, str] = {}
    workflow_inputs.update(load_library_seed_docs(ctx.armance_root, _lib_names))
    if seed_inputs:
        workflow_inputs.update(load_adhoc_seed_docs(seed_inputs))
    if workflow_inputs:
        # Any step referencing a seed by basename must be able to see it even
        # if only the CLI/web supplied it (not the step's own `seed_docs`
        # list). Attach every loaded basename to the root steps (no deps) so
        # the default-prompt seed block fires there.
        _loaded_names = [k[len("seed."):] for k in workflow_inputs]
        for _step in wf.steps:
            if not (getattr(_step, "depends_on", None) or []):
                for _bn in _loaded_names:
                    if _bn not in _step.seed_docs:
                        _step.seed_docs.append(_bn)

    # Auto-boost all boostable agents at run start if the depth mode is deep
    # (meaning intense). Kim's YAML assigns steps by `role`, not by explicit
    # `agents:` lists — so boost every boostable agent whose role appears in
    # the workflow (plus any explicitly named one).
    is_intense = (depth == "deep")
    if is_intense:
        step_agent_names: set[str] = set()
        step_roles: set[str] = set()
        for step in wf.steps:
            if getattr(step, "agents", None):
                step_agent_names.update(step.agents)
            role = (getattr(step, "role", "") or "").lower().strip()
            if role:
                step_roles.add(role)
        for agent in ctx.agents:
            in_workflow = (
                agent.name in step_agent_names
                or (agent.role or "").lower().strip() in step_roles
            )
            if in_workflow and agent.is_boostable:
                ctx.state.boosted_agents.add(agent.name)

    # ── Pre-run health check (degraded, not all-or-nothing) ────────────────
    # Team metaphor: a sick agent is *absent* — the run continues without
    # it and warns. Cheap: reads frontmatter (`last_health` from Malik's
    # recruit-time probe), no extra API call. We only refuse to launch
    # when NOT A SINGLE required role has a healthy agent: such a run
    # could not produce anything.
    staffable_roles, sick_roles, sick_labels = _role_staffing(wf, ctx)
    if sick_roles and not staffable_roles:
        msg = t("system_msg.workflow_health_block", agents=", ".join(sick_labels))
        # Surface the block on the web path: the run is launched as a detached
        # task whose return value is discarded, and the frontend tracks
        # progress via /active-workflow (which stays null because no run dir is
        # minted). Without an event the click is a silent no-op. Emit so the
        # SSE stream can show *why* nothing ran.
        bus = getattr(ctx, "event_bus", None)
        if bus is not None:
            try:
                await bus.emit(
                    "workflow.blocked",
                    attributes={
                        "workflow": name,
                        "reason": "unhealthy_agents",
                        "agents": ", ".join(sick_labels),
                        "message": msg,
                    },
                    severity="warn",
                )
            except Exception:  # noqa: BLE001 — telemetry must never break the path
                logger.debug("workflow.blocked emit failed", exc_info=True)
        return msg
    if sick_roles:
        degraded_msg = t("workflow.degraded_roles", roles=", ".join(sick_roles))
        ctx.append(degraded_msg)
        bus = getattr(ctx, "event_bus", None)
        if bus is not None:
            try:
                await bus.emit(
                    "workflow.degraded",
                    attributes={
                        "workflow": name,
                        "roles": ", ".join(sick_roles),
                        "agents": ", ".join(sick_labels),
                        "message": degraded_msg,
                    },
                    severity="warn",
                )
            except Exception:  # noqa: BLE001 — telemetry must never break the path
                logger.debug("workflow.degraded emit failed", exc_info=True)

    # user_prompt_override is set when called from TUI context (Kim/orchestrator)
    # so the workflow runs without a blocking prompt. Otherwise we ask via the
    # checkpoint handler (frontend-agnostic; web has no TTY).
    if user_prompt_override is not None:
        user_prompt = user_prompt_override
    else:
        if ctx.checkpoint_handler is None:
            return t("common.error", error="no checkpoint handler")
        resp = await ctx.checkpoint_handler.prompt(
            Checkpoint(id="workflow.prompt", prompt=t("prompts.workflow_prompt"), kind="text")
        )
        if resp.is_abort or not resp.content:
            return t("common.cancelled")
        user_prompt = resp.content

    if not skip_preflight:
        from armance.service.cost import estimate_workflow
        prices_override = getattr(ctx.cfg, "prices", None) or {}
        estimate = estimate_workflow(wf, ctx.agents, user_prompt, prices_override=prices_override, intense=is_intense)
        total = estimate["total_usd"]
        lines = [
            t("prompts.cost_estimate", total=f"{total:.4f}", steps=len(estimate["steps"]))
        ]
        for provider, cost in estimate["by_provider"].items():
            lines.append(f"  {provider}: ${cost:.4f}")
        if is_intense and estimate.get("boosted_count", 0) > 0:
            lines.append(t("boost.workflow_notice", count=estimate["boosted_count"]))
        ctx.append("\n".join(lines))
        if ctx.checkpoint_handler is None:
            return t("common.error", error="no checkpoint handler")
        confirm = await ctx.checkpoint_handler.prompt(
            Checkpoint(id="workflow.confirm",
                       prompt=t("prompts.confirm_run", total=f"{total:.4f}"),
                       kind="confirm")
        )
        if confirm.is_abort or confirm.content != "yes":
            return t("common.cancelled")

    prior_notes = ""
    if enrich_sid:
        transcript_path = ctx.armance_root / "sessions" / enrich_sid / "transcript.md"
        if transcript_path.exists():
            prior_notes = transcript_path.read_text(encoding="utf-8")
        else:
            prior_notes = ""
        user_prompt = f"Prior conversation notes:\n{prior_notes}\n\nUser request: {user_prompt}"

    from armance.core.models.task import Task
    from armance.service.workflow_runs import (
        add_step_warning,
        create_run,
        finalise as _finalise_run,
        mark_step_completed,
        mark_step_failed,
        mark_step_provided,
        mark_step_skipped,
        mark_step_started,
        write_running_manifest,
        write_step_output,
        write_step_prompt,
        write_synthesis,
    )

    # Mint a versioned run dir up-front; every step output lands there.
    artefact = create_run(ctx.armance_root, name, step_ids=[s.id for s in wf.steps])
    # Lot I: record parent+overrides provenance so the new run references the
    # parent instead of ever mutating it ("a run never overwrites a run").
    if derived_from:
        artefact.derived_from = list(derived_from)
        write_running_manifest(artefact)
    ctx.append(t("workflow.run_started", path=str(artefact.run_dir.relative_to(ctx.armance_root))))

    # Circuit breaker: after N consecutive absent steps (missing agent OR
    # every candidate failing), abort the whole run — the provider is
    # probably down; no point burning through an 18-step DAG.
    _fail_streak = {"count": 0, "max": 3}
    _absent_steps: list[str] = []

    class _WorkflowAbort(RuntimeError):
        pass

    # Set ONLY by a user abort at a checkpoint. A failed step no longer
    # aborts the run: its contribution is *absent* (team metaphor) and the
    # rest of the workflow keeps going with an absence note in its place.
    _run_aborted = {"flag": False, "reason": ""}

    async def _mark_absent(step, reason: str) -> str:
        """A step nobody could take: record it, warn, keep the run going.

        The returned note becomes the step's output, so downstream prompts
        see explicitly what is missing instead of silently losing it.
        """
        _set_status(ctx, step.id, "error")
        note = t(
            "workflow.step_absent_note",
            step_id=step.id, role=step.role or "?", reason=reason,
        )
        try:
            write_step_output(artefact, step.id, note)
        except Exception:  # noqa: BLE001
            logger.debug("could not persist absence note for %s", step.id, exc_info=True)
        mark_step_failed(artefact, step.id, reason)
        _absent_steps.append(step.id)
        ctx.append(t("workflow.step_absent_warn", step_id=step.id, role=step.role or "?"))
        bus = getattr(ctx, "event_bus", None)
        if bus is not None:
            try:
                await bus.emit(
                    "workflow.step_absent",
                    attributes={"step_id": step.id, "role": step.role or "", "reason": reason},
                    severity="warn",
                )
            except Exception:  # noqa: BLE001 — telemetry must never break the run
                logger.debug("workflow.step_absent emit failed", exc_info=True)
        _fail_streak["count"] += 1
        if _fail_streak["count"] >= _fail_streak["max"]:
            raise _WorkflowAbort(
                t("workflow.aborted_consecutive_absences", n=_fail_streak["max"])
            )
        return note

    async def runner(step, prompt: str) -> str:
        # Lot I: a provided/overridden step is NOT re-executed. Its output was
        # supplied service-side (human-edited override, or carried from parent);
        # return it verbatim so downstream templates resolve {{step.output}} to
        # it, mark the manifest `provided`, and burn 0 tokens. Core stays pure —
        # this is a service-layer runner decision.
        if step.id in _provided:
            text = _provided[step.id]
            write_step_output(artefact, step.id, text)
            mark_step_provided(
                artefact, step.id,
                _provided_src.get(step.id, "override"),
                stage=getattr(step, "stage", None) or None,
            )
            _set_status(ctx, step.id, "completed")
            return text
        # Short-circuit after a USER abort: skip the rest cleanly.
        if _run_aborted["flag"]:
            mark_step_skipped(artefact, step.id, _run_aborted["reason"])
            _set_status(ctx, step.id, "skipped")
            msg = f"[skipped: {_run_aborted['reason']}]"
            write_step_output(artefact, step.id, msg)
            return msg

        _set_status(ctx, step.id, "working")
        mark_step_started(artefact, step.id)
        task = Task(prompt=prompt, role=step.role, mode=step.mode)
        candidates = _step_agent_candidates(step.role, ctx)
        if not candidates:
            return await _mark_absent(
                step, t("workflow.no_agent_for_step", domain=step.role, step_id=step.id),
            )
        # Caveman policy:
        #   - specialist task / critique steps speak agent→agent → ultra
        #   - Mona's judge step produces the user-facing synthesis → none
        #   - deliverable step is read by the user → none
        step_caveman = "none" if step.kind in ("judge", "deliverable") else "ultra"
        # Failover: try the healthy candidates in order (max 2 attempts) —
        # like a team, when the first pick is out, a same-role peer steps in.
        last_error = ""
        for attempt, agent_obj in enumerate(candidates[:2]):
            try:
                report = await run_specialist(
                    agent_obj,
                    task,
                    ctx.armance_root,
                    ctx.cfg,
                    reports_root=ctx.armance_root / "reports",
                    caveman_level=step_caveman,
                    event_bus=ctx.event_bus,
                    boosted_agents=ctx.state.boosted_agents,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception(
                    "workflow step %s failed with agent %s", step.id, agent_obj.name,
                )
                last_error = str(exc)
                # Lot E.1: a candidate that fails (or an unhealthy second
                # regard that gets tried and errors) must NOT vanish silently
                # — the contradictory binôme is the whole point. Surface it in
                # the conversation and on the event bus so the user sees which
                # second look was lost and why.
                warn_msg = t(
                    "workflow.step_candidate_failed",
                    step_id=step.id, agent=agent_obj.name, error=str(exc),
                )
                ctx.append(warn_msg)
                try:
                    add_step_warning(artefact, step.id, warn_msg)
                except Exception:  # noqa: BLE001 — persistence must never break the run
                    logger.debug("could not persist step warning for %s", step.id, exc_info=True)
                bus = getattr(ctx, "event_bus", None)
                if bus is not None:
                    try:
                        await bus.emit(
                            "workflow.step_candidate_failed",
                            attributes={
                                "step_id": step.id,
                                "agent": agent_obj.name,
                                "error": str(exc),
                            },
                            severity="warn",
                        )
                    except Exception:  # noqa: BLE001 — telemetry must never break the run
                        logger.debug(
                            "workflow.step_candidate_failed emit failed", exc_info=True,
                        )
                continue
            if attempt > 0:
                ctx.append(t(
                    "workflow.step_failover",
                    step_id=step.id,
                    from_agent=candidates[0].name,
                    to_agent=agent_obj.name,
                ))
            _fail_streak["count"] = 0
            _set_status(ctx, step.id, "completed")
            write_step_output(artefact, step.id, report.content)
            def _safe_int(v):
                return v if isinstance(v, int) else None

            def _safe_float(v):
                return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None

            # Lot H: record the step's crucible stage + the family that ACTUALLY
            # spoke (failover-aware — agent_obj is the winner, not the candidate)
            # so the quality report reconstructs families-per-stage at report time.
            _stage = getattr(step, "stage", None) or None
            _family = None
            if _stage and _stage != "standard":
                from armance.service.workflow_crucible import model_family
                _family = model_family(
                    getattr(agent_obj, "provider", "") or "",
                    getattr(agent_obj, "model", "") or "",
                )
            mark_step_completed(
                artefact, step.id,
                tokens_in=_safe_int(getattr(report, "tokens_in", None)),
                tokens_out=_safe_int(getattr(report, "tokens_out", None)),
                cost_usd=_safe_float(getattr(report, "cost_usd", None)),
                agent=agent_obj.name,
                stage=_stage,
                family=_family,
            )
            if step.kind == "judge":
                write_synthesis(artefact, report.content)
            return report.content
        return await _mark_absent(
            step, t("workflow.step_error", step_id=step.id, error=last_error),
        )

    # Build checkpoint handler for human_checkpoint steps
    from armance.service.checkpoint import Checkpoint, CheckpointResponse

    _abort_state: dict[str, Any] = {"was_canceled": False, "step_id": None}

    def _mark_aborted(step_id: str) -> None:
        _abort_state["was_canceled"] = True
        _abort_state["step_id"] = step_id
        _run_aborted["flag"] = True
        _run_aborted["reason"] = f"user aborted at checkpoint `{step_id}`"

    async def _emit_qa(step, question: str, answer: str, by: str) -> None:
        """Record a checkpoint Q/A on the run + emit it so the web Flux tab can
        show the question and who answered (the user, or Mona in autonomous)."""
        bus = getattr(ctx, "event_bus", None)
        if bus is not None:
            try:
                await bus.emit("checkpoint.answered", attributes={
                    "step_id": getattr(step, "id", "?"),
                    "question": question,
                    "answer": answer,
                    "answered_by": by,
                })
            except Exception:  # noqa: BLE001 — never let telemetry break the run
                logger.debug("checkpoint.answered emit failed", exc_info=True)

    async def checkpoint_handler(step, prior_outputs: dict[str, str]) -> str:
        # After a user abort, later checkpoints must not prompt anyone —
        # the run is already being wound down.
        if _run_aborted["flag"]:
            return t("workflow.aborted")
        question = (getattr(step, "prompt", "") or "").strip()
        if not question:
            # Kim's YAML frequently omits `prompt:` on checkpoints; an empty
            # question shown to the user (or to Mona) is unanswerable.
            question = t(
                "workflow.checkpoint_default_prompt",
                step_id=getattr(step, "id", "?"),
            )
        # In autonomous mode, Mona speaks on behalf of the CEO. We ask the
        # mona meta-agent to answer the checkpoint based on the project
        # brief + upstream outputs, no TTY prompt to the user.
        if run_mode == "autonomous":
            proxy_res = await _mona_proxy_checkpoint(
                step, prior_outputs, ctx, question=question,
            )
            if proxy_res.startswith("[ASK_USER]"):
                reason_and_q = proxy_res[len("[ASK_USER]"):].strip()
                if ctx.checkpoint_handler is None:
                    raise RuntimeError("No checkpoint handler configured to prompt user.")
                checkpoint = Checkpoint(
                    id=getattr(step, "id", "?"),
                    prompt=f"{reason_and_q}\n\n(Original question: {question})",
                )
                response: CheckpointResponse = await ctx.checkpoint_handler.prompt(checkpoint)
                if response.is_abort:
                    _set_status(ctx, step.id, "canceled")
                    _mark_aborted(step.id)
                    ctx.append(f"[abort] workflow aborted at checkpoint '{step.id}'")
                    return t("workflow.aborted")
                await _emit_qa(step, question, response.content, "user")
                mark_step_completed(artefact, step.id, agent="user")
                return response.content
            await _emit_qa(step, question, proxy_res, "Mona")
            # Persist Mona's autonomous decision as a step file so the
            # hypotheses route (which scans step-*.md for the
            # `**Hypothèse (Mona) :**` marker) can surface it in the UI.
            try:
                write_step_output(
                    artefact, getattr(step, "id", "checkpoint"),
                    f"## Checkpoint — {question}\n\n{proxy_res}",
                )
            except Exception:
                logger.debug("could not persist mona checkpoint step file", exc_info=True)
            mark_step_completed(artefact, getattr(step, "id", "checkpoint"), agent="Mona")
            return proxy_res

        if ctx.checkpoint_handler is None:
            raise RuntimeError("No checkpoint handler configured to prompt user.")

        checkpoint = Checkpoint(
            id=getattr(step, "id", "?"),
            prompt=question,
        )
        response: CheckpointResponse = await ctx.checkpoint_handler.prompt(checkpoint)
        if response.is_abort:
            _set_status(ctx, step.id, "canceled")
            _mark_aborted(step.id)
            ctx.append(f"[abort] workflow aborted at checkpoint '{step.id}'")
            return t("workflow.aborted")
        await _emit_qa(step, question, response.content, "user")
        mark_step_completed(artefact, step.id, agent="user")
        return response.content

    # Safety-net hooks: cross-family advisory + Serge consensus auto-invoke.
    # validate_cross_family NEVER aborts — it only surfaces warnings via the
    # notify callback. The workflow always runs (user's choice).
    from armance.service.workflow_hooks import (
        check_consensus_and_maybe_invoke_serge,
        validate_cross_family,
    )

    async def _notify(kind: str, payload: dict) -> None:
        msg = payload.get("message") or str(payload)
        ctx.append(f"[{kind}] {msg}")

    def _on_step_prompt(step_id: str, prompt: str, template_used: bool) -> None:
        # Lot C: persist the effective prompt next to the step output so
        # a run is fully auditable/rejouable. core does no I/O — this hook
        # is the service-layer seam.
        try:
            write_step_prompt(artefact, step_id, prompt, template_used=template_used)
        except Exception:  # noqa: BLE001 — persistence must never break the run
            logger.debug("could not persist prompt for step %s", step_id, exc_info=True)

    async def _pre_run(workflow) -> None:
        await validate_cross_family(workflow, ctx.cfg, notify=_notify)

    async def _post_run(workflow, results, runner_fn) -> None:
        async def _critique(auto_step, payload):
            return await runner_fn(auto_step, payload)
        outcome = await check_consensus_and_maybe_invoke_serge(
            workflow, results, critique_runner=_critique, notify=_notify,
        )
        if outcome is not None:
            from armance.core.models.workflow import StepResult
            auto_id, auto_output = outcome
            results[auto_id] = StepResult(id=auto_id, output=auto_output)

    try:
        results = await execute_workflow(
            wf,
            user_prompt=user_prompt,
            runner=runner,
            prior_session_notes=prior_notes,
            checkpoint_handler=checkpoint_handler,
            pre_run_hook=_pre_run,
            post_run_hook=_post_run,
            armance_root=ctx.armance_root,
            on_step_prompt=_on_step_prompt,
            inputs=workflow_inputs,
        )
        # Auto-serge critique was injected post-run: persist it too.
        for sid, r in results.items():
            if sid.startswith("auto_") and not artefact.step_path(sid).exists():
                write_step_output(artefact, sid, r.output)

        # Assumptions register — Mona reviews step outputs, extracts
        # hypotheses/questions, writes assumptions.md next to synthesis.md.
        from armance.service.assumptions_ops import (
            compile_and_persist,
            split_exec_summary,
        )

        assumptions_content = await compile_and_persist(artefact, results, ctx)

        # Lot H: write the Creuset quality receipt (quality.md) BEFORE finalise
        # so the manifest's `quality_present` flag is accurate. No-op (returns
        # None) for a plain `standard` run — nothing is written.
        try:
            import json as _json
            from armance.service.workflow_quality_report import (
                build_crucible_report,
                render_crucible_report_md,
            )
            _running = _json.loads(artefact.manifest_path().read_text(encoding="utf-8"))
            _qr = build_crucible_report(_running, artefact.run_dir)
            if _qr is not None:
                (artefact.run_dir / "quality.md").write_text(
                    render_crucible_report_md(_qr), encoding="utf-8"
                )
        except Exception:  # noqa: BLE001 — the receipt must never break the run
            logger.debug("crucible quality report failed", exc_info=True)

        final_status = "canceled" if _abort_state["was_canceled"] else "completed"
        _finalise_run(artefact, status=final_status)
        if _abort_state["was_canceled"]:
            return t(
                "workflow.run_aborted",
                step_id=_abort_state["step_id"],
                path=str(artefact.run_dir.relative_to(ctx.armance_root)),
            )
        run_path = str(artefact.run_dir.relative_to(ctx.armance_root))
        # Last non-empty step output → 150-char preview
        last_output = ""
        for r in reversed(list(results.values())):
            if r.output and r.output.strip():
                last_output = r.output.strip()
                break
        preview = last_output[:150].replace("\n", " ")
        mona_offer = t("workflow.run_mona_offer")
        final_msg = t("workflow.run_preview", path=run_path, preview=preview, mona_offer=mona_offer)
        if _absent_steps:
            final_msg += "\n" + t(
                "workflow.run_absences", steps=", ".join(f"`{s}`" for s in _absent_steps),
            )
        exec_summary = split_exec_summary(assumptions_content)
        if exec_summary:
            final_msg += t("workflow.assumptions_header") + exec_summary
        return final_msg
    except _WorkflowAbort as exc:
        # Circuit breaker: consecutive absent steps — provider likely down.
        _finalise_run(artefact, status="failed")
        return str(exc)
    except asyncio.CancelledError:
        # Web Stop button (run_task.cancel()) or process shutdown: leave an
        # honest terminal manifest, then let the cancellation propagate.
        _finalise_run(artefact, status="canceled")
        raise
    except RuntimeError as exc:
        _finalise_run(artefact, status="canceled")
        return str(exc)
    except Exception as exc:
        _finalise_run(artefact, status="failed")
        logger.exception("workflow execution failed")
        return t("common.error", error=str(exc))


# ---------------------------------------------------------------------------
# /workflow design <name> / new
# ---------------------------------------------------------------------------

async def _cmd_workflow_design(name_or_input: str, ctx: LoopContext) -> str:
    """Slash entry point. The skill expects Kim's full LLM reply with an
    inline YAML block; when invoked from the CLI we don't have that, so we
    redirect the user to talk to Kim in NL."""
    return t("workflow.deprecated_design")


# ---------------------------------------------------------------------------
# /workflow dispatcher
# ---------------------------------------------------------------------------

async def _cmd_workflow(args: list[str], ctx: LoopContext) -> str:
    if not args:
        return t("workflow.usage_root")
    sub = args[0].lower()
    if sub == "new":
        return t("workflow.deprecated_design")
    if sub == "run":
        if len(args) < 2:
            return t("workflow.usage_run")
        name = args[1]
        enrich_sid: str | None = None
        if "--enrich" in args:
            idx = args.index("--enrich")
            if idx + 1 < len(args):
                enrich_sid = args[idx + 1]
        skip_preflight = "--yes" in args
        depth = "deep" if "--deep" in args or "--intense" in args else "quick"
        # --input <file> (repeatable): ad-hoc seed docs to challenge/extend.
        # Accepts `--input path` or `--input key=path`. NL alias handled by
        # the router (e.g. "run <name> with <file>").
        seed_inputs: list[str] = []
        for i, tok in enumerate(args):
            if tok == "--input" and i + 1 < len(args):
                seed_inputs.append(args[i + 1])
        return await _cmd_workflow_run(
            name, enrich_sid, ctx,
            skip_preflight=skip_preflight, depth=depth,
            seed_inputs=seed_inputs or None,
        )
    if sub == "design":
        if len(args) < 2:
            return t("workflow.usage_design")
        name_or_input = " ".join(args[1:])
        return await _cmd_workflow_design(name_or_input, ctx)
    if sub == "list":
        return await _cmd_workflow_list(ctx, args[1:])
    if sub == "compare":
        return await _cmd_workflow_compare(ctx, args[1:])
    if sub in ("rerun", "re-run"):
        return await _cmd_workflow_rerun(ctx, args[1:])
    return t("workflow.unknown_sub", sub=sub)


async def _cmd_workflow_rerun(ctx: LoopContext, args: list[str]) -> str:
    """Lot I: partial re-run with human output override.

    Reads the override file(s) SERVICE-side, carries the parent run's other
    step outputs, and re-runs only downstream steps via `_cmd_workflow_run`
    (provided steps are not re-executed). A brand-new run is minted — the
    parent is never overwritten (`derived_from` records the provenance).
    """
    from armance.core.models.workflow import load_workflow
    from armance.service.skills.rerun_with_override import (
        RerunWithOverrideSkill,
        parse_rerun_args,
    )
    try:
        plan = parse_rerun_args(" ".join(args))
    except ValueError as exc:
        return str(exc)

    skill = RerunWithOverrideSkill(ctx.armance_root)
    wf_path = ctx.armance_root / ".armance" / "workflows" / f"{plan['workflow']}.yaml"
    if not wf_path.exists():
        wf_path = ctx.armance_root / "workflows" / f"{plan['workflow']}.yaml"
    if not wf_path.exists():
        return t("workflow.not_found", name=plan["workflow"])
    try:
        wf = load_workflow(wf_path)
        override_texts = skill.read_overrides(plan["overrides"])
    except ValueError as exc:
        return str(exc)
    parent_outputs = skill.load_parent_outputs(plan["workflow"], plan["parent_run_id"])
    if not parent_outputs:
        return f"Run parent `{plan['parent_run_id']}` introuvable ou vide."
    deps = {s.id: list(s.depends_on) for s in wf.steps}
    built = skill.build_plan(
        plan["parent_run_id"], override_texts, parent_outputs,
        plan["from_step"], deps,
    )
    return await _cmd_workflow_run(
        plan["workflow"], None, ctx,
        skip_preflight=True,
        user_prompt_override="(re-run partiel avec override humain)",
        provided_outputs=built["provided"],
        provided_sources=built["sources"],
        derived_from=built["derived_from"],
    )


async def _cmd_workflow_list(ctx: LoopContext, args: list[str]) -> str:
    """List runs for a workflow: `/workflow list <name>`."""
    from armance.service.workflow_runs import list_runs
    if not args:
        return t("workflow.list_usage")
    wf = args[0]
    runs = list_runs(ctx.armance_root, wf)
    if not runs:
        return t("workflow.list_empty", workflow=wf)
    lines = [t("workflow.list_header", workflow=wf, n=len(runs))]
    for r in runs:
        lines.append(
            f"- `{r['run_id']}` — {r['status']} — "
            f"{len(r.get('steps', []))} step(s) — {r['ended_at'] or r['started_at']}"
        )
    return "\n".join(lines)


async def _cmd_workflow_compare(ctx: LoopContext, args: list[str]) -> str:
    """Compare two runs of the same workflow: `/workflow compare <name> <run1> <run2>`."""
    from armance.service.workflow_runs import load_run
    if len(args) < 3:
        return t("workflow.compare_usage")
    wf, r1, r2 = args[0], args[1], args[2]
    a = load_run(ctx.armance_root, wf, r1)
    b = load_run(ctx.armance_root, wf, r2)
    if not a or not b:
        return t("workflow.compare_not_found", workflow=wf, run1=r1, run2=r2)
    # Queue both runs into Mona's next prompt and switch to him so the
    # comparison happens with full evidence in context.
    pending = list(ctx.session.metadata.get("mona_pending_run_load", []))
    pending.extend([f"{wf}::{r1}", f"{wf}::{r2}"])
    ctx.session.metadata["mona_pending_run_load"] = pending
    ctx.state.current_agent = "system-judge"
    ctx.session.save()
    return t("workflow.compare_queued", workflow=wf, run1=r1, run2=r2)



# /deliverable lives in armance.service.task_ops.


# /library and [EXECUTE:/library-status] handlers live in
# armance.service.library_ops (imported at top of this file). The references
# below are kept so the HANDLERS table near the end of the module can
# resolve them by their original private names.


# ---------------------------------------------------------------------------
# /save — freeze context to L0
# ---------------------------------------------------------------------------

# /save (L0/L1/L2) handler lives in armance.service.save_ops, imported at top.


# /role, /agents, /agent, /feedback-loop, /iterate-from handlers
# live in armance.service.role_ops (imported at top).


# ---------------------------------------------------------------------------
# dispatcher table
# ---------------------------------------------------------------------------

HANDLERS = {
    "help": _cmd_help,
    "quit": _cmd_quit,
    "switch": _cmd_switch,
    "model": _cmd_model,
    "effort": _cmd_effort,
    "task": _cmd_task,
    "report": _cmd_report,
    "judge": _cmd_judge,
    "export": _cmd_export,
    "workflow": _cmd_workflow,
    "deliverable": _cmd_deliverable,
    "save": _cmd_save,
    "role": _cmd_role,
    "agents": _cmd_agents,
    "agent": _cmd_agent,
    "feedback-loop": _cmd_feedback_loop,
    "feedback_loop": _cmd_feedback_loop,
    "iterate-from": _cmd_iterate_from,
    "iterate_from": _cmd_iterate_from,
    "footprint": _cmd_footprint,
    "empreinte": _cmd_footprint,
    "library": _cmd_library,
    "lib": _cmd_library,
    # Legacy aliases (route into /library)
    "rag-status": lambda args, ctx: _library_dispatch(["status"], ctx),
    "rag_status": lambda args, ctx: _library_dispatch(["status"], ctx),
    "rag": lambda args, ctx: _library_dispatch(["status"], ctx),
    "scan": lambda args, ctx: _library_dispatch(["scan"], ctx),
    "load": lambda args, ctx: _library_dispatch(["load", *args], ctx),
    "forget": lambda args, ctx: _library_dispatch(["unindex", *args], ctx),
    "ingest-docs": lambda args, ctx: _library_dispatch(["index", *args], ctx),
    "ingest_docs": lambda args, ctx: _library_dispatch(["index", *args], ctx),
}
