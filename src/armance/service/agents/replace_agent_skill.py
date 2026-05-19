"""Replace agent skill — atomic fire-and-rehire of a specialist.

Skill: ``ReplaceAgentSkill``
Slash: ``/agent replace <old_name> with <new_persona>``
NL patterns: "remplace aisha", "replace agent", "swap agent"

Calls ``AgentLifecycleService.replace_agent()`` which archives the old agent
and recruits a replacement in a single transaction.

Spec reference: ``[spec:20_agent_lifecycle.md§Replace (atomic fire + rehire)]``
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


class ReplaceAgentSkill:
    """Skill that replaces an agent with a new specialist.

    Example::

        skill = ReplaceAgentSkill(armance_root=Path(".armance"))
        result = skill.run("historian-aisha with revisionist")
    """

    slash = "/agent replace"
    nl_patterns = [
        "remplace ",
        "replace agent",
        "swap agent",
        "remplacer ",
    ]
    triggered_by = "user"

    def __init__(self, armance_root: Path) -> None:
        self.armance_root = armance_root

    def run(self, args: str = "") -> str:
        """Execute the replace agent skill.

        Args:
            args: "old_name with new_persona", e.g. "historian-aisha with revisionist"

        Returns:
            User-friendly result message.
        """
        parsed = self._parse_args(args)
        if not parsed or not parsed.old_name or not parsed._with or not parsed.new_persona:
            return "Usage: ``/agent replace <old_name> with <new_persona>``"

        service = AgentLifecycleService(self.armance_root)

        try:
            old_name, new_agent = service.replace_agent(parsed.old_name, parsed.new_persona)
            return (
                f"**{old_name}** archived. Malik recruited **{new_agent.name}** "
                f"({parsed.new_persona} {new_agent.domain})."
            )
        except AgentNotFoundError as exc:
            return f"Error: {exc}"
        except AgentLifecycleError as exc:
            return f"Error: {exc}"

    def _parse_args(self, args: str) -> argparse.Namespace | None:
        """Parse skill arguments.

        Expected format: "old_name with new_persona"
        The literal word "with" is the separator.
        """
        parser = argparse.ArgumentParser(description="Replace agent")
        parser.add_argument("old_name", help="Agent name to replace")
        parser.add_argument("_with", metavar="with", help="Separator keyword")
        parser.add_argument("new_persona", help="New persona for replacement")
        try:
            return parser.parse_args(args.strip().split() if args.strip() else [])
        except SystemExit:
            return None
