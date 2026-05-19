"""Tests for core/models/event.py — OTel-shaped Event dataclass."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from armance.core.models.event import Event


# ---------------------------------------------------------------------------
# Valid event names
# ---------------------------------------------------------------------------

VALID_NAMES = [
    "workflow.run.started",
    "workflow.step.completed",
    "claim.appended",
    "claim.verified",
    "agent.created",
    "context.l0.frozen",
    "render.completed",
    "rag.doc.ingested",
    "rag.query.completed",
    "workflow.manifest.migrated",
]

INVALID_NAMES = [
    "step_done",          # no dots at all
    "workflow",           # only one segment (no dot)
    "Workflow.run.done",  # uppercase
    "workflow.run.",      # trailing dot
    ".workflow.run.done", # leading dot
    "",                   # empty
]


@pytest.mark.parametrize("name", VALID_NAMES)
def test_valid_event_names(name: str) -> None:
    event = Event(
        trace_id="a" * 16,
        span_id="b" * 8,
        parent_span_id=None,
        name=name,
        timestamp=datetime.now(tz=timezone.utc),
        attributes={},
        severity="info",
    )
    assert event.name == name


@pytest.mark.parametrize("name", INVALID_NAMES)
def test_invalid_event_names_rejected(name: str) -> None:
    with pytest.raises(ValidationError):
        Event(
            trace_id="a" * 16,
            span_id="b" * 8,
            parent_span_id=None,
            name=name,
            timestamp=datetime.now(tz=timezone.utc),
            attributes={},
            severity="info",
        )


# ---------------------------------------------------------------------------
# ID format validation
# ---------------------------------------------------------------------------

def test_trace_id_must_be_16_hex_chars() -> None:
    with pytest.raises(ValidationError):
        Event(
            trace_id="tooshort",
            span_id="b" * 8,
            parent_span_id=None,
            name="workflow.run.started",
            timestamp=datetime.now(tz=timezone.utc),
            attributes={},
            severity="info",
        )


def test_span_id_must_be_8_hex_chars() -> None:
    with pytest.raises(ValidationError):
        Event(
            trace_id="a" * 16,
            span_id="toolong123",
            parent_span_id=None,
            name="workflow.run.started",
            timestamp=datetime.now(tz=timezone.utc),
            attributes={},
            severity="info",
        )


def test_non_hex_trace_id_rejected() -> None:
    with pytest.raises(ValidationError):
        Event(
            trace_id="g" * 16,  # 'g' is not hex
            span_id="b" * 8,
            parent_span_id=None,
            name="workflow.run.started",
            timestamp=datetime.now(tz=timezone.utc),
            attributes={},
            severity="info",
        )


def test_parent_span_id_can_be_none() -> None:
    event = Event(
        trace_id="a" * 16,
        span_id="b" * 8,
        parent_span_id=None,
        name="workflow.run.started",
        timestamp=datetime.now(tz=timezone.utc),
        attributes={},
        severity="info",
    )
    assert event.parent_span_id is None


def test_parent_span_id_must_be_8_hex_when_set() -> None:
    with pytest.raises(ValidationError):
        Event(
            trace_id="a" * 16,
            span_id="b" * 8,
            parent_span_id="bad",
            name="workflow.run.started",
            timestamp=datetime.now(tz=timezone.utc),
            attributes={},
            severity="info",
        )


# ---------------------------------------------------------------------------
# Attribute types
# ---------------------------------------------------------------------------

def test_attributes_accept_str_int_float_bool() -> None:
    event = Event(
        trace_id="a" * 16,
        span_id="b" * 8,
        parent_span_id=None,
        name="workflow.run.started",
        timestamp=datetime.now(tz=timezone.utc),
        attributes={"run_id": "r_abc", "step": 3, "cost": 0.05, "ok": True},
        severity="info",
    )
    assert event.attributes["run_id"] == "r_abc"
    assert event.attributes["step"] == 3


# ---------------------------------------------------------------------------
# Serialisation — must produce OTel-shaped JSON
# ---------------------------------------------------------------------------

def test_serialisation_roundtrip() -> None:
    ts = datetime(2026, 5, 12, 10, 0, 0, tzinfo=timezone.utc)
    event = Event(
        trace_id="abcd1234abcd1234",
        span_id="ef567890",
        parent_span_id=None,
        name="workflow.step.completed",
        timestamp=ts,
        attributes={"run_id": "r_test", "step_id": "judge"},
        severity="info",
    )
    data = json.loads(event.model_dump_json())
    assert data["trace_id"] == "abcd1234abcd1234"
    assert data["span_id"] == "ef567890"
    assert data["name"] == "workflow.step.completed"
    assert "2026-05-12" in data["timestamp"]
    assert data["attributes"]["run_id"] == "r_test"


def test_otel_json_schema_compliance() -> None:
    """Event JSON must contain all required OTel log record fields."""
    event = Event(
        trace_id="abcd1234abcd1234",
        span_id="ef567890",
        parent_span_id="12345678",
        name="claim.appended",
        timestamp=datetime.now(tz=timezone.utc),
        attributes={"claim_id": "c_001"},
        severity="warn",
    )
    data = json.loads(event.model_dump_json())
    required_fields = {"trace_id", "span_id", "parent_span_id", "name", "timestamp", "attributes", "severity"}
    assert required_fields <= data.keys()
