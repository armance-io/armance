"""Input bar: prompt glyph + native Textual Input with slash autocomplete."""
from __future__ import annotations

import logging

from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Static, TextArea

logger = logging.getLogger(__name__)

class ChatInput(TextArea):
    """Multiline text area that submits on Enter and inserts newlines on Shift+Enter."""
    BINDINGS = [
        Binding("enter", "submit", "Submit", priority=True),
        Binding("ctrl+j", "newline", "New line", priority=True),
        # Ctrl+Backspace = delete word. Terminals report this key under
        # several names (true `ctrl+backspace`, the readline aliases
        # `ctrl+h` / `ctrl+w`, sometimes plain `ctrl+_`). Bind all of
        # them with priority so the TextArea default (which maps
        # `ctrl+w` elsewhere) cannot win. `on_key` below catches any
        # leftover variants the binding table missed.
        Binding("ctrl+backspace", "delete_word_left", "Delete word", priority=True),
        Binding("ctrl+h", "delete_word_left", "Delete word", show=False, priority=True),
        Binding("ctrl+w", "delete_word_left", "Delete word", show=False, priority=True),
    ]

    def action_submit(self) -> None:
        text = self.text.strip()
        if text:
            self.post_message(InputBar.Submitted(text))
            self.text = ""

    def action_newline(self) -> None:
        self.insert("\n")

    def on_key(self, event) -> None:
        """Intercept multiline triggers and the various Ctrl+Backspace aliases.

        Some terminals (notably tmux + xterm-256color, and Konsole under
        certain profiles) don't report `ctrl+backspace` consistently —
        the BINDINGS table misses them. Match by key name AND character
        as a safety net.
        """
        if event.key in ("shift+enter", "ctrl+enter", "alt+enter"):
            event.prevent_default()
            event.stop()
            self.insert("\n")
            return
        if event.key in ("ctrl+backspace", "ctrl+h", "ctrl+w"):
            event.prevent_default()
            event.stop()
            self.action_delete_word_left()


class InputBar(Widget):
    """Multi-line prompt with leading `›` glyph."""

    DEFAULT_CSS = """
    InputBar {
        layout: horizontal;
        background: $panel;
        height: auto;
        max-height: 8;
        min-height: 3;
    }

    InputBar > #prompt-glyph {
        width: 4;
        height: 100%;
        content-align: center middle;
        color: $accent;
        text-style: bold;
        background: $panel;
    }

    InputBar ChatInput {
        width: 1fr;
        height: auto;
        min-height: 1;
        max-height: 8;
        background: $panel;
        color: $foreground;
        border: none;
        padding: 0 1;
    }

    InputBar ChatInput:focus {
        background: $surface;
        border: none;
    }
    """

    class Submitted(Message):
        """Posted when user submits a non-empty input."""

        def __init__(self, value: str) -> None:
            super().__init__()
            self.value = value

    def compose(self) -> ComposeResult:
        yield Static("›", id="prompt-glyph")
        yield ChatInput(id="armance-input", show_line_numbers=False)

    def on_mount(self) -> None:
        self.query_one(ChatInput).focus()

    def focus(self, scroll_visible: bool = True) -> "InputBar":  # type: ignore[override]
        self.query_one(ChatInput).focus(scroll_visible=scroll_visible)
        return self

