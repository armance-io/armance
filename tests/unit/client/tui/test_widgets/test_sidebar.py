"""Tests for Sidebar widget."""
from __future__ import annotations

import pytest

from armance.client.tui.widgets.sidebar import (
    Sidebar,
    SidebarSection,
    _SPINNER_FRAMES,
    _STATE_COLORS,
    _STATE_ICONS,
)


def test_state_icons_mapping():
    """State icons defined for canonical static states."""
    assert _STATE_ICONS["idle"] == "○"
    assert _STATE_ICONS["waiting"] == "?"
    assert _STATE_ICONS["completed"] == "✓"
    assert _STATE_ICONS["error"] == "✕"


def test_spinner_frames_present():
    """Spinner frames defined for working state animation."""
    assert len(_SPINNER_FRAMES) >= 4
    # All braille-pattern characters
    for frame in _SPINNER_FRAMES:
        assert len(frame) == 1


def test_state_colors_mapping():
    """State colors defined for all states."""
    for state in ("idle", "working", "waiting", "completed", "error"):
        assert state in _STATE_COLORS


def test_sidebar_section_construct():
    """SidebarSection accepts title + section_id (no DOM)."""
    section = SidebarSection("Roles & Agents", section_id="section-poles")
    assert section._title == "Roles & Agents"
    assert section._items == []
    assert not section._is_collapsed


def test_sidebar_section_toggle_class():
    """action_toggle flips collapsed state."""
    section = SidebarSection("Test", section_id="test-section")
    assert not section._is_collapsed
    section._is_collapsed = True
    assert section._is_collapsed


@pytest.mark.asyncio
async def test_sidebar_pilot_integration():
    """Sidebar mounts and exposes its four sections via Pilot."""
    from textual.app import App

    class T(App):
        def compose(self):
            yield Sidebar()

    async with T().run_test() as pilot:
        sidebar = pilot.app.query_one(Sidebar)
        for sid in ("section-meta", "section-roles", "section-workflows", "section-tasks"):
            sec = sidebar.query_one(f"#{sid}", SidebarSection)
            assert sec is not None


@pytest.mark.asyncio
async def test_sidebar_set_agents_renders():
    """set_agents() with a structured table renders role headers + agent rows."""
    from textual.app import App

    class T(App):
        def compose(self):
            yield Sidebar()

    async with T().run_test() as pilot:
        sidebar = pilot.app.query_one(Sidebar)
        sidebar.set_agents({
            "woodworker": [
                {"name": "Tom", "state": "working", "active": True},
                {"name": "Marie", "state": "idle", "active": False},
            ],
        })
        await pilot.pause()
        section = sidebar.query_one("#section-roles", SidebarSection)
        # 1 header + 2 agents = 3 lines
        assert len(section._items) == 3
        # The active agent line includes [reverse bold]
        active_line = next(line for line in section._items if "Tom" in line)
        assert "reverse" in active_line


@pytest.mark.asyncio
async def test_sidebar_add_agent_compat():
    """Backwards-compat add_agent populates the table."""
    from textual.app import App

    class T(App):
        def compose(self):
            yield Sidebar()

    async with T().run_test() as pilot:
        sidebar = pilot.app.query_one(Sidebar)
        sidebar.add_agent("backend", "alpha", "working", active=True)
        await pilot.pause()
        assert "backend" in sidebar._roles
        assert len(sidebar._roles["backend"]) == 1
        assert sidebar._roles["backend"][0]["name"] == "alpha"
