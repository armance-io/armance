"""Edit agent skill — update agent attributes.

Skill: ``EditAgentSkill``
Slash: ``/agent edit <name> [--persona <persona>] [--model <model>] [--force]``
NL patterns: "modifie aisha", "edit agent", "change persona"

Calls ``AgentLifecycleService.update_agent()`` with the provided fields.
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


class EditAgentSkill:
    """Skill that edits an existing agent's attributes.

    Example::

        skill = EditAgentSkill(armance_root=Path(".armance"))
        result = skill.run("--historian-aisha --persona revisionist")
    """

    slash = "/agent edit"
    nl_patterns = [
        "modifie ",
        "edit agent",
        "change persona",
        "update agent",
        "modifier ",
    ]
    triggered_by = "user"

    def __init__(self, armance_root: Path) -> None:
        self.armance_root = armance_root

    def run(self, args: str = "") -> str:
        """Execute the edit agent skill.

        Args:
            args: Raw argument string, e.g. "--historian-aisha --persona revisionist --force"

        Returns:
            User-friendly result message.
        """
        parsed = self._parse_args(args)
        if not parsed or not parsed.name:
            return "Usage: ``/agent edit <name> [--persona <persona>] [--model <model>] [--system-prompt <text>] [--force]``"

        service = AgentLifecycleService(self.armance_root)

        try:
            agent = service.update_agent(
                parsed.name,
                persona=parsed.persona,
                model=parsed.model,
                system_prompt=parsed.system_prompt,
                force_version=parsed.force,
            )
            version_note = f" (v{agent.version})" if agent.version > 1 else ""
            return f"**{agent.name}** updated{version_note}. Persona: ``{agent.persona}``, Model: ``{agent.model}``"
        except AgentNotFoundError as exc:
            return f"Error: {exc}"
        except AgentLifecycleError as exc:
            return f"Error: {exc}"

    def _parse_args(self, args: str) -> argparse.Namespace | None:
        """Parse skill arguments."""
        parser = argparse.ArgumentParser(description="Edit agent")
        parser.add_argument("name", nargs="?", help="Agent name")
        parser.add_argument("--persona", help="New persona stance")
        parser.add_argument("--model", help="New model")
        parser.add_argument("--system-prompt", dest="system_prompt", help="New system prompt")
        parser.add_argument("--force", action="store_true", help="Force version bump")
        try:
            return parser.parse_args(args.strip().split() if args.strip() else [])
        except SystemExit:
            return None
