"""Agent panel widget for Armance TUI.

Replaces render_agent_panel() from tui.py.
Shows a list of agents with their status, tokens, and cost.
"""
from __future__ import annotations

import logging
from typing import Any

from textual.containers import Container
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from armance.client.tui.types import AgentStatus

logger = logging.getLogger(__name__)

# State display configuration
STATE_STYLES: dict[str, dict[str, str]] = {
    "idle": {"color": "$text-muted", "icon": "○"},
    "working": {"color": "$warning", "icon": "◉"},
    "completed": {"color": "$success", "icon": "✓"},
    "error": {"color": "$error", "icon": "✗"},
    "waiting": {"color": "$accent", "icon": "🔔"},
}

ACTIVE_MARKER = " ▶"


class AgentRow(Static):
    """A single agent row in the AgentPanel."""
    
    DEFAULT_CSS = """
    AgentRow {
        height: 1;
        layout: horizontal;
        padding: 0 1;
    }
    
    AgentRow > #agent-name {
        width: 20;
        text-style: bold;
    }
    
    AgentRow > #agent-state {
        width: 15;
    }
    
    AgentRow > #agent-tokens-in {
        width: 8;
        text-align: right;
    }
    
    AgentRow > #agent-tokens-out {
        width: 8;
        text-align: right;
    }
    
    AgentRow > #agent-cost {
        width: 10;
        text-align: right;
    }
    """
    
    def __init__(self, agent: AgentStatus, is_active: bool = False) -> None:
        super().__init__()
        self.agent = agent
        self.is_active = is_active
        
    def compose(self) -> Any:
        state_info = STATE_STYLES.get(self.agent.state, STATE_STYLES["idle"])
        icon = state_info["icon"]
        color = state_info["color"]
        
        name = self.agent.name
        if self.is_active:
            name += ACTIVE_MARKER
            
        yield Static(
            f"[{color}]{name}[/]",
            id="agent-name"
        )
        yield Static(
            f"[{color}]{icon} {self.agent.state}[/]",
            id="agent-state"
        )
        yield Static(str(self.agent.tokens_in), id="agent-tokens-in")
        yield Static(str(self.agent.tokens_out), id="agent-tokens-out")
        yield Static(f"{self.agent.cost_usd:.4f}", id="agent-cost")
        
    def update(self, agent: AgentStatus, is_active: bool = False) -> None:
        """Update the row with new agent data."""
        self.agent = agent
        self.is_active = is_active
        self.refresh()


class AgentPanel(Widget):
    """Panel showing all agents with their status, tokens, and cost.
    
    Replaces the Rich Table-based render_agent_panel() function.
    """
    
    DEFAULT_CSS = """
    AgentPanel {
        dock: right;
        width: 42;
        border: solid $primary;
        background: $surface;
    }
    
    AgentPanel > #title {
        height: 1;
        text-align: center;
        text-style: bold;
        color: $accent;
    }
    
    AgentPanel > #header-row {
        height: 1;
        color: $text-muted;
        text-style: italic;
    }
    
    AgentPanel > #agents-list {
        height: 1fr;
    }
    """
    
    statuses: reactive[list[AgentStatus]] = reactive([])
    active_agent: reactive[str | None] = reactive(None)
    
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._agent_rows: dict[str, AgentRow] = {}
        
    def compose(self) -> Any:
        yield Static("Agents", id="title")
        yield Static("agent        state       in      out     $", id="header-row")
        with Container(id="agents-list"):
            pass
            
    def update_agent(self, agent_name: str, state: str) -> None:
        """Update a single agent's status.
        
        Args:
            agent_name: Name of the agent
            state: New state (idle, working, done, error, waiting)
        """
        for s in self.statuses:
            if s.name == agent_name:
                s.state = state
                break
        else:
            self.statuses.append(AgentStatus(name=agent_name, state=state))
        self._update_rows()
        
    def update_all(self, statuses: list[AgentStatus], active_agent: str | None = None) -> None:
        """Update all agent statuses.
        
        Args:
            statuses: List of all agent statuses
            active_agent: Name of the active agent
        """
        self.statuses = statuses
        self.active_agent = active_agent
        self._update_rows()
        
    def _update_rows(self) -> None:
        """Update the agent rows display."""
        # Guard: skip if not mounted yet
        try:
            agents_list = self.query_one("#agents-list", Container)
        except Exception:
            return
        
        # Remove old rows
        for row in self._agent_rows.values():
            row.remove()
        self._agent_rows.clear()
        
        # Separate user agents from system agents
        system_prefixes = ("system-",)
        user_agents = []
        system_agents = []
        
        for status in self.statuses:
            if status.name.startswith(system_prefixes):
                system_agents.append(status)
            else:
                user_agents.append(status)
        
        # Create rows for user agents
        for status in user_agents:
            row = AgentRow(status, is_active=status.name == self.active_agent)
            agents_list.mount(row)
            self._agent_rows[status.name] = row
            
        # Add separator if system agents exist
        if system_agents:
            separator = Static("────────────────────────────────────────", id="separator")
            agents_list.mount(separator)
            system_header = Static("[dim]system[/]", id="system-header")
            agents_list.mount(system_header)
            
        # Create rows for system agents
        for status in system_agents:
            row = AgentRow(status, is_active=status.name == self.active_agent)
            agents_list.mount(row)
            self._agent_rows[status.name] = row
            
        self.refresh()
        
    def clear(self) -> None:
        """Clear all agent rows."""
        self.statuses = []
        self.active_agent = None
        self._update_rows()
