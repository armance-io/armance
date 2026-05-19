"""Transport base classes for Armance."""

from __future__ import annotations

import abc
import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from armance.transport.dto import (
        AgentInfo,
        ContextInfo,
        Event,
        RoleInfo,
        TaskInfo,
        WorkflowInfo,
    )


class Transport(abc.ABC):
    """Abstract base class for Armance transport layers."""

    @abc.abstractmethod
    async def start(self) -> None:
        """Initialize the transport layer."""

    @abc.abstractmethod
    async def stop(self) -> None:
        """Clean up and close the transport."""

    @abc.abstractmethod
    async def list_agents(self) -> list[AgentInfo]:
        """List all agents in the project."""

    @abc.abstractmethod
    async def get_agent(self, name: str) -> AgentInfo:
        """Get a specific agent by name."""

    @abc.abstractmethod
    async def switch_agent(self, name: str) -> None:
        """Switch to a different agent."""

    @abc.abstractmethod
    async def list_roles(self) -> list[RoleInfo]:
        """List all roles in the project."""

    @abc.abstractmethod
    async def list_context_versions(self) -> list[ContextInfo]:
        """List all context versions."""

    @abc.abstractmethod
    async def load_context(self, version: str) -> None:
        """Load a specific context version."""

    @abc.abstractmethod
    async def list_tasks(self) -> list[TaskInfo]:
        """List all tasks."""

    @abc.abstractmethod
    async def create_task(self, brief: str, assignees: list[str]) -> str:
        """Create a new task."""

    @abc.abstractmethod
    async def run_task(self, task_id: str) -> None:
        """Run a task."""

    @abc.abstractmethod
    async def list_workflows(self) -> list[WorkflowInfo]:
        """List all workflows."""

    @abc.abstractmethod
    async def run_workflow(self, name: str, user_prompt: str) -> None:
        """Run a workflow."""

    @abc.abstractmethod
    async def events(self) -> asyncio.Queue[Event]:
        """Async iterator over state change events."""
