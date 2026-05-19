"""Tests for AgentPanel widget (logic-only, no DOM)."""
from __future__ import annotations

import pytest

from armance.client.tui.types import AgentStatus
from armance.client.tui.widgets.agent_panel import AgentPanel


@pytest.mark.asyncio
async def test_agent_panel_reactive_state():
    """Test AgentPanel reactive state update."""
    panel = AgentPanel()
    statuses = [
        AgentStatus(name="alpha", state="idle"),
        AgentStatus(name="beta", state="working"),
    ]
    panel.statuses = statuses
    panel.active_agent = "alpha"
    assert panel.statuses == statuses
    assert panel.active_agent == "alpha"


@pytest.mark.asyncio
async def test_agent_panel_update_single():
    """Test updating a single agent status."""
    panel = AgentPanel()
    panel.update_agent("alpha", "working")
    assert len(panel.statuses) == 1
    assert panel.statuses[0].name == "alpha"
    assert panel.statuses[0].state == "working"


@pytest.mark.asyncio
async def test_agent_panel_clear():
    """Test clearing all agents."""
    panel = AgentPanel()
    panel.statuses = [
        AgentStatus(name="alpha", state="idle"),
        AgentStatus(name="beta", state="idle"),
    ]
    panel.clear()
    assert panel.statuses == []
    assert panel.active_agent is None


@pytest.mark.asyncio
async def test_agent_panel_system_agents():
    """Test that system agents are tracked."""
    panel = AgentPanel()
    panel.update_all([
        AgentStatus(name="alpha", state="idle"),
        AgentStatus(name="system-context", state="idle"),
    ])
    assert len(panel.statuses) == 2


@pytest.mark.asyncio
async def test_agent_panel_active_marker():
    """Test active agent tracking."""
    panel = AgentPanel()
    panel.update_all([
        AgentStatus(name="alpha", state="idle"),
        AgentStatus(name="beta", state="idle"),
    ], active_agent="beta")
    assert panel.active_agent == "beta"
