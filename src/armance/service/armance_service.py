"""ArmanceService - main service layer API.

This module exposes the public API for Armance, which is consumed by
the transport layer (LocalTransport, gRPC) and ultimately by the TUI.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import AsyncIterator, List

from armance.transport.dto import (
    AgentInfo,
    ContextInfo,
    Event,
    RoleInfo,
    TaskInfo,
    WorkflowInfo,
)

logger = logging.getLogger(__name__)


class ArmanceService:
    """Main service layer for Armance."""

    def __init__(self, armance_root: Path) -> None:
        self.armance_root = armance_root
        self._agents: List[AgentInfo] = []
        self._roles: List[RoleInfo] = []
        self._tasks: List[TaskInfo] = []
        self._workflows: List[WorkflowInfo] = []
        self._events: List[Event] = []

    async def start(self) -> None:
        """Initialize the service."""
        await self._load_agents()
        await self._load_roles()
        await self._load_workflows()
        logger.info("ArmanceService started for %s", self.armance_root)

    async def stop(self) -> None:
        """Clean up the service."""
        logger.info("ArmanceService stopped")

    async def _load_roles(self) -> None:
        """Load roles from .armance/roles/."""
        roles_dir = self.armance_root / "roles"
        if not roles_dir.exists():
            return

        for path in sorted(roles_dir.glob("*.md")):
            try:
                role_name = path.stem
                # Find agents that are in this role's domain
                agents_for_role = []
                for agent in self._agents:
                    if agent.domain == role_name:
                        agents_for_role.append(agent.name)
                self._roles.append(RoleInfo(
                    name=role_name,
                    agents=agents_for_role,
                    description="",
                ))
            except Exception as exc:
                logger.warning("Failed to load role %s: %s", path.name, exc)

    async def _load_agents(self) -> None:
        """Load agents from .armance/agents/."""
        from armance.core.models.agent import Agent

        agents_dir = self.armance_root / "agents"
        if not agents_dir.exists():
            return

        for path in sorted(agents_dir.glob("*.md")):
            try:
                agent = Agent.load(path)
                self._agents.append(AgentInfo(
                    name=agent.name,
                    domain=agent.domain,
                    kind=agent.kind if hasattr(agent, "kind") else AgentInfo.__pydantic_fields__.get("kind"),
                    persona=agent.persona,
                    provider=agent.provider,
                    model=agent.model,
                    reasoning=agent.reasoning,
                    system_prompt=agent.system_prompt,
                ))
            except Exception as exc:
                logger.warning("Failed to load agent %s: %s", path.name, exc)

    async def _load_workflows(self) -> None:
        """Load workflows from .armance/workflows/."""
        from armance.core.models.workflow import load_workflow

        workflows_dir = self.armance_root / "workflows"
        if not workflows_dir.exists():
            return

        for path in sorted(workflows_dir.glob("*.yaml")):
            try:
                workflow = load_workflow(path)
                self._workflows.append(WorkflowInfo(
                    name=workflow.name,
                    path=path,
                    steps=[],
                    created_at=workflow.created_at if hasattr(workflow, "created_at") else None,
                ))
            except Exception as exc:
                logger.warning("Failed to load workflow %s: %s", path.name, exc)

    async def list_agents(self) -> List[AgentInfo]:
        """List all agents in the project."""
        return self._agents

    async def get_agent(self, name: str) -> AgentInfo:
        """Get a specific agent by name."""
        for agent in self._agents:
            if agent.name == name:
                return agent
        raise ValueError(f"Agent not found: {name}")

    async def switch_agent(self, name: str) -> None:
        """Switch to a different agent."""
        await self.get_agent(name)  # Validate agent exists
        # In a real implementation, this would update session state

    async def list_roles(self) -> List[RoleInfo]:
        """List all roles in the project."""
        return self._roles

    async def list_context_versions(self) -> List[ContextInfo]:
        """List all context versions."""

        context_dir = self.armance_root / "context"
        if not context_dir.exists():
            return []

        versions = []
        for path in sorted(context_dir.glob("L0_v*.md")):
            versions.append(ContextInfo(
                version=path.stem,
                layer="L0",
                theme=None,
                created_at=None,
            ))

        return versions

    async def load_context(self, version: str) -> None:
        """Load a specific context version."""
        # In a real implementation, this would load and apply context
        pass

    async def list_tasks(self) -> List[TaskInfo]:
        """List all tasks."""
        return self._tasks

    async def create_task(self, brief: str, assignees: List[str]) -> str:
        """Create a new task."""
        # In a real implementation, this would create and store a task
        return "task_id_placeholder"

    async def run_task(self, task_id: str) -> None:
        """Run a task."""
        # In a real implementation, this would execute the task
        pass

    async def list_workflows(self) -> List[WorkflowInfo]:
        """List all workflows."""
        return self._workflows

    async def run_workflow(self, name: str, user_prompt: str) -> None:
        """Run a workflow."""
        # In a real implementation, this would execute the workflow
        pass

    async def events(self) -> AsyncIterator[Event]:
        """Async iterator over state change events."""
        # In a real implementation, this would yield events from the event stream
        while True:
            yield Event(timestamp=None, type="placeholder")
