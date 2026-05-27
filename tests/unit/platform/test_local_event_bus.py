"""J.3 — LocalEventBus refactor: verify back-compat after move to platform.

Spec: issues/features/web-j-platform-abstractions.md § J.3

After J.3:
- armance.platform.events exports LocalEventBus (the implementation).
- armance.service.events becomes a one-line shim re-exporting LocalEventBus.
- All existing service/events tests continue to pass unchanged.

These tests cover the new import path from armance.platform.events.
The existing service-level tests (tests/unit/service/test_event_bus.py)
cover the shim back-compat.
"""
from __future__ import annotations

import json
import pytest
from pathlib import Path


# ---------------------------------------------------------------------------
# Import path
# ---------------------------------------------------------------------------

def test_local_event_bus_importable_from_platform() -> None:
    """LocalEventBus must be importable from armance.platform.events."""
    from armance.platform.events import LocalEventBus  # noqa: F401


def test_local_event_bus_importable_from_platform_package() -> None:
    """LocalEventBus must be re-exported from armance.platform."""
    from armance.platform import LocalEventBus  # noqa: F401


def test_service_events_shim_re_exports_local_event_bus() -> None:
    """armance.service.events must still export LocalEventBus (shim)."""
    from armance.service.events import LocalEventBus  # noqa: F401


def test_both_local_event_bus_are_same_class() -> None:
    """The class from the shim and from the platform must be identical."""
    from armance.platform.events import LocalEventBus as PlatBus
    from armance.service.events import LocalEventBus as SvcBus
    assert PlatBus is SvcBus


# ---------------------------------------------------------------------------
# Behaviour (platform import path)
# ---------------------------------------------------------------------------

def _make_bus(tmp_path: Path):
    from armance.platform.events import LocalEventBus
    log_path = tmp_path / "sessions" / "test-sid" / "events.log"
    log_path.parent.mkdir(parents=True)
    return LocalEventBus(log_path=log_path)


@pytest.mark.asyncio
async def test_platform_bus_emit_writes_jsonl(tmp_path: Path) -> None:
    bus = _make_bus(tmp_path)
    await bus.emit("platform.test.event", attributes={"k": "v"})
    lines = bus.log_path.read_text().splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["name"] == "platform.test.event"
    assert event["attributes"]["k"] == "v"


@pytest.mark.asyncio
async def test_platform_bus_emit_puts_in_queue(tmp_path: Path) -> None:
    bus = _make_bus(tmp_path)
    await bus.emit("platform.test.event", attributes={})
    event = bus.queue.get_nowait()
    assert event.name == "platform.test.event"
