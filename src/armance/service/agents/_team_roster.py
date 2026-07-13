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


def build_team_roster(
    armance_root: Path, current_name: str, *, show_health: bool = False
) -> str:
    """Render a compact team roster, excluding `current_name`.

    One line per role: ``**role**: Name, Name``. No per-agent prose — just a
    pointer to `.armance/agents/<name>.md` for the full persona. Returns '' when
    no other specialist is on board.

    `show_health=True` appends a ``⚠ (status)`` marker to any agent whose
    `last_health` is an error — used for Malik so it knows which agents to
    repair with `/agent-swap`. Specialists get the lean, health-free view.
    It also annotates each agent with its provider *family* (``[anthropic]``,
    ``[google]``…) so Malik can spread a Creuset's `draft` steps across
    DISTINCT families (§G2) instead of concentrating them on one — a
    same-family critique validates by sycophancy.
    """
    from armance.service.workflow_crucible import model_family
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
        label = peer.name
        if show_health:
            family = (peer.provider_family or "").strip() or model_family(
                peer.provider or "", peer.model or ""
            )
            if family:
                label += f" [{family}]"
            health = (peer.last_health or "").strip()
            if health.startswith("error"):
                label += f" ⚠ ({health})"
        by_role.setdefault(role, []).append(label)

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
    if show_health:
        lines.append(
            "The `[family]` tag is each agent's provider family. For a Creuset "
            "workflow, the `draft` steps MUST span DISTINCT families (ideally "
            "anthropic + google + openai), the `critique` a further different "
            "family, and the `gate` a family ≠ the `synthesis` — a same-family "
            "critique validates by sycophancy. Recruit/swap to cover the "
            "families the drafts need; if your setup offers only one family, "
            "say so plainly (it is a config limit, never a fault)."
        )
    return "\n".join(lines)
