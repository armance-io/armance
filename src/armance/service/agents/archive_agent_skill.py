"""Archive agent skill — archive or hard-delete an agent.

Skill: ``ArchiveAgentSkill``
Slash: ``/agent archive <name> [--hard] [--confirm]``
NL patterns: "archive aisha", "vire aisha", "delete agent", "supprimer"

Calls ``AgentLifecycleService.archive_agent()``.

Spec reference: ``[spec:20_agent_lifecycle.md§Archive]``

Confirmation requirement:
When ``hard=True``, the skill MUST ask for confirmation via ``--confirm`` flag.
Without confirmation, a ``ValueError`` is raised to prevent accidental data loss.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from armance.service.agents.agent_lifecycle_service import (
    AgentLifecycleError,
    AgentLifecycleService,
    AgentNotFoundError,
)

logger = logging.getLogger(__name__)


class ArchiveAgentSkill:
    """Skill that archives or hard-deletes an agent.

    Hard delete requires explicit confirmation via ``--confirm`` flag.

    Example::

        skill = ArchiveAgentSkill(armance_root=Path(".armance"))
        result = skill.run("historian-aisha --hard --confirm")
    """

    slash = "/agent archive"
    nl_patterns = [
        "archive ",
        "vire ",
        "delete agent",
        "supprimer",
        "remove agent",
    ]
    triggered_by = "user"

    def __init__(self, armance_root: Path) -> None:
        self.armance_root = armance_root

    def run(self, args: str = "") -> str:
        """Execute the archive agent skill.

        Args:
            args: "agent_name [--hard] [--confirm]", e.g. "historian-aisha --hard --confirm"

        Returns:
            User-friendly result message.

        Raises:
            ValueError: If ``hard=True`` but ``--confirm`` is not provided.
        """
        parsed = self._parse_args(args)
        if not parsed or not parsed.name:
            return "Usage: ``/agent archive <name> [--hard] [--confirm]``"

        # Hard delete requires confirmation
        if parsed.hard and not parsed.confirm:
            raise ValueError("Hard delete requires confirmation via --confirm flag")

        service = AgentLifecycleService(self.armance_root)

        try:
            agent = service.archive_agent(parsed.name, hard=parsed.hard)
            action = "hard-deleted" if parsed.hard else "archived"
            return f"**{agent.name}** {action}. Conversation kept read-only."
        except AgentNotFoundError as exc:
            return f"Error: {exc}"
        except AgentLifecycleError as exc:
            return f"Error: {exc}"

    def _parse_args(self, args: str) -> argparse.Namespace | None:
        """Parse skill arguments."""
        parser = argparse.ArgumentParser(description="Archive agent")
        parser.add_argument("name", help="Agent name")
        parser.add_argument("--hard", action="store_true", help="Hard delete instead of archive")
        parser.add_argument("--confirm", action="store_true", help="Confirm hard delete")
        try:
            return parser.parse_args(args.strip().split() if args.strip() else [])
        except SystemExit:
            return None
