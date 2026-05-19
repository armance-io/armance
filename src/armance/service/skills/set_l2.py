"""SetL2Skill — /save --layer=L2 writes topic-specific L2 context.

Spec refs: 05_context.md
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Callable

from armance.core.models.context import _slugify
from armance.service.context_service import ContextService
from armance.service.skills.base import Skill

logger = logging.getLogger(__name__)

NL_PATTERNS = [
    r"fige\s+le\s+savoir\s+sur\s+(.+)",
    r"save\s+L2\s+for\s+(.+)",
    r"freeze\s+topic\s+(.+)",
]


class SetL2Skill(Skill):
    """Handles /save --layer=L2 to freeze topic-specific knowledge."""

    description = "Freeze topic-specific knowledge as an L2 context file (context/L2/<theme>/v<N>_<date>_<slug>.md)."
    input_schema = {
        "type": "object",
        "properties": {
            "theme": {"type": "string", "description": "Theme/Topic name (e.g. 'sqlite-vec')."},
            "content": {"type": "string", "description": "Markdown body to freeze as L2."},
            "slug": {"type": "string", "description": "Short slug for the filename (optional)."},
        },
        "required": ["theme", "content"],
    }
    output_schema = {"type": "string", "description": "Path of the written L2 file or error."}

    slash = "/save"
    nl_patterns = NL_PATTERNS
    triggered_by = "user"

    def __init__(
        self,
        armance_root: Path,
        config: Any,
        on_token: Callable[[str], None] | None = None,
    ) -> None:
        self.armance_root = armance_root
        self.config = config
        self.on_token = on_token or (lambda t: None)
        self.context_service = ContextService(armance_root)
        # Working buffer of topic-specific facts
        self._buffer: list[str] = []
        # The theme currently being worked on
        self._current_theme: str | None = None

    def set_theme(self, theme: str) -> None:
        """Set the current theme context."""
        self._current_theme = theme

    def add_to_buffer(self, fact: str) -> None:
        """Add a topic-specific fact to the working buffer."""
        self._buffer.append(fact)

    def run(
        self,
        args: str = "",
        ctx: dict[str, Any] | None = None,
    ) -> str:
        """Execute the L2 save operation."""
        # Determine theme
        theme = self._extract_theme(args, ctx)
        if not theme:
            return (
                "**Cannot save L2: no theme specified.**\n\n"
                "Usage: `/save --layer=L2 --theme=sqlite-vec`"
            )

        # Compose body from buffer + prior L2
        prior_body = self.context_service.read_current_l2(theme) or ""
        buffer_text = "\n".join(self._buffer).strip()

        slug = None
        if args:
            slug_match = re.search(r"--slug=(\S+)", args)
            if slug_match:
                slug = slug_match.group(1)
        if not slug:
            source = buffer_text or prior_body
            slug = _slugify(f"{theme}-{source[:40]}", max_len=40)

        body_lines = []
        body_lines.append(f"# L2: {theme.title()}\n")

        if prior_body:
            body_lines.append("## Prior Knowledge (updated)\n")
            body_lines.append(prior_body)
            body_lines.append("")
            body_lines.append("---")
            body_lines.append("")

        if buffer_text:
            body_lines.append("## New Knowledge\n")
            body_lines.append(buffer_text)
            body_lines.append("")

        body = "\n".join(body_lines)

        # Write L2 with confirmed_by_user=true
        path = self.context_service.write_l2(
            theme=theme,
            body=body,
            slug=slug,
            confirmed_by_user=True,
        )

        # Clear buffer
        self._buffer.clear()

        return (
            f"**L2 context saved for theme `{theme}`.**\n\n"
            f"Written to `.armance/{path.relative_to(self.armance_root)}`"
        )

    def _extract_theme(self, args: str, ctx: dict[str, Any] | None) -> str | None:
        """Extract theme from args, ctx, or current_theme."""
        # Check args for --theme=
        theme_match = re.search(r"--theme=(\S+)", args)
        if theme_match:
            return theme_match.group(1).lower()

        # Check ctx for domain/theme
        if ctx and isinstance(ctx, dict):
            theme = ctx.get("theme") or ctx.get("domain")
            if theme:
                return str(theme).lower()

        # Fall back to current_theme
        return self._current_theme

    def reset_buffer(self) -> None:
        """Clear the working buffer."""
        self._buffer.clear()
