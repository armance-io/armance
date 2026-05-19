"""Service-level notifier implementation.

This module provides a service wrapper around the notifier protocol
for emitting state change events from the service layer.
"""

from __future__ import annotations

import logging
from typing import AsyncIterator

from armance.core.protocols.notifier import Notifier, get_notifier
from armance.transport.dto import Event, AgentStateChanged, TaskEvent, WorkflowEvent

logger = logging.getLogger(__name__)


class ServiceNotifier:
    """Service-level notifier wrapper."""

    def __init__(self, notifier: Notifier | None = None) -> None:
        self._notifier = notifier or get_notifier()

    async def emit_agent_state_changed(
        self,
        agent_name: str,
        old_state: str,
        new_state: str,
    ) -> None:
        """Emit an agent state change event."""
        event = AgentStateChanged(
            timestamp=None,
            agent_name=agent_name,
            old_state=old_state,
            new_state=new_state,
        )
        await self._notifier.emit(event)

    async def emit_task_event(
        self,
        task_id: str,
        task_brief: str,
        status: str,
        message: str = "",
    ) -> None:
        """Emit a task event."""
        event = TaskEvent(
            timestamp=None,
            task_id=task_id,
            task_brief=task_brief,
            status=status,
            message=message,
        )
        await self._notifier.emit(event)

    async def emit_workflow_event(
        self,
        workflow_name: str,
        step_id: str | None,
        status: str,
        message: str = "",
    ) -> None:
        """Emit a workflow event."""
        event = WorkflowEvent(
            timestamp=None,
            workflow_name=workflow_name,
            step_id=step_id,
            status=status,
            message=message,
        )
        await self._notifier.emit(event)

    async def events(self) -> AsyncIterator[Event]:
        """Subscribe to events."""
        async for event in self._notifier.subscribe():
            yield event
