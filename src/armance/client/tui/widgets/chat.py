"""Chat view: scrolling RichLog with role-prefixed messages.

Supports custom agent labels (e.g. "Tom · woodworker", "Context · agent")
and text selection (Textual ALLOW_SELECT propagates from Screen).
"""
from __future__ import annotations

import logging
from typing import Any

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import RichLog

logger = logging.getLogger(__name__)


# role -> rich_color (warm editorial palette — never saturated, never bluish).
# The user prefix carries the rare mauve accent (a precious wink, not a base
# colour). Agent / system / error stay in the warm-ink family.
_ROLE_COLORS: dict[str, str] = {
    "user":   "#8f7e9d",
    "agent":  "#c5aa72",
    "system": "#7d7a75",
    "error":  "#c86459",
}

# Fixed colors for meta staff — muted shades of the warm family, no flash.
# Must match sidebar._META_COLORS exactly.
_META_AGENT_COLORS: dict[str, str] = {
    "armance":  "#4a3666",   # violet profond
    "malik":    "#6b4f8a",   # violet moyen
    "kim":      "#b7a4c9",   # violet doux
    "mona":     "#7a5da4",   # violet Mona
    "serge":    "#3a2b54",   # violet très sombre
}

# Default labels per role (used when no custom label given)
_DEFAULT_LABELS: dict[str, str] = {
    "user":   "you",
    "agent":  "agent",
    "system": "system",
    "error":  "error",
}


class ChatView(Widget):
    """Scrolling chat transcript with text selection enabled."""

    # Textual ≥ 0.79: enables mouse-drag text selection on this widget
    ALLOW_SELECT = True

    DEFAULT_CSS = """
    ChatView {
        background: $background;
        padding: 1 2;
    }

    ChatView RichLog {
        background: $background;
        color: $foreground;
        scrollbar-background: $background;
        scrollbar-color: $surface;
        scrollbar-color-hover: $primary;
        scrollbar-color-active: $accent;
        scrollbar-size-vertical: 1;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._log: RichLog | None = None
        # Raw markdown messages (role, label, content) for copy support
        self._messages: list[tuple[str, str, str]] = []

    def compose(self) -> ComposeResult:
        self._log = RichLog(
            highlight=False,
            markup=True,
            wrap=True,
            auto_scroll=True,
        )
        # Allow text selection on the inner RichLog (Textual ≥ 0.85)
        try:
            self._log.allow_select = True  # type: ignore[attr-defined]
        except Exception:
            pass
        yield self._log

    def append_message(
        self,
        role: str,
        content: str,
        label: str | None = None,
    ) -> None:
        """Append a role-prefixed message.

        Args:
            role: One of "user" | "agent" | "system" | "error"
            content: Message body
            label: Optional custom label (e.g. "Tom · woodworker"). If None,
                   uses _DEFAULT_LABELS[role].
        """
        if self._log is None:
            return
        color = _ROLE_COLORS.get(role, "white")
        if role == "agent" and label:
            # Check for meta staff by first name in label (before " · ")
            first = label.split(" · ")[0].lower()
            if first in _META_AGENT_COLORS:
                color = _META_AGENT_COLORS[first]
            else:
                # Specialist palette — warm desaturated tints in the same
                # family as the staff. No flashy hue lands on a name.
                colors = [
                    "#bc9392",  # rose poussière
                    "#b29267",  # ocre
                    "#94ac98",  # sauge claire
                    "#c5aa72",  # ambre passé
                    "#ba7f6a",  # terre cuite
                    "#a7a085",  # lin
                    "#9aa0a5",  # ardoise tiède
                    "#c0a18b",  # sable
                ]
                hash_val = sum(ord(c) for c in label)
                color = colors[hash_val % len(colors)]

        text_label = label if label is not None else _DEFAULT_LABELS.get(role, role)
        # Track raw markdown for copy support
        self._messages.append((role, text_label, content))
        idx = len(self._messages)

        # Message index tag (for /copy N)
        idx_tag = f" [grey50 dim]#{idx}[/]"
        prefix_lbl = f"[bold {color}]{text_label}[/]{idx_tag}"

        if role == "agent":
            from rich.markdown import Markdown
            from rich.panel import Panel

            # Clean up blockquotes from LLM that look weird
            clean_content = content.replace("\n> ", "\n=> ").replace("^> ", "=> ")
            if clean_content.startswith("> "):
                clean_content = "=> " + clean_content[2:]
                
            bubble = Panel(Markdown(clean_content), border_style=color, padding=(0, 1))
            self._log.write(prefix_lbl)
            self._log.write(bubble)
        else:
            prefix = f"{prefix_lbl} [grey39]│[/]"
            lines = content.splitlines() or [""]
            self._log.write(f"{prefix} {lines[0]}")
            # Continuation lines: align the dim separator exactly under the
            # one on the first line. The visible prefix is:
            #   <text_label><space>#<idx><space>
            # (markup like [bold ...] is invisible). Index width grows with
            # the message count, so derive it instead of hard-coding.
            visible_prefix_len = len(text_label) + 1 + 1 + len(str(idx)) + 1
            pad = " " * visible_prefix_len + "[grey39]│[/]"
            for line in lines[1:]:
                self._log.write(f"{pad} {line}")
        self._log.write("")  # spacer between turns

    def append_streaming(self, content: str) -> None:
        """Append raw content (token streaming, no prefix)."""
        if self._log is not None:
            self._log.write(content)

    def clear(self) -> None:
        if self._log is not None:
            self._log.clear()
        self._messages.clear()

    def get_message_markdown(self, idx: int) -> str | None:
        """Return the raw markdown of the Nth message (1-indexed)."""
        if idx < 1 or idx > len(self._messages):
            return None
        role, label, content = self._messages[idx - 1]
        # Frame as quoted markdown with attribution
        return f"**{label}**:\n\n{content}\n"

    def get_last_markdown(self) -> str | None:
        if not self._messages:
            return None
        return self.get_message_markdown(len(self._messages))

    def action_copy_message(self, idx: int) -> None:
        """Action triggered when the user clicks [copy] next to a message."""
        from armance.nls import t
        md = self.get_message_markdown(int(idx))
        if not md:
            try:
                self.app.notify(t("chat.copy_nothing"), severity="warning", timeout=2)
            except Exception:
                pass
            return
        try:
            self.app.copy_to_clipboard(md)
            self.app.notify(
                t("chat.copy_ok", idx=idx, chars=len(md)),
                severity="information",
                timeout=2,
            )
        except Exception as exc:
            try:
                self.app.notify(t("chat.copy_failed", error=str(exc)), severity="error", timeout=3)
            except Exception:
                logger.exception("copy_message failed")

    def get_full_transcript_markdown(self) -> str:
        """Return the entire chat as markdown."""
        out: list[str] = []
        for role, label, content in self._messages:
            out.append(f"**{label}**:\n\n{content}\n")
        return "\n---\n\n".join(out)

    # Backward compat
    def update_agent(self, agent_name: str) -> None:
        pass
