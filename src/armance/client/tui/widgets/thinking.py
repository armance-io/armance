"""ThinkingIndicator: bottom spinner shown while waiting for agent response.

Mirrors the sidebar spinner glyph animation (UNI_DOTS4 / Braille frames).
Supports an optional label override (e.g. for long-running ingestion jobs).
"""
from __future__ import annotations

import logging
from typing import Any

from textual.app import ComposeResult
from textual.timer import Timer
from textual.widget import Widget
from textual.widgets import Static

logger = logging.getLogger(__name__)

# Spinner frames (same as sidebar)
_SPINNER_FRAMES = ["⠅", "⠙", "⠹", "⠸", "⠼", "⠾", "⡊", "⡋", "⡇", "⡏"]
_SPINNER_INTERVAL = 0.1  # seconds per frame


class ThinkingIndicator(Widget):
    """Thin status bar with animated spinner. Hidden by default, shown during agent work."""

    DEFAULT_CSS = """
    ThinkingIndicator {
        height: 1;
        width: 100%;
        background: $panel;
        padding: 0 2;
        opacity: 0;
        dock: bottom;
    }

    ThinkingIndicator.visible {
        opacity: 1;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._timer: Timer | None = None
        self._spinner_idx: int = 0
        self._label_override: str | None = None

    def _label(self) -> str:
        if self._label_override:
            return self._label_override
        try:
            from armance.nls import t
            return t("thinking.default")
        except Exception:
            return "Thinking..."

    def _format_line(self) -> str:
        # Do not name this _render — that name is reserved by textual.widget.Widget
        # and overriding it with a str-returning method crashes Visual.to_strips.
        return f"  [#d9b06b]{_SPINNER_FRAMES[self._spinner_idx]}[/] {self._label()}"

    def compose(self) -> ComposeResult:
        yield Static(self._format_line(), id="thinking-text")

    def on_mount(self) -> None:
        self._timer = self.set_interval(_SPINNER_INTERVAL, self._tick_spinner)

    def _tick_spinner(self) -> None:
        self._spinner_idx = (self._spinner_idx + 1) % len(_SPINNER_FRAMES)
        try:
            self.query_one("#thinking-text", Static).update(self._format_line())
        except Exception:
            pass

    def show(self, label: str | None = None) -> None:
        """Show the indicator. Optional label overrides 'Thinking…' (NLS default)."""
        self._label_override = label
        self.add_class("visible")
        self._spinner_idx = 0
        try:
            self.query_one("#thinking-text", Static).update(self._format_line())
        except Exception:
            pass

    def hide(self) -> None:
        """Hide the thinking indicator."""
        self.remove_class("visible")
        self._label_override = None
        try:
            self.query_one("#thinking-text", Static).update(self._format_line())
        except Exception:
            pass
