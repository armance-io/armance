"""Per-agent conversation-turn visibility policy.

Single source of truth for which past turns an agent may see in the DM/chat
path. Enforces competence boundaries: a turn directed at one agent (e.g. a
recruitment request to Malik) must NOT leak into another agent's history.

NOTE: this gates ONLY the conversational `history` list passed to the chat
path. The workflow path injects context through the system prompt and passes
NO history — it is intentionally untouched.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from armance.core.models.turn import Turn

# Armance's framing channel — project-level context every agent inherits.
_FRAMING_AGENTS = {"system-context", "context", "armance"}

# Recruitment-relevant agents Malik may see cross-talk from. Mirrors the
# legacy malik.py _MALIK_AGENTS = {"system-hr", "malik"} (normalised to "hr"),
# plus framing, so Malik keeps its recruitment + framing context.
_MALIK_AGENTS = {"hr"}


def _norm(agent: str | None) -> str:
    return (agent or "").lower().replace("system-", "")


_FRAMING_NORMS = frozenset(_norm(a) for a in _FRAMING_AGENTS)


def visible_turns(turns: list["Turn"], viewer: str) -> list[dict[str, str]]:
    """Filter `turns` to those within `viewer`'s competence scope.

    Returns role/content dicts ready for the LLM messages list.
    """
    viewer_norm = _norm(viewer)
    is_armance = viewer_norm in _FRAMING_NORMS
    is_malik = viewer_norm in {"hr", "malik"}

    out: list[dict[str, str]] = []
    for turn in turns:
        agent_norm = _norm(turn.agent)
        visible = (
            is_armance
            or turn.agent == viewer
            or agent_norm == viewer_norm
            or agent_norm in _FRAMING_NORMS
            or (is_malik and agent_norm in _MALIK_AGENTS)
        )
        if visible:
            out.append({"role": turn.role, "content": turn.content})
    return out
