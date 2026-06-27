"""Team-roster injection — every agent knows the whole team, cheaply.

Used by `SpecialistRunner._build_layered_context` (so it reaches every agent,
Malik included). Reads `.armance/agents/*.md`, skips built-in staff
(`system-*`) and helper files (`_*`), groups peers by role.

Token discipline: we **declare** the roster (names grouped by role) but do NOT
inline each persona — a pointer to the agent `.md` files lets a curious agent
read a colleague's full persona on demand instead of paying for it every turn.
"""
from __future__ import annotations

import logging
from pathlib import Path

from armance.core.models.agent import Agent

logger = logging.getLogger(__name__)


def build_team_roster(armance_root: Path, current_name: str) -> str:
    """Render a compact team roster, excluding `current_name`.

    One line per role: ``**role**: Name, Name``. No per-agent prose — just a
    pointer to `.armance/agents/<name>.md` for the full persona. Returns '' when
    no other specialist is on board.
    """
    agents_dir = armance_root / "agents"
    if not agents_dir.exists():
        return ""

    by_role: dict[str, list[str]] = {}
    for path in sorted(agents_dir.glob("*.md")):
        stem = path.stem
        if stem.startswith("system-") or stem.startswith("_"):
            continue
        if stem == current_name:
            continue
        try:
            peer = Agent.load(path)
        except Exception:
            logger.debug("roster: failed to load %s", path, exc_info=True)
            continue
        role = (peer.role or "specialist").strip()
        by_role.setdefault(role, []).append(peer.name)

    if not by_role:
        return ""

    lines = ["## Your team"]
    for role in sorted(by_role):
        lines.append(f"- **{role}**: {', '.join(by_role[role])}")
    lines.append(
        "Build on a colleague's point or push against it by name; never "
        "duplicate someone who shares your role. Each persona lives in "
        "`.armance/agents/<name>.md` if you need their full angle."
    )
    return "\n".join(lines)
