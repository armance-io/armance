"""Tests for HITLBanner widget."""
from __future__ import annotations

import pytest

from armance.client.tui.widgets.footer import HITLBanner


@pytest.mark.asyncio
async def test_hitl_banner_show_and_hide_via_pilot():
    """show_for adds .visible class; hide removes it."""
    from textual.app import App

    class T(App):
        def compose(self):
            yield HITLBanner()

    async with T().run_test() as pilot:
        banner = pilot.app.query_one(HITLBanner)
        banner.show_for("alpha")
        await pilot.pause()
        assert banner.has_class("visible")
        assert banner._agent_name == "alpha"

        banner.hide()
        await pilot.pause()
        assert not banner.has_class("visible")
        assert banner._agent_name == ""


@pytest.mark.asyncio
async def test_hitl_banner_update_agent_compat():
    """Backward-compat update_agent() routes to show_for."""
    from textual.app import App

    class T(App):
        def compose(self):
            yield HITLBanner()

    async with T().run_test() as pilot:
        banner = pilot.app.query_one(HITLBanner)
        banner.update_agent("beta")
        await pilot.pause()
        assert banner.has_class("visible")
        assert banner._agent_name == "beta"
