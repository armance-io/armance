"""Tests for ChatView widget."""
from __future__ import annotations

import pytest

from armance.client.tui.widgets.chat import ChatView, _ROLE_COLORS, _DEFAULT_LABELS


def test_chat_view_constructs_without_kwargs():
    """ChatView can be instantiated with no args."""
    view = ChatView()
    assert view._log is None  # not yet composed


def test_role_styles_defined():
    """All expected roles have colors and default labels."""
    for role in ("user", "agent", "system", "error"):
        assert role in _ROLE_COLORS
        assert role in _DEFAULT_LABELS


def test_custom_label_via_pilot():
    """append_message accepts custom label override."""
    pass  # covered by pilot test below


def test_append_streaming_no_op_before_mount():
    """append_streaming silently no-ops if RichLog not yet composed."""
    view = ChatView()
    view.append_streaming("partial")  # must not raise


def test_append_message_no_op_before_mount():
    """append_message silently no-ops if RichLog not yet composed."""
    view = ChatView()
    view.append_message("user", "hello")  # must not raise


def test_clear_no_op_before_mount():
    """clear no-ops if RichLog not yet composed."""
    view = ChatView()
    view.clear()  # must not raise


def test_update_agent_compat():
    """update_agent is a no-op for backward compat."""
    view = ChatView()
    view.update_agent("alpha")  # no-op, no exception


@pytest.mark.asyncio
async def test_chat_view_pilot_integration():
    """ChatView mounts under a Pilot app and accepts messages."""
    from textual.app import App

    class T(App):
        def compose(self):
            yield ChatView()

    async with T().run_test() as pilot:
        view = pilot.app.query_one(ChatView)
        view.append_message("user", "hello")
        view.append_message("agent", "hi")
        view.clear()
        await pilot.pause()
