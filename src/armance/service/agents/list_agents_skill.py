"""List agents skill — show the full team roster.

Skill: ``ListAgentsSkill``
Slash: ``/agents``
NL patterns: "qui est dans l'equipe?", "list my agents", "donne-moi le roster", "show team"

Reads all agents from the lifecycle service and renders a markdown table
with name, role, persona, model, family, status, and lead topics.
"""

from __future__ import annotations

from pathlib import Path

from armance.service.agents.agent_lifecycle_service import AgentLifecycleService


class ListAgentsSkill:
    """Skill that lists all agents in a markdown table.

    Example::

        skill = ListAgentsSkill(armance_root=Path(".armance"))
        result = skill.run()
    """

    slash = "/agents"
    nl_patterns = [
        "qui est dans l'equipe",
        "list my agents",
        "donne-moi le roster",
        "show team",
        "show agents",
        "list agents",
        "team roster",
    ]
    triggered_by = "user"

    def __init__(self, armance_root: Path, include_archived: bool = False) -> None:
        self.armance_root = armance_root
        self.include_archived = include_archived

    def run(self) -> str:
        """Execute the list agents skill.

        Returns:
            Markdown table string with agent details.
        """
        service = AgentLifecycleService(self.armance_root)
        agents = service.list_agents(include_archived=self.include_archived)

        if not agents:
            return "No agents found. Use ``/agent create`` or ask Malik to recruit."

        lines = [
            "| Name | Role | Persona | Model | Family | Status | Lead For |",
            "|---|---|---|---|---|---|---|",
        ]

        for agent in agents:
            lines.append(
                f"| {agent.name} "
                f"| {agent.role or '-'} "
                f"| {agent.persona} "
                f"| {agent.model} "
                f"| {agent.provider_family or '-'} "
                f"| {agent.status} "
                f"| {', '.join(agent.lead_for) or '-'} |"
            )

        return "\n".join(lines)
