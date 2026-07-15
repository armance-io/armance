"""Guard: there is one Event type in Armance.

The canonical Event = `armance.core.models.event.Event`. The dead
parallel system (transport.dto.Event + subclasses, transport.events,
service.notifier, core.protocols.notifier) has been removed.
"""
from __future__ import annotations


def test_transport_dto_has_no_event_dataclass():
    from armance.transport import dto

    for attr in (
        "Event",
        "AgentStateChanged",
        "TaskEvent",
        "WorkflowEvent",
        "ContextEvent",
        "BudgetEvent",
    ):
        assert not hasattr(dto, attr), (
            f"transport.dto.{attr} must be gone — use core.models.event.Event"
        )


def test_transport_events_module_is_gone():
    import importlib

    import pytest

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("armance.transport.events")


def test_service_notifier_module_is_gone():
    import importlib

    import pytest

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("armance.service.notifier")


def test_canonical_event_is_core_models_event():
    from armance.core.models.event import Event

    # Pydantic model with name / timestamp / attributes fields
    assert hasattr(Event, "model_fields")
    fields = Event.model_fields
    assert "name" in fields
    assert "timestamp" in fields
    assert "attributes" in fields


def test_local_event_bus_emits_canonical_event():
    from armance.core.models.event import Event
    from armance.service.events import LocalEventBus

    assert callable(LocalEventBus.__init__)
    # Sanity: queue type is asyncio.Queue parameterised on Event
    # (we can only check the symbol, not the runtime parameterisation)
    import armance.service.events as evmod

    assert evmod.Event is Event
