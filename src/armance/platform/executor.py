"""armance.platform.executor — WorkflowExecutor ABC.

V2 implementation: InProcessExecutor (see J.4).
V3 swap: CloudTasksExecutor — see issues/features/web-v3-saas-readiness.md.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

# Forward-compatible stubs for J.4 types.
# J.4 will replace these with proper dataclasses / enums.
WorkflowRunSpec = Any
RunHandle = Any
RunStatus = Any


@runtime_checkable
class WorkflowExecutor(Protocol):
    """Abstract workflow task runner.

    The in-process implementation (V2) wraps ``asyncio.create_task`` and
    stores handles in a dict keyed by run_id.

    The Cloud Tasks implementation (V3) enqueues runs on Cloud Tasks;
    Cloud Run worker instances consume them.
    """

    async def start(self, run_spec: WorkflowRunSpec) -> RunHandle:
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
