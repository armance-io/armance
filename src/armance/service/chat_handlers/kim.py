"""Kim (system-orchestrator) — workflow design + run chat shell.

NL-first dialogue, mirrors Malik's pattern:
  1. Load Kim's prompt.
  2. Build [SYSTEM CONTEXT] addon (project brief, roster, workflows,
     strategies, YAML contract).
  3. Filter history to Kim turns only.
  4. run_specialist() — no library/docs plumbing.
  5. Scrub via sandbox.
  6. Intercept [EXECUTE:/workflow-design] → parse Kim's YAML block.
  7. Intercept [EXECUTE:/workflow-run:<name>] → run the workflow.
  8. Agent-to-agent forwarding for `@Malik, ...` etc.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from armance.nls import t
from armance.service.agent_sandbox import scrub_reply
from armance.service.agent_visibility import visible_turns
from armance.service.agents.specialist_runner import run_specialist
from armance.service.chat_handlers.common import resolve_agent_path, set_status
from armance.service.library_ops import intercept_library_status
from armance.service.loop_context import LoopContext

logger = logging.getLogger(__name__)


KIM_AGENT_NAME = "system-orchestrator"
_META_FORWARD_TARGETS = {
    "Armance": "system-context",
    "Malik": "system-hr",
    "Kim": "system-orchestrator",
    "Mona": "system-judge",
    "Serge": "system-challenger",
}
_FORWARD_RE = re.compile(
    r"(?m)^\s*@(Malik|Armance|Kim|Mona|Serge)\s*[,:]\s*(.+)$"
)
_WF_RUN_RE = re.compile(
    r"\[EXECUTE:/workflow-run:([^\]:]+)(?::([a-z]+))?\]"
)
_DESIGN_TAG = "[EXECUTE:/workflow-design]"
_YAML_FENCE_WF_RE = re.compile(r"```(?:yaml)?\s*\n(name:.*?)\n```", flags=re.DOTALL)

# User intents that signal Kim should emit a workflow (safety-net trigger).
_USER_DESIGN_INTENTS = (
    "workflow", "flux", "crée", "cree", "créer", "create", "design",
    "sauvegarde", "sauve", "save", "valide", "enregistre",
)


async def cmd_orchestrator_chat(
    text: str,
    ctx: LoopContext,
    *,
    workflow_runner: Any,
) -> str:
    """Run one Kim turn.

    `workflow_runner` is the async function used to execute a workflow when
    Kim emits `[EXECUTE:/workflow-run:<name>]`. Injected to keep this
    module free of circular imports against handlers.py.
    """
    from armance.core.models.agent import Agent
    from armance.core.models.task import Task
    from armance.service.skills.design_workflow import DesignWorkflowSkill

    set_status(ctx, KIM_AGENT_NAME, "working")
    ctx.session.metadata.pop("kim_design_state", None)  # legacy

    kim_path = resolve_agent_path(ctx.armance_root, "system-orchestrator")
    if kim_path is None:
        set_status(ctx, KIM_AGENT_NAME, "error")
        return t("meta_agent.kim_missing")
    kim_agent = Agent.load(kim_path)

    addon = _build_system_context(ctx)
    history = visible_turns(ctx.session.conversation.turns, KIM_AGENT_NAME)

    ctx.session.conversation.append("user", text, agent=KIM_AGENT_NAME)

    try:
        task = Task(
            prompt=text, domain="meta", mode="light", requested_agent=KIM_AGENT_NAME,
        )
        report = await run_specialist(
            kim_agent,
            task,
            ctx.armance_root,
            ctx.cfg,
            reports_root=ctx.armance_root / "reports",
            history=history,
            system_addon=addon,
            event_bus=ctx.event_bus,
        )
        reply = scrub_reply(report.content, agent_role="kim")
        set_status(ctx, KIM_AGENT_NAME, "completed")
    except Exception as exc:
        set_status(ctx, KIM_AGENT_NAME, "error")
        logger.exception("Kim LLM failed")
        reply = t("common.error", error=str(exc))

    reply = _normalise_tool_call_run(reply)
    reply = _inject_design_tag_if_yaml_only(reply, text)
    reply = _intercept_design(reply, ctx, DesignWorkflowSkill)
    reply = await _intercept_run(reply, ctx, workflow_runner, text)
    reply = intercept_library_status(reply, ctx)

    forwarded = await _maybe_forward(reply, ctx, text)
    if forwarded is not None:
        return forwarded

    ctx.session.conversation.append("assistant", reply, agent=KIM_AGENT_NAME)
    ctx.session.save()
    ctx._last_output = reply
    return reply


def _build_system_context(ctx: LoopContext) -> str:
    # Workflows may live under <armance_root>/workflows or
    # <armance_root>/.armance/workflows depending on how the skill was invoked.
    wf_dir = ctx.armance_root / ".armance" / "workflows"
    if not wf_dir.exists():
        wf_dir = ctx.armance_root / "workflows"
    wf_names = [p.stem for p in wf_dir.glob("*.yaml")] if wf_dir.exists() else []

    roster_lines: list[str] = []
    role_by_name: dict[str, str] = {}
    for a in ctx.agents:
        if a.name.startswith("system-"):
            continue
        role = (a.domain or "specialist").strip().lower()
        roster_lines.append(
            f"  - name=`{a.name}` · role=`{role}` · model=`{a.model or '?'}`"
        )
        role_by_name[a.name] = role

    distinct_roles = sorted(set(role_by_name.values())) if role_by_name else []

    lines: list[str] = ["", "[SYSTEM CONTEXT]"]
    if ctx.state.project_brief:
        lines.append("Project brief (Armance's L0):")
        lines.append(ctx.state.project_brief.strip())
        lines.append("")
    lines.append("Team roster (note: `name` is the agent's first name; `role` is what they do):")
    if roster_lines:
        lines.extend(roster_lines)
    else:
        lines.append("  (empty — escalate to @Malik before designing)")
    lines.append("")
    if distinct_roles:
        lines.append(
            "VALID step `role:` values for workflow YAML (use one of these — "
            "never an agent's first name): "
            + ", ".join(f"`{d}`" for d in distinct_roles)
            + ", `mona`, `serge`."
        )
        lines.append("")
    lines.append(
        "Staff (judge / critique only — NEVER list as team members): "
        "mona (judge / final synthesis), serge (critique)."
    )
    lines.append("")
    if wf_names:
        lines.append("Existing workflows: " + ", ".join(f"`{n}`" for n in wf_names))
        lines.append("")
    lines.append(
        "Strategies (starting points; user may adjust): "
        "🟢 rapide / 🟡 équilibrée / 🔴 approfondie. "
        "Use these names; legacy short/standard/deep are aliases."
    )
    lines.append(
        "Cost & complexity: tier + gem only (🟢 minimal / 🟡 modéré / 🔴 élevé). "
        "Never quote dollar amounts."
    )
    lines.append(
        "WORKFLOW DESIGN PROTOCOL — follow strictly:\n"
        "  Step 1 (explore): Ask questions, gather requirements. Do NOT emit the tag.\n"
        "  Step 2 (recap): When you have enough, present a NAMED, STRUCTURED summary of "
        "the proposed workflow (title, strategy, list of steps with role + purpose). "
        "End with: 'Veux-tu que je sauvegarde ce workflow ?' (or equivalent in user's language). "
        "Do NOT emit the tag yet.\n"
        "  Step 3 (confirm): ONLY if the user replies with an EXPLICIT yes — words like "
        "'oui', 'yes', 'valide', 'sauvegarde', 'go', 'vas-y', 'parfait', 'ok' — "
        "emit `[EXECUTE:/workflow-design]` followed immediately by the ```yaml block.\n"
        "  NEVER skip Step 2. NEVER emit the tag without a preceding explicit confirmation.\n"
        "  The YAML must contain `name` (kebab-case), `strategy`, and `steps`. "
        "Each step has `id`, `kind`, `role`, `depends_on`. "
        "CRITICAL: step `role` is one of the roster values listed above (or `mona`/`serge`) "
        "— NEVER an agent's first name like `theodore`."
    )
    lines.append(
        "WORKFLOW RUN PROTOCOL — strict:\n"
        "  To launch a workflow you MUST emit exactly `[EXECUTE:/workflow-run:<name>]` "
        "(optionally `[EXECUTE:/workflow-run:<name>:autonomous]` or `:interactive`).\n"
        "  Python intercepts the tag and actually starts the run.\n"
        "  ❌ Do NOT narrate fake progress: never write '🔄 Workflow lancé', "
        "'étape démarrée', '🔹 démarré', 'en attente de…', 'avancement…' or "
        "anything that pretends the workflow is in progress UNLESS the tag is "
        "in the same reply.\n"
        "  ❌ Do NOT invent specialist questions like 'Aicha a besoin de toi: …' "
        "— specialists only speak through the workflow runner, not through you.\n"
        "  If the user asks for status, point them at `.armance/exports/<wf>/run-*/` "
        "or say plainly that no run is active."
    )
    return "\n".join(lines)


_BARE_WF_RE = re.compile(r"(?m)^(name:\s+\S.*)$", flags=re.MULTILINE)
_WF_YAML_FENCE_RE = re.compile(
    r"```(?:yaml)?\s*\n(.*?name\s*:.*?steps\s*:.*?)\n```", re.DOTALL,
)
# Combined intents: explicit save verbs + explicit confirmation words.
# Kept intentionally broad — this is a last-resort safety net, not a trigger.
_USER_SAVE_INTENTS = (
    "sauvegarde", "sauve", "save", "crée", "cree", "créer", "creer",
    "enregistre", "valide", "parfait", "do it", "fais-le",
    "workflow", "flux", "design", "create",
    "oui", "yes", "go", "vas-y", "ok",
)




def _latest_workflow_name(ctx: LoopContext) -> str | None:
    """Return the most-recently-modified workflow file's stem.

    Workflows can live under either `<armance_root>/workflows/` (canonical
    when armance_root IS the `.armance` dir) or
    `<armance_root>/.armance/workflows/` (when armance_root is the project
    root — the legacy convention used by the design skill). Scan both.
    """
    candidates: list[Path] = []
    for wf_dir in (
        ctx.armance_root / "workflows",
        ctx.armance_root / ".armance" / "workflows",
    ):
        if wf_dir.exists():
            candidates.extend(wf_dir.glob("*.yaml"))
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0].stem


# Structural detector: any `<tool_call>` markup or malformed [EXECUTE:...]
# variant referring to workflow-run. Language-agnostic — covers the most
# common ways a weak LLM mangles the canonical tag.
_MALFORMED_RUN_TAG_RE = re.compile(
    r"(?:"
    # <tool_call>execute:workflow-run:NAME[:MODE]   (with _ / - / space)
    r"<tool_call>\s*execute[:_\- ]+workflow[_\- ]*run[:_\- ]+(?P<n1>[\w\-]+)(?:[:_\- ]+(?P<m1>\w+))?|"
    # [EXECUTE:workflow-run:...]   (missing leading slash)
    r"\[\s*EXECUTE\s*:\s*workflow[_\- ]*run\s*:\s*(?P<n2>[\w\-]+)(?:\s*:\s*(?P<m2>\w+))?\s*\]|"
    # /workflow-run:NAME   (just a slash-command echo)
    r"`?/workflow[_\- ]*run\s*:\s*(?P<n3>[\w\-]+)(?:\s*:\s*(?P<m3>\w+))?`?"
    r")",
    re.IGNORECASE,
)


def _normalise_tool_call_run(reply: str) -> str:
    """Rewrite any malformed run-tag variant into the canonical
    `[EXECUTE:/workflow-run:NAME[:MODE]]` so `_intercept_run` actually fires.

    Structural — no language-specific keywords."""
    # If a canonical tag is already present, leave the reply alone.
    if "[EXECUTE:/workflow-run:" in reply:
        return reply
    m = _MALFORMED_RUN_TAG_RE.search(reply)
    if not m:
        return reply
    name = m.group("n1") or m.group("n2") or m.group("n3")
    mode = m.group("m1") or m.group("m2") or m.group("m3")
    if not name:
        return reply
    canonical = f"[EXECUTE:/workflow-run:{name}{(':' + mode) if mode else ''}]"
    # Replace the matched span with the canonical tag.
    return reply[: m.start()] + canonical + reply[m.end():]





def _inject_design_tag_if_yaml_only(reply: str, user_text: str) -> str:
    """Safety net: weak LLMs (e.g. Laguna) emit workflow YAML without
    [EXECUTE:/workflow-design]. Handles fenced blocks AND bare YAML.
    Injects the tag so _intercept_design fires and the skill saves the file."""
    if _DESIGN_TAG in reply:
        return reply
    has_name = "name:" in reply
    has_steps = "steps:" in reply
    if not (has_name and has_steps):
        return reply
    low = (user_text or "").lower().strip()
    if not any(intent in low for intent in _USER_SAVE_INTENTS):
        return reply
    logger.warning("Kim emitted workflow YAML without %s; injecting tag", _DESIGN_TAG)
    # Fenced block: inject before the opening fence.
    fence = _WF_YAML_FENCE_RE.search(reply)
    if fence:
        start = fence.start()
        return reply[:start].rstrip() + f"\n\n{_DESIGN_TAG}\n" + reply[start:]
    # Bare YAML (no backticks): find first `name:` line, wrap in fence.
    bare = _BARE_WF_RE.search(reply)
    if bare:
        start = bare.start()
        return reply[:start].rstrip() + f"\n\n{_DESIGN_TAG}\n```yaml\n" + reply[start:].rstrip() + "\n```"
    return reply


_YAML_BLOCK_RE = re.compile(r"```(?:yaml)?\s*\n.*?\n```", re.DOTALL)


def _intercept_design(reply: str, ctx: LoopContext, SkillCls) -> str:
    if _DESIGN_TAG not in reply:
        return reply
    kim_full_reply = reply
    reply = reply.replace(_DESIGN_TAG, "").strip()
    # Strip fenced YAML block from visible reply — user never needs raw YAML
    reply = _YAML_BLOCK_RE.sub("", reply).strip()
    non_meta = [a for a in ctx.agents if not a.name.startswith("system-")]
    if not non_meta:
        return reply + "\n\n" + t("workflow.design_blocked_no_team")
    skill = SkillCls(
        armance_root=ctx.armance_root.parent,
        config=ctx.cfg,
        agents=ctx.agents,
        project_brief=ctx.state.project_brief or "",
    )
    skill_reply = skill.run(args=kim_full_reply, ctx={})
    return reply + ("\n\n" if reply else "") + skill_reply


async def _intercept_run(
    reply: str,
    ctx: LoopContext,
    workflow_runner: Any,
    user_text: str,
) -> str:
    m = _WF_RUN_RE.search(reply)
    if not m:
        return reply
    wf_name = m.group(1).strip()
    mode = (m.group(2) or "").strip().lower() or None  # "interactive" | "autonomous" | None
    reply = _WF_RUN_RE.sub("", reply).strip()
    non_meta = [a for a in ctx.agents if not a.name.startswith("system-")]
    if not non_meta:
        return reply + "\n\n" + t("workflow.run_blocked_no_team")
    wf_prompt = (
        ctx.state.project_brief
        or ctx.session.metadata.get("host_cached_brief", "")
        or user_text
    )
    run_reply = await workflow_runner(
        wf_name, enrich_sid=None, ctx=ctx,
        skip_preflight=True, user_prompt_override=wf_prompt,
        run_mode=mode,
    )
    return reply + ("\n\n" if reply else "") + run_reply


async def _maybe_forward(reply: str, ctx: LoopContext, user_text: str) -> str | None:
    fm = _FORWARD_RE.search(reply)
    if not fm:
        return None
    target_meta = _META_FORWARD_TARGETS[fm.group(1)]
    if target_meta == KIM_AGENT_NAME:
        return None
    forwarded_request = fm.group(2).strip()
    ctx.state.current_agent = target_meta
    ctx.session.save()
    ctx.session.conversation.append("assistant", reply, agent=KIM_AGENT_NAME)
    from armance.service.tui_bridge import dispatch_input as _dispatch
    forwarded_reply = await _dispatch(forwarded_request, ctx)
    forwarded_text = (
        forwarded_reply[0] if isinstance(forwarded_reply, tuple) else forwarded_reply
    )
    # One-shot delegation; restore Kim.
    ctx.state.current_agent = KIM_AGENT_NAME
    ctx.session.save()
    out = (
        reply
        + "\n\n"
        + t("system_msg.forwarded", target=fm.group(1))
        + "\n\n"
        + str(forwarded_text)
    )
    ctx._last_output = out
    return out
