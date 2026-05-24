"""armance.platform.events — EventBus ABC.

V2 implementation: LocalEventBus (refactored from armance.service.events in J.3).
V3 swap: PubSubEventBus — see issues/features/web-v3-saas-readiness.md.

Note (J.3): when J.3 lands, LocalEventBus will be moved here and
``armance.service.events`` will become a one-line shim re-exporting it.
"""
from __future__ import annotations

from typing import AsyncIterator, Protocol, runtime_checkable


@runtime_checkable
class EventBus(Protocol):
    """Abstract ordered event stream.

    Each session owns one EventBus instance.  Publishers call ``publish``;
    consumers call ``subscribe`` to receive an async stream of event dicts.

    The local implementation (V2) uses an asyncio.Queue.
    The Pub/Sub implementation (V3) wraps a Google Pub/Sub topic keyed by
    session.
    """

    async def publish(self, event: dict) -> None:
        """Publish *event* to the bus."""
        ...

    async def subscribe(self) -> AsyncIterator[dict]:  # type: ignore[misc]
        """Return an async iterator that yields events in order."""
        ...

    async def close(self) -> None:
        """Shut down the bus and release resources."""
        ...
