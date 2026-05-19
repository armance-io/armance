"""Tests for InputBar widget."""
from __future__ import annotations

import pytest

from armance.client.tui.widgets.input import InputBar


@pytest.mark.asyncio
async def test_input_bar_has_submitted_message_class():
    """InputBar.Submitted message class exists."""
    assert hasattr(InputBar, "Submitted")


@pytest.mark.asyncio
async def test_input_bar_focus_method_exists():
    """focus() method exists on InputBar (no DOM needed)."""
    bar = InputBar()
    assert callable(bar.focus)


@pytest.mark.asyncio
async def test_input_bar_pilot_integration():
    """InputBar mounts and is accessible via Pilot."""
    from textual.app import App
    from armance.client.tui.widgets.input import InputBar

    class TestApp(App):
        def compose(self):
            yield InputBar()

    async with TestApp().run_test() as pilot:
        input_bar = pilot.app.query_one(InputBar)
        assert input_bar is not None


@pytest.mark.asyncio
async def test_input_bar_submit_posts_message():
    """Enter on Input triggers InputBar.Submitted with correct value."""
    from textual.app import App
    from armance.client.tui.widgets.input import InputBar, ChatInput

    received: list[str] = []

    class TestApp(App):
        def compose(self):
            yield InputBar()

        def on_input_bar_submitted(self, event: InputBar.Submitted) -> None:
            received.append(event.value)

    async with TestApp().run_test() as pilot:
        await pilot.click(ChatInput)
        
        # Inject text directly instead of pressing keys to be safe with TextArea
        input_widget = pilot.app.query_one(ChatInput)
        input_widget.text = "hello world"
        
        await pilot.press("enter")
        await pilot.pause()

    assert received == ["hello world"]


@pytest.mark.asyncio
async def test_input_bar_empty_submit_ignored():
    """Empty submit (just Enter) does not post Submitted message."""
    from textual.app import App
    from armance.client.tui.widgets.input import InputBar, ChatInput

    received: list[str] = []

    class TestApp(App):
        def compose(self):
            yield InputBar()

        def on_input_bar_submitted(self, event: InputBar.Submitted) -> None:
            received.append(event.value)

    async with TestApp().run_test() as pilot:
        await pilot.click(ChatInput)
        
        input_widget = pilot.app.query_one(ChatInput)
        input_widget.text = "   "
        
        await pilot.press("enter")
        await pilot.pause()

    assert received == []
