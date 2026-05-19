"""OTel-shaped Event dataclass.

Spec: docs/spec/23_future_web_layer.md § Invariant 5
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# Dotted event name: at least 2 lowercase segments, e.g. "claim.appended", "context.l0.frozen".
# Segments may contain letters, digits, underscores; must start with a letter.
_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*){1,}$")
# Exactly 16 lowercase hex chars
_TRACE_ID_RE = re.compile(r"^[0-9a-f]{16}$")
# Exactly 8 lowercase hex chars
_SPAN_ID_RE = re.compile(r"^[0-9a-f]{8}$")


class Event(BaseModel):
    """OpenTelemetry-compatible event record.

    All service-emitted events must use this shape so that a future OTel
    exporter (T-32+) can forward them with zero structural changes.
    """

    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    attributes: dict[str, str | int | float | bool] = Field(default_factory=dict)
    severity: Literal["debug", "info", "warn", "error"] = "info"

    @field_validator("trace_id")
    @classmethod
    def _validate_trace_id(cls, v: str) -> str:
        if not _TRACE_ID_RE.match(v):
            raise ValueError(f"trace_id must be exactly 16 lowercase hex chars, got {v!r}")
        return v

    @field_validator("span_id")
    @classmethod
    def _validate_span_id(cls, v: str) -> str:
        if not _SPAN_ID_RE.match(v):
            raise ValueError(f"span_id must be exactly 8 lowercase hex chars, got {v!r}")
        return v

    @field_validator("parent_span_id")
    @classmethod
    def _validate_parent_span_id(cls, v: str | None) -> str | None:
        if v is not None and not _SPAN_ID_RE.match(v):
            raise ValueError(f"parent_span_id must be exactly 8 lowercase hex chars, got {v!r}")
        return v

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        if not _NAME_RE.match(v):
            raise ValueError(
                f"event name must match <component>.<action>[.<detail>] "
                f"(all lowercase, at least 2 dot-separated segments), got {v!r}"
            )
        return v

    model_config = {"frozen": True}
