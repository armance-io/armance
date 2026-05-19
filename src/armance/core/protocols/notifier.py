"""Notifier protocol for event streaming.

This module defines the Notifier protocol and a default in-memory
implementation for emitting state change events.
"""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator, List, Protocol

from armance.transport.dto import Event

logger = logging.getLogger(__name__)


class Notifier(Protocol):
    """Protocol for event notification."""

    async def emit(self, event: Event) -> None:
        """Emit an event to all subscribers."""
        ...

    async def subscribe(self) -> AsyncIterator[Event]:
        """Subscribe to events via async iterator."""
        ...

    async def unsubscribe(self, iterator_id: str) -> None:
        """Unsubscribe from events."""
        ...


class InMemoryNotifier:
    """In-memory notifier implementation."""

    def __init__(self) -> None:
        self._subscribers: List[asyncio.Queue[Event]] = []
        self._lock = asyncio.Lock()

    async def emit(self, event: Event) -> None:
        """Emit an event to all subscribers."""
        async with self._lock:
            for queue in self._subscribers:
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    logger.warning("Subscriber queue full, dropping event")

    async def subscribe(self) -> AsyncIterator[Event]:
        """Subscribe to events via async iterator."""
        queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=100)

        async with self._lock:
            self._subscribers.append(queue)

        try:
            while True:
                event = await queue.get()
                yield event
        finally:
            async with self._lock:
                if queue in self._subscribers:
                    self._subscribers.remove(queue)

    async def unsubscribe(self, iterator_id: str) -> None:
        """Unsubscribe from events."""
        # In a real implementation, we would track iterators by ID
        pass


# Global notifier instance
_global_notifier: InMemoryNotifier | None = None


def get_notifier() -> InMemoryNotifier:
    """Get the global notifier instance."""
    global _global_notifier
    if _global_notifier is None:
        _global_notifier = InMemoryNotifier()
    return _global_notifier


def set_notifier(notifier: InMemoryNotifier) -> None:
    """Set the global notifier instance."""
    global _global_notifier
    _global_notifier = notifier
