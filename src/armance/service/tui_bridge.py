"""Bridge between Textual TUI and the existing service-layer handlers.

Builds a LoopContext, dispatches user input (slash commands or free text)
to the appropriate handler, and returns formatted reply + label info for
the chat view.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

from armance.service.loop_context import AgentStatus, LoopContext
from armance.core.models.agent import Agent

if TYPE_CHECKING:
    from armance.config import Config
    from armance.platform.events import EventBus
    from armance.service.llm_service import TokenLedger
    from armance.service.session import SessionState, Session
    from armance.service.checkpoint import CheckpointHandler

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Agent label formatting
# ---------------------------------------------------------------------------

# System agents: stem -> (display_name, role_title)
# Personas (figés):
#   Armance — weaver (tisserande, frames projects, weaves tempo)
#   Malik  — scout (dénicheur, recruits diverse specialist panels)
#   Kim    — conductor (orchestratrice, orchestrates process/workflows)
#   Mona   — distiller (distillatrice, bridges vision/production, extracts quintessence)
#   Serge  — critic (critique, stress-tests syntheses)
SYSTEM_AGENT_PERSONAS: dict[str, tuple[str, str]] = {
    "system-context":      ("Armance", "weaver"),
    "system-hr":           ("Malik",   "scout"),
    "system-orchestrator": ("Kim",     "conductor"),
    "system-judge":        ("Mona",    "distiller"),
    "system-challenger":   ("Serge",   "critic"),
}

# All meta-agent display ids (used by sidebar to show Hosts & Staff section)
META_AGENTS: list[tuple[str, str, str]] = [
    # (canonical_name, first_name, title)
    ("system-context",      "Armance", "weaver"),
    ("system-hr",           "Malik",   "scout"),
    ("system-orchestrator", "Kim",     "conductor"),
    ("system-judge",        "Mona",    "distiller"),
    ("system-challenger",   "Serge",   "critic"),
]

# First-names reserved for permanent staff — user agents cannot use these.
RESERVED_STAFF_NAMES: frozenset[str] = frozenset(
    first_name.lower() for _, first_name, _ in META_AGENTS
)


def resolve_meta_agent(name: str) -> str | None:
    """Map a first-name (Armance/Malik/Kim/Mona/Serge) to canonical agent id."""
    n = name.strip().lower()
    for canonical, first_name, _ in META_AGENTS:
        if n == first_name.lower():
            return canonical
    return None


def agent_label(agent_name: str | None, agents: list[Agent]) -> tuple[str, str]:
    """Return (label, role_color) for the chat view.

    Examples:
      Tom (role=woodworker)        -> ("Tom · woodworker", "agent")
      system-context               -> ("Armance · host", "system")
      system-hr                    -> ("Malik · recruiter", "system")
      system-orchestrator          -> ("Kim · operator", "system")
      system-judge                 -> ("Mona · vice-president", "system")
      None / unknown               -> ("agent", "agent")
    """
    if not agent_name:
        return ("agent", "agent")

    stem = agent_name.lower()
    persona = SYSTEM_AGENT_PERSONAS.get(stem)
    if persona is None and stem.startswith("system-"):
        # Fallback for unknown system-* agents
        bare = stem.replace("system-", "")
        persona = (bare.capitalize(), "agent")
    if persona is not None:
        first_name, title = persona
        return (f"{first_name} · {title}", "agent")

    # Find the user agent definition
    agent = next((a for a in agents if a.name == agent_name), None)
    if agent is None:
        return (agent_name, "agent")

    role_val = agent.role or agent.domain or ""
    if role_val:
        return (f"{agent.name} · {role_val}", "agent")
    return (agent.name, "agent")


# ---------------------------------------------------------------------------
# Agent loading
# ---------------------------------------------------------------------------

def load_user_agents(armance_root: Path) -> list[Agent]:
    """Load every non-system .md agent under .armance/agents/."""
    agents_dir = armance_root / "agents"
    if not agents_dir.exists():
        return []
    out: list[Agent] = []
    # Sort by creation time so Malik's recruitment order is preserved in sidebar.
    paths = sorted(agents_dir.glob("*.md"), key=lambda p: p.stat().st_mtime)
    for path in paths:
        if path.stem.startswith("system-") or path.stem.lower() in RESERVED_STAFF_NAMES:
            continue
        try:
            out.append(Agent.load(path))
        except Exception:
            logger.exception("failed to load agent %s", path)
    return out


def find_agents_by_role(agents: list[Agent], role: str) -> list[Agent]:
    """Return agents whose role or domain matches `role` (case-insensitive)."""
    r = role.lower()
    return [a for a in agents if (a.role or a.domain or "").lower() == r]




def find_agent_by_name(agents: list[Agent], name: str) -> Agent | None:
    """Match by exact name or first-name prefix (case-insensitive)."""
    n = name.lower()
    for a in agents:
        if a.name.lower() == n:
            return a
    # First-name prefix (e.g. "Tom" matches "tom-audacious" or just "Tom")
    for a in agents:
        if a.name.lower().startswith(n):
            return a
    return None


# ---------------------------------------------------------------------------
# Natural-language switch detection
# ---------------------------------------------------------------------------

# Switch is EXPLICIT: only `@<Name>` at the start of the message (with or
# without trailing text) triggers it. Natural-language verbs ("talk to",
# "change", "switch to") matched too aggressively — saying "Malik, change
# Priya's model" used to silently switch to Priya. Use `/switch` for the
# verb-driven path.
_SWITCH_AT_RE = re.compile(r"^\s*@(?P<target>[\w\-]+)", re.I)


def detect_switch_intent(text: str) -> str | None:
    """Return the target name if the text starts with `@<Name>`, else None."""
    m = _SWITCH_AT_RE.match(text)
    return m.group("target") if m else None


# ---------------------------------------------------------------------------
# LoopContext factory
# ---------------------------------------------------------------------------

def make_loop_context(
    armance_root: Path,
    cfg: "Config",
    state: "SessionState",
    session: "Session",
    ledger: "TokenLedger",
    checkpoint_handler: "CheckpointHandler" | None = None,
    event_bus: "EventBus | None" = None,
) -> LoopContext:
    """Build a LoopContext suitable for service.handlers dispatch."""
    agents = load_user_agents(armance_root)
    statuses = [AgentStatus(name=a.name) for a in agents]
    return LoopContext(
        armance_root=armance_root,
        cfg=cfg,
        state=state,
        session=session,
        ledger=ledger,
        statuses=statuses,
        agents=agents,
        checkpoint_handler=checkpoint_handler,
        event_bus=event_bus,
    )



# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

async def dispatch_input(text: str, ctx: LoopContext) -> tuple[str, str | None]:
    """Route user input to the right handler.

    Returns (reply_text, agent_name_for_label).

    - Slash command → routes to handlers.HANDLERS[name]
    - Natural-language switch → updates ctx.state.current_agent, returns confirmation
    - Free text → routes to _cmd_chat (which delegates to context/HR/normal agents)
    """
    from armance.nls import t
    from armance.service.handlers import HANDLERS, _cmd_chat

    text_stripped = text.strip()



    # 1) Slash command
    if text_stripped.startswith("/"):
        body = text_stripped[1:]
        parts = body.split()
        if not parts:
            return (t("dispatch.usage_command"), None)
        cmd = parts[0].lower()
        args = parts[1:]

        if cmd in ("quit", "exit", "q"):
            return ("[quit]", None)
        if cmd == "clear":
            return ("[clear]", None)

        handler = HANDLERS.get(cmd)
        if handler is None:
            return (t("dispatch.unknown_command", cmd=cmd), None)
        try:
            reply = await handler(args, ctx)
        except Exception as exc:
            logger.exception("handler /%s failed", cmd)
            reply = t("dispatch.handler_error", cmd=cmd, error=str(exc))
        return (reply, ctx.state.current_agent)

    # 2) Explicit `@<Name>` switch (with optional trailing text to forward)
    # Special case: @mention with trailing text → switch + forward the text
    _at_match = re.match(r"^\s*@([\w\-]+)\s*[,\s]\s*(.+)", text_stripped, re.DOTALL)
    _at_mention_text: str | None = None
    if _at_match:
        _at_mention_text = _at_match.group(2).strip()

    target = detect_switch_intent(text_stripped)
    if target:
        # Meta-agent first-name lookup (Armance / Malik / Kim / Mona)
        meta = resolve_meta_agent(target)
        if meta is not None:
            ctx.state.current_agent = meta
            ctx.session.save()
            if _at_mention_text:
                # Forward remaining text to the switched-to agent
                return await dispatch_input(_at_mention_text, ctx)
            label, _ = agent_label(meta, ctx.agents)
            return (t("nl_switch.switched_meta", label=label), meta)

        agent = find_agent_by_name(ctx.agents, target)
        if agent is not None:
            ctx.state.current_agent = agent.name
            ctx.session.save()
            if _at_mention_text:
                return await dispatch_input(_at_mention_text, ctx)
            label, _ = agent_label(agent.name, ctx.agents)
            return (t("nl_switch.switched_agent", label=label), agent.name)

        candidates = find_agents_by_role(ctx.agents, target)
        if len(candidates) == 1:
            ctx.state.current_agent = candidates[0].name
            ctx.session.save()
            if _at_mention_text:
                return await dispatch_input(_at_mention_text, ctx)
            label, _ = agent_label(candidates[0].name, ctx.agents)
            return (t("nl_switch.switched_by_role", label=label), candidates[0].name)
        if len(candidates) > 1:
            names = " · ".join(f"{a.name}" for a in candidates)
            return (
                t("nl_switch.multiple_for_role", target=target, names=names),
                ctx.state.current_agent,
            )
        # Unknown: fall through to chat (don't block user)
        logger.debug("switch target %r matched no agent; passing through", target)

    # 3) Free text → chat with current agent
    if ctx.state.current_agent is None:
        # Default to system-context if nothing selected
        ctx.state.current_agent = "system-context"

    try:
        reply = await _cmd_chat(text, ctx)
    except Exception as exc:
        logger.exception("chat dispatch failed")
        reply = f"error: {exc}"

    return (reply, ctx.state.current_agent)
