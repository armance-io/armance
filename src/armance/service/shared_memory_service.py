"""SharedMemoryService — cross-agent bulletin board.

Reads/writes `.armance/shared_memory/` files and provides a per-agent
digest for system-prompt injection.

Spec: docs/spec/17_shared_memory.md
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from armance.service.context_service import ContextService

logger = logging.getLogger(__name__)

_ROSTER_FILE = "roster.yaml"
_DECISIONS_FILE = "decisions.md"
_PENDING_FILE = "pending_addressed.json"
_ADDRESSING_FILE = "addressing_log.jsonl"


class SharedMemoryService:
    """Read-only access to shared_memory; builds per-agent digests."""

    def __init__(self, armance_root: Path) -> None:
        self.armance_root = armance_root
        self._sm_dir = armance_root / "shared_memory"
        self._context = ContextService(armance_root)

    # ------------------------------------------------------------------
    # Project brief (delegates to ContextService / L0)
    # ------------------------------------------------------------------

    def get_project_brief(self) -> str:
        return self._context.read_l0_body() or ""

    # ------------------------------------------------------------------
    # Roster
    # ------------------------------------------------------------------

    def get_roster(self) -> list[dict[str, Any]]:
        roster_path = self._sm_dir / _ROSTER_FILE
        if not roster_path.exists():
            return []
        try:
            data = yaml.safe_load(roster_path.read_text(encoding="utf-8")) or {}
            return data.get("specialists", [])
        except Exception:
            logger.exception("Failed to load roster.yaml")
            return []

    # ------------------------------------------------------------------
    # Pending addressed
    # ------------------------------------------------------------------

    def get_pending_addressed(self, agent_id: str) -> list[dict[str, Any]]:
        pending_path = self._sm_dir / _PENDING_FILE
        if not pending_path.exists():
            return []
        try:
            data = json.loads(pending_path.read_text(encoding="utf-8"))
            return data.get(agent_id, [])
        except Exception:
            logger.exception("Failed to load pending_addressed.json")
            return []

    # ------------------------------------------------------------------
    # Digest
    # ------------------------------------------------------------------

    def digest_for_agent(self, agent_id: str) -> str:
        """Build injectable markdown digest for the given agent.

        Includes: project brief (L0), roster, recent decisions (≤5),
        and pending @-mentions for this agent.
        """
        parts: list[str] = []

        brief = self.get_project_brief()
        if brief:
            parts.append(f"## Project Brief\n\n{brief.strip()}")

        roster = self.get_roster()
        if roster:
            lines = ["## Team Roster\n"]
            for spec in roster:
                name = spec.get("canonical", spec.get("name", "?"))
                role = spec.get("role", "")
                persona = spec.get("persona", "")
                model = spec.get("model", "")
                lines.append(f"- **{name}** ({role} · {persona}) — {model}")
            parts.append("\n".join(lines))

        decisions = self._read_recent_decisions(n=5)
        if decisions:
            parts.append(f"## Recent Decisions\n\n{decisions}")

        pending = self.get_pending_addressed(agent_id)
        if pending:
            lines = [f"## Pending mentions (@{agent_id})\n"]
            for entry in pending:
                from_ = entry.get("from_", "?")
                snippet = entry.get("snippet", "")
                ts = entry.get("ts", "")
                lines.append(f"- [{ts}] {from_}: {snippet}")
            parts.append("\n".join(lines))

        return "\n\n".join(parts)

    def _read_recent_decisions(self, n: int = 5) -> str:
        decisions_path = self._sm_dir / _DECISIONS_FILE
        if not decisions_path.exists():
            return ""
        content = decisions_path.read_text(encoding="utf-8").strip()
        if not content:
            return ""
        # Each decision is a ## block; return up to n blocks
        import re
        blocks = re.split(r"\n(?=## )", content)
        recent = blocks[-n:] if len(blocks) > n else blocks
        return "\n\n".join(b.strip() for b in recent if b.strip())


class RosterService:
    """Manages roster.yaml — updated on every lifecycle op."""

    def __init__(self, armance_root: Path) -> None:
        self.armance_root = armance_root
        self._sm_dir = armance_root / "shared_memory"

    def refresh(self) -> None:
        """Recompute roster.yaml from the agents/ directory.

        Only active agents are included in the YAML roster; archived ones are excluded.
        All non-archived agents (including system-*) receive agent_card.json sidecars.
        """
        from armance.core.models.agent import Agent
        from armance.storage.paths import agent_card_path

        agents_dir = self.armance_root / "agents"
        specialists: list[dict[str, Any]] = []

        if agents_dir.exists():
            for agent_file in sorted(agents_dir.glob("*.md")):
                try:
                    agent = Agent.load(agent_file)
                except (ValueError, FileNotFoundError):
                    continue
                if agent.status == "archived":
                    continue

                # Write A2A agent_card.json sidecar for every non-archived agent
                self._write_agent_card(agent, agent_card_path(self.armance_root, agent.name))

                # Skip staff agents (system-*) from the YAML roster
                if agent.name.startswith("system-"):
                    continue
                entry: dict[str, Any] = {
                    "canonical": agent.name,
                    "role": agent.domain or agent.role or "",
                    "persona": agent.persona or "",
                    "provider": agent.provider or "",
                    "model": agent.model or "",
                    "provider_family": agent.provider_family or "",
                    "version": agent.version,
                    "lead_for": agent.lead_for,
                    "recruited_at": agent.created_at or "",
                    "updated_at": agent.updated_at or "",
                }
                if agent.lead_for:
                    entry["lead_for"] = agent.lead_for
                specialists.append(entry)

        roster = {"specialists": specialists}
        self._sm_dir.mkdir(parents=True, exist_ok=True)
        roster_path = self._sm_dir / _ROSTER_FILE
        roster_path.write_text(
            yaml.safe_dump(roster, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        logger.info("Roster refreshed: %d active specialists", len(specialists))

    def _write_agent_card(self, agent: Any, path: Path) -> None:
        """Write an A2A-shaped agent_card.json sidecar next to the agent .md file."""
        description = (agent.system_prompt or "").strip().split("\n")[0][:200]
        card: dict[str, Any] = {
            "name": agent.name,
            "description": description,
            "version": "1",
            "skills": [
                {
                    "name": "answer_question",
                    "description": "Answer a question scoped to the agent's role.",
                },
                {
                    "name": "produce_deliverable",
                    "description": "Produce a markdown deliverable for a workflow step.",
                },
            ],
            "capabilities": {
                "streaming": True,
                "push_notifications": False,
            },
            "endpoint": None,
            "auth": None,
            "provider_family": agent.provider_family or "",
        }
        path.write_text(json.dumps(card, indent=2, ensure_ascii=False), encoding="utf-8")
