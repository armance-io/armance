"""HITLBanner: thin status bar shown only when an agent waits on the user."""
from __future__ import annotations

import logging
from typing import Any

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

logger = logging.getLogger(__name__)


class HITLBanner(Widget):
    """Human-in-the-loop alert. Hidden until ask_user fires."""

    DEFAULT_CSS = """
    HITLBanner {
        height: 0;
        background: $warning;
        color: $background;
        text-style: bold;
        padding: 0 2;
    }

    HITLBanner.visible {
        height: 1;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._agent_name: str = ""

    def compose(self) -> ComposeResult:
        yield Static("", id="hitl-text")

    def show_for(self, agent_name: str) -> None:
        self._agent_name = agent_name
        try:
            self.query_one("#hitl-text", Static).update(
                f"⚠  {agent_name} is waiting — type /switch {agent_name} to respond"
            )
        except Exception:
            pass
        self.add_class("visible")

    def hide(self) -> None:
        self._agent_name = ""
        try:
            self.query_one("#hitl-text", Static).update("")
        except Exception:
            pass
        self.remove_class("visible")

    # Backward compat
    def update_agent(self, agent_name: str) -> None:
        self.show_for(agent_name)
