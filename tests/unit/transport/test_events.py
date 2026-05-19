"""Tests for event stream transport layer.

Verifies:
- EventStream consumes events from ServiceNotifier
- Event types are correctly dispatched
- close() is callable
"""
import pytest
from datetime import datetime
from typing import Sequence

from armance.transport.events import EventStream, get_event_stream, set_event_stream
from armance.transport.dto import (
    Event,
    AgentStateChanged,
    TaskEvent,
    WorkflowEvent,
    ContextEvent,
    BudgetEvent,
    TaskStatus,
)
from armance.service.notifier import ServiceNotifier


class _MockNotifier:
    """Mock notifier that yields events from subscribe()."""

    def __init__(self, items: Sequence[Event]) -> None:
        self._items = list(items)

    async def emit(self, event: Event) -> None:
        self._items.append(event)

    async def subscribe(self):
        for item in self._items:
            yield item

    async def unsubscribe(self) -> None:
        pass


class TestEventStream:
    """Test EventStream async iterator."""

    @pytest.mark.asyncio
    async def test_stream_consumes_agent_state_events(self):
        """EventStream yields AgentStateChanged events from notifier."""
        notifier = ServiceNotifier(_MockNotifier([]))
        events: Sequence[Event] = [
            AgentStateChanged(
                timestamp=datetime.now(),
                type="agent_state_changed",
                agent_name="design_audacious",
                old_state="idle",
                new_state="working",
            ),
            AgentStateChanged(
                timestamp=datetime.now(),
                type="agent_state_changed",
                agent_name="design_audacious",
                old_state="working",
                new_state="completed",
            ),
        ]
        notifier._notifier = _MockNotifier(events)
        stream = EventStream(notifier)
        consumed = []
        async for event in stream:
            consumed.append(event)
        assert len(consumed) == 2
        assert isinstance(consumed[0], AgentStateChanged)
        assert consumed[0].agent_name == "design_audacious"
        assert consumed[0].new_state == "working"
        assert consumed[1].new_state == "completed"

    @pytest.mark.asyncio
    async def test_stream_consumes_task_events(self):
        """EventStream yields TaskEvent objects."""
        events: Sequence[Event] = [
            TaskEvent(
                timestamp=datetime.now(),
                type="task_event",
                task_id="task-1",
                task_brief="Design system",
                status=TaskStatus.WORKING,
                message="started",
            ),
        ]
        notifier = ServiceNotifier(_MockNotifier(events))
        stream = EventStream(notifier)
        consumed = []
        async for event in stream:
            consumed.append(event)
        assert len(consumed) == 1
        assert isinstance(consumed[0], TaskEvent)
        assert consumed[0].task_id == "task-1"
        assert consumed[0].status == TaskStatus.WORKING

    @pytest.mark.asyncio
    async def test_stream_consumes_workflow_events(self):
        """EventStream yields WorkflowEvent objects."""
        events: Sequence[Event] = [
            WorkflowEvent(
                timestamp=datetime.now(),
                type="workflow_event",
                workflow_name="review-pipeline",
                step_id="step-1",
                status="started",
            ),
        ]
        notifier = ServiceNotifier(_MockNotifier(events))
        stream = EventStream(notifier)
        consumed = []
        async for event in stream:
            consumed.append(event)
        assert len(consumed) == 1
        assert isinstance(consumed[0], WorkflowEvent)
        assert consumed[0].workflow_name == "review-pipeline"

    @pytest.mark.asyncio
    async def test_stream_empty_notifier(self):
        """EventStream yields nothing when notifier has no events."""
        notifier = ServiceNotifier(_MockNotifier([]))
        stream = EventStream(notifier)
        consumed = []
        async for event in stream:
            consumed.append(event)
        assert len(consumed) == 0

    @pytest.mark.asyncio
    async def test_close_is_callable(self):
        """EventStream.close() can be called without error."""
        notifier = ServiceNotifier(_MockNotifier([]))
        stream = EventStream(notifier)
        await stream.close()  # should not raise

    @pytest.mark.asyncio
    async def test_close_multiple_times(self):
        """EventStream.close() is idempotent."""
        notifier = ServiceNotifier(_MockNotifier([]))
        stream = EventStream(notifier)
        await stream.close()
        await stream.close()  # should not raise


class TestGlobalEventStream:
    """Test global event stream accessor functions."""

    def test_get_event_stream_creates_default(self):
        """get_event_stream creates a default EventStream."""
        set_event_stream(None)  # type: ignore[arg-type]
        try:
            stream = get_event_stream()
            assert isinstance(stream, EventStream)
        finally:
            set_event_stream(None)  # type: ignore[arg-type]

    def test_get_event_stream_returns_existing(self):
        """get_event_stream returns the existing stream if set."""
        notifier = ServiceNotifier()
        expected = EventStream(notifier)
        set_event_stream(expected)
        try:
            result = get_event_stream()
            assert result is expected
        finally:
            set_event_stream(None)  # type: ignore[arg-type]

    def test_set_event_stream_replaces(self):
        """set_event_stream replaces the global stream."""
        notifier1 = ServiceNotifier()
        notifier2 = ServiceNotifier()
        stream1 = EventStream(notifier1)
        stream2 = EventStream(notifier2)
        set_event_stream(stream1)
        try:
            assert get_event_stream() is stream1
            set_event_stream(stream2)
            assert get_event_stream() is stream2
        finally:
            set_event_stream(None)  # type: ignore[arg-type]


class TestDTOModels:
    """Test DTO data classes."""

    def test_agent_state_changed(self):
        """AgentStateChanged has expected fields."""
        now = datetime.now()
        event = AgentStateChanged(
            timestamp=now,
            type="agent_state_changed",
            agent_name="test_agent",
            old_state="idle",
            new_state="working",
        )
        assert event.agent_name == "test_agent"
        assert event.old_state == "idle"
        assert event.new_state == "working"
        assert event.timestamp == now

    def test_task_event(self):
        """TaskEvent has expected fields."""
        now = datetime.now()
        event = TaskEvent(
            timestamp=now,
            type="task_event",
            task_id="t-1",
            task_brief="Build something",
            status=TaskStatus.DEFINED,
            message="initial",
        )
        assert event.task_id == "t-1"
        assert event.task_brief == "Build something"
        assert event.status == TaskStatus.DEFINED
        assert event.message == "initial"

    def test_workflow_event_defaults(self):
        """WorkflowEvent has correct defaults."""
        now = datetime.now()
        event = WorkflowEvent(
            timestamp=now,
            type="workflow_event",
            workflow_name="wf-1",
        )
        assert event.step_id is None
        assert event.status == "started"
        assert event.message == ""

    def test_context_event(self):
        """ContextEvent has expected fields."""
        now = datetime.now()
        event = ContextEvent(
            timestamp=now,
            type="context_event",
            layer="L0",
            theme="project-alpha",
            action="created",
            path="/data/l0_v001.json",
        )
        assert event.layer == "L0"
        assert event.theme == "project-alpha"
        assert event.action == "created"
        assert event.path == "/data/l0_v001.json"

    def test_budget_event(self):
        """BudgetEvent has expected fields."""
        now = datetime.now()
        event = BudgetEvent(
            timestamp=now,
            type="budget_event",
            current_spent=1.50,
            budget_cap=10.0,
            warning_level="warning",
        )
        assert event.current_spent == 1.50
        assert event.budget_cap == 10.0
        assert event.warning_level == "warning"
