"""Event stream transport layer.

This module exposes an async iterator for the TUI to consume events
from the service layer.
"""

from __future__ import annotations

import logging
from typing import AsyncIterator

from armance.transport.dto import Event
from armance.service.notifier import ServiceNotifier

logger = logging.getLogger(__name__)


class EventStream:
    """Async event stream for TUI consumption."""

    def __init__(self, notifier: ServiceNotifier) -> None:
        self._notifier = notifier

    async def __aiter__(self) -> AsyncIterator[Event]:
        """Async iterator over events."""
        async for event in self._notifier.events():
            yield event

    async def close(self) -> None:
        """Close the event stream."""
        # In a real implementation, this would clean up resources
        pass


# Global event stream instance
_event_stream: EventStream | None = None


def get_event_stream(notifier: ServiceNotifier | None = None) -> EventStream:
    """Get or create the global event stream."""
    global _event_stream
    if _event_stream is None:
        _event_stream = EventStream(notifier or ServiceNotifier())
    return _event_stream


def set_event_stream(stream: EventStream) -> None:
    """Set the global event stream."""
    global _event_stream
    _event_stream = stream
