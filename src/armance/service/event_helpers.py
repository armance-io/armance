"""Helpers for generating OTel-compatible IDs and managing span context.

Spec: docs/spec/23_future_web_layer.md § Invariant 5
"""
from __future__ import annotations

import secrets
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Generator


def generate_trace_id() -> str:
    """Return a 16-char lowercase hex trace ID."""
    return secrets.token_hex(8)  # 8 bytes = 16 hex chars


def generate_span_id() -> str:
    """Return an 8-char lowercase hex span ID."""
    return secrets.token_hex(4)  # 4 bytes = 8 hex chars


@dataclass
class SpanContext:
    trace_id: str
    span_id: str
    parent_span_id: str | None


# Active span context for the current asyncio task / thread
_current_span: ContextVar[SpanContext | None] = ContextVar("_current_span", default=None)


@contextmanager
def span(name: str, attributes: dict[str, Any] | None = None) -> Generator[SpanContext, None, None]:
    """Context manager that sets the active span context for the duration of the block.

    Nested spans inherit the outer trace_id; inner span's parent_span_id = outer span_id.
    """
    parent = _current_span.get()
    trace_id = parent.trace_id if parent else generate_trace_id()
    span_id = generate_span_id()
    ctx = SpanContext(
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=parent.span_id if parent else None,
    )
    token = _current_span.set(ctx)
    try:
        yield ctx
    finally:
        _current_span.reset(token)


def current_span() -> SpanContext | None:
    """Return the active span context, or None if outside any span."""
    return _current_span.get()
