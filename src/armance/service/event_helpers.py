"""armance.service.event_helpers — shim (J.3).

Implementation moved to armance.platform.event_helpers.
This module re-exports everything for back-compat.
"""
from armance.platform.event_helpers import (  # noqa: F401
    SpanContext,
    current_span,
    generate_span_id,
    generate_trace_id,
    span,
)
