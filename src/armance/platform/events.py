"""armance.platform.events — EventBus ABC + LocalEventBus.

LocalEventBus moved here from armance.service.events (J.3).
armance.service.events is now a one-line shim re-exporting from here.

V2 implementation: LocalEventBus (in-process, JSONL log + asyncio.Queue).
V3 swap: PubSubEventBus — see the V3 forward-spec (internal).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Protocol, runtime_checkable

from armance.core.models.event import Event
from armance.platform.event_helpers import (
    SpanContext,
    current_span,
    generate_span_id,
    generate_trace_id,
)

logger = logging.getLogger(__name__)


@runtime_checkable
class EventBus(Protocol):
    """Protocol for all event buses in Armance.

    V2 buses use the ``emit(name, attributes=...)`` interface that carries
    OTel span context.  The publish/subscribe/close interface (the J-spec
    draft) will be added in V3 alongside the Pub/Sub backend.

    Callers use ``await bus.emit(name, attributes=...)``.
    The bus is responsible for trace propagation and persistence.
    """

    async def emit(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
        severity: str = "info",
        *,
        _span: SpanContext | None = None,
    ) -> None: ...


class LocalEventBus:
    """In-process EventBus that writes JSONL to a local log file.

    Moved from armance.service.events (J.3).  No behaviour change.
    """

    def __init__(self, log_path: Path) -> None:
        self.log_path = log_path
        self.queue: asyncio.Queue[Event] = asyncio.Queue()
        self._lock = asyncio.Lock()

    async def emit(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
        severity: str = "info",
        *,
        _span: SpanContext | None = None,
    ) -> None:
        """Emit an event.

        Span context is resolved (in order of priority):
        1. Explicit _span kwarg (for nested test scenarios).
        2. Active contextvars span (set by event_helpers.span()).
        3. Fresh IDs (top-level, unspanned call).
        """
        ctx = _span or current_span()
        if ctx is not None:
            trace_id = ctx.trace_id
            span_id = ctx.span_id
            parent_span_id = ctx.parent_span_id
        else:
            trace_id = generate_trace_id()
            span_id = generate_span_id()
            parent_span_id = None

        event = Event(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            name=name,
            timestamp=datetime.now(tz=timezone.utc),
            attributes=attributes or {},
            severity=severity,  # type: ignore[arg-type]
        )

        async with self._lock:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as fh:
                fh.write(event.model_dump_json() + "\n")

        try:
            self.queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.debug("EventBus queue full; TUI subscriber is slow")
