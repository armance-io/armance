"""armance.platform.executor — WorkflowExecutor ABC + InProcessExecutor.

V2 implementation: InProcessExecutor (asyncio.create_task).
V3 swap: CloudTasksExecutor — see the V3 forward-spec (internal).
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Coroutine, Protocol, runtime_checkable


@dataclass
class WorkflowRunSpec:
    """Minimal spec to start a workflow run.

    run_id must be unique within the executor's lifetime.
    payload is an open dict for workflow-specific parameters.
    """

    run_id: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunHandle:
    """Handle returned by WorkflowExecutor.start().

    task is only populated by InProcessExecutor.  Cloud-based executors
    may leave it None and use a remote run_id for tracking.
    """

    run_id: str
    task: asyncio.Task | None = None  # type: ignore[type-arg]


# Literal run status strings
RunStatus = str  # "working" | "completed" | "failed" | "cancelled" | "not_found"


@runtime_checkable
class WorkflowExecutor(Protocol):
    """Abstract workflow task runner.

    The in-process implementation (V2) wraps ``asyncio.create_task`` and
    stores handles in a dict keyed by run_id.

    The Cloud Tasks implementation (V3) enqueues runs on Cloud Tasks;
    Cloud Run worker instances consume them.
    """

    async def start(self, run_spec: WorkflowRunSpec, **kwargs: Any) -> RunHandle:
        """Schedule *run_spec* and return a handle with a ``run_id``."""
        ...

    async def cancel(self, run_id: str) -> bool:
        """Cancel the run identified by *run_id*.

        Returns ``True`` if the run was found and cancelled; ``False``
        if it was not found or had already completed.
        """
        ...

    async def status(self, run_id: str) -> RunStatus:
        """Return the current status of *run_id*."""
        ...


class InProcessExecutor:
    """V2 WorkflowExecutor that runs coroutines as asyncio Tasks.

    ``start`` wraps the provided coroutine (or a placeholder no-op) in
    ``asyncio.create_task``.  The run_id from *run_spec* is used as the
    key; callers must ensure uniqueness.
    """

    def __init__(self) -> None:
        self._handles: dict[str, RunHandle] = {}

    async def start(
        self,
        run_spec: WorkflowRunSpec,
        *,
        coro: Coroutine[Any, Any, Any] | None = None,
    ) -> RunHandle:
        """Schedule *coro* (or a no-op) under *run_spec.run_id*.

        *coro* is a test-injection point.  Production callers supply a
        coroutine produced by ``execute_workflow(run_spec.payload)``.
        """
        if coro is None:
            async def _noop() -> None:
                pass
            coro = _noop()

        task: asyncio.Task[Any] = asyncio.create_task(coro, name=run_spec.run_id)
        handle = RunHandle(run_id=run_spec.run_id, task=task)
        self._handles[run_spec.run_id] = handle
        return handle

    async def cancel(self, run_id: str) -> bool:
        """Cancel a live task.  Returns False if not found or already done."""
        handle = self._handles.get(run_id)
        if handle is None or handle.task is None:
            return False
        if handle.task.done():
            return False
        handle.task.cancel()
        return True

    async def status(self, run_id: str) -> RunStatus:
        """Return one of: working | completed | failed | cancelled | not_found."""
        handle = self._handles.get(run_id)
        if handle is None or handle.task is None:
            return "not_found"
        task = handle.task
        if not task.done():
            return "working"
        if task.cancelled():
            return "cancelled"
        if task.exception() is not None:
            return "failed"
        return "completed"
