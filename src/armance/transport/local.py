"""Local in-process transport for Armance.

This module provides a pass-through transport that calls the service
layer directly without any network overhead. It's used for local
development and testing.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from armance.transport.dto import (
    AgentInfo,
    ContextInfo,
    Event,
    RoleInfo,
    TaskInfo,
    WorkflowInfo,
)
from armance.transport import Transport

if TYPE_CHECKING:
    from armance.service.armance_service import ArmanceService

logger = logging.getLogger(__name__)


class LocalTransport(Transport):
    """In-process transport that calls ArmanceService directly."""

    def __init__(self, service: ArmanceService) -> None:
        self._service = service
        self._running = False

    async def start(self) -> None:
        """Initialize the transport layer."""
        self._running = True
        logger.info("LocalTransport started")

    async def stop(self) -> None:
        """Clean up and close the transport."""
        self._running = False
        logger.info("LocalTransport stopped")

    async def list_agents(self) -> list[AgentInfo]:
        """List all agents in the project."""
        return await self._service.list_agents()

    async def get_agent(self, name: str) -> AgentInfo:
        """Get a specific agent by name."""
        return await self._service.get_agent(name)

    async def switch_agent(self, name: str) -> None:
        """Switch to a different agent."""
        await self._service.switch_agent(name)

    async def list_roles(self) -> list[RoleInfo]:
        """List all roles in the project."""
        return await self._service.list_roles()


    async def list_context_versions(self) -> list[ContextInfo]:
        """List all context versions."""
        return await self._service.list_context_versions()

    async def load_context(self, version: str) -> None:
        """Load a specific context version."""
        await self._service.load_context(version)

    async def list_tasks(self) -> list[TaskInfo]:
        """List all tasks."""
        return await self._service.list_tasks()

    async def create_task(self, brief: str, assignees: list[str]) -> str:
        """Create a new task."""
        return await self._service.create_task(brief, assignees)

    async def run_task(self, task_id: str) -> None:
        """Run a task."""
        await self._service.run_task(task_id)

    async def list_workflows(self) -> list[WorkflowInfo]:
        """List all workflows."""
        return await self._service.list_workflows()

    async def run_workflow(self, name: str, user_prompt: str) -> None:
        """Run a workflow."""
        await self._service.run_workflow(name, user_prompt)

    async def events(self) -> asyncio.Queue[Event]:
        """Async iterator over state change events."""
        return await self._service.events()
