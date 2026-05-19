"""Demote agent skill — remove an agent from lead on a topic.

Skill: ``DemoteAgentSkill``
Slash: ``/agent demote <name> <topic>``
NL patterns: "aisha n'est plus lead", "demote agent", "remove lead"

Calls ``AgentLifecycleService.demote_agent()``.
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


class DemoteAgentSkill:
    """Skill that demotes an agent from lead on a topic.

    Example::

        skill = DemoteAgentSkill(armance_root=Path(".armance"))
        result = skill.run("historian-aisha textiles")
    """

    slash = "/agent demote"
    nl_patterns = [
        "n'est plus lead",
        "demote agent",
        "remove lead",
        "unlead",
    ]
    triggered_by = "user"

    def __init__(self, armance_root: Path) -> None:
        self.armance_root = armance_root

    def run(self, args: str = "") -> str:
        """Execute the demote agent skill.

        Args:
            args: "agent_name topic", e.g. "historian-aisha textiles"

        Returns:
            User-friendly result message.
        """
        parsed = self._parse_args(args)
        if not parsed or not parsed.name or not parsed.topic:
            return "Usage: ``/agent demote <name> <topic>``"

        service = AgentLifecycleService(self.armance_root)

        try:
            agent = service.demote_agent(parsed.name, parsed.topic)
            return f"**{agent.name}** is no longer lead on ``{parsed.topic}``."
        except AgentNotFoundError as exc:
            return f"Error: {exc}"
        except AgentLifecycleError as exc:
            return f"Error: {exc}"

    def _parse_args(self, args: str) -> argparse.Namespace | None:
        """Parse skill arguments."""
        parser = argparse.ArgumentParser(description="Demote agent")
        parser.add_argument("name", help="Agent name")
        parser.add_argument("topic", help="Topic slug")
        try:
            return parser.parse_args(args.strip().split() if args.strip() else [])
        except SystemExit:
            return None
