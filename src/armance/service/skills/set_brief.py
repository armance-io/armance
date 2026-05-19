"""SetBriefSkill — /save writes context/L0/v<NNN>_<date>_<slug>.md.

Implements T-15c: L0 dialogue and unified project brief.
The skill is triggered by:
- Slash: `/save` (in open-space view)
- NL: "fige le contexte", "save the brief", "fige ce contexte"

Spec refs: 05_context.md (Freezing flow), 12_implementation_plan.md (T-15c)
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


class SetBriefSkill(Skill):
    """Handles /save to freeze the active view's conversation as L0."""

    description = "Freeze the active conversation as an L0 project brief (context/L0/v<N>_<date>_<slug>.md)."
    input_schema = {
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "Markdown body to freeze as L0."},
            "slug": {"type": "string", "description": "Short slug for the filename (optional)."},
        },
        "required": ["content"],
    }
    output_schema = {"type": "string", "description": "Path of the written L0 file or error."}

    slash = "/save"
    nl_patterns = [
        r"fige\s+(le\s+)?contexte",
        r"save\s+(the\s+)?brief",
        r"fige\s+ce\s+contexte",
        r"freeze\s+(the\s+)?brief",
    ]
    triggered_by = "user"  # user-initiated, not agent

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
        # Working buffer of project facts accumulated by Armance
        self._buffer: list[str] = []

    def add_to_buffer(self, fact: str) -> None:
        """Add a project fact to the working buffer."""
        self._buffer.append(fact)

    def run(
        self,
        args: str = "",
        ctx: dict[str, Any] | None = None,
    ) -> str:
        """Execute the save operation.

        Dialog flow:
        1. Collect buffer + prior L0 body
        2. Compose new L0 body (Goal, Constraints, Decisions, Open questions)
        3. Write v<N+1> with confirmed_by_user=true
        4. Update manifest
        """
        # Migrate legacy project_brief.md if present
        migrated = self.context_service.migrate_legacy_project_brief()
        if migrated:
            self.on_token(f"[Migrated legacy project_brief.md → {migrated.name}]\n")

        # Compose body from buffer + prior L0
        prior_body = self.context_service.read_l0_body() or ""
        buffer_text = "\n".join(self._buffer).strip()

        # Extract slug from args or derive from content
        slug = None
        if args.strip():
            slug = _slugify(args.strip(), max_len=40)
        else:
            # Derive from first meaningful line of buffer or prior body
            source = buffer_text or prior_body
            slug = _slugify(source[:80])

        # Compose the L0 body
        body_lines = []

        # Always include the L0 header
        body_lines.append("## L0")
        body_lines.append("")

        if prior_body:
            body_lines.append(
                "### Previous context (updated)\n"
            )
            body_lines.append(prior_body)
            body_lines.append("")
            body_lines.append("---")
            body_lines.append("")

        if buffer_text:
            body_lines.append(
                "### Updated facts\n"
            )
            body_lines.append(buffer_text)
            body_lines.append("")

        # Ensure at least a Goal section so the file is never frontmatter-only
        body_text = "\n".join(body_lines)
        if not re.search(r"^###\s+Goal", body_text, re.MULTILINE):
            goal_text = buffer_text[:200] if buffer_text else "Project context to be defined."
            body_lines.insert(2, f"### Goal\n{goal_text}")

        body = "\n".join(body_lines)

        # Write L0 with confirmed_by_user=true (user typed /save)
        path = self.context_service.write_l0(
            body=body,
            slug=slug,
            confirmed_by_user=True,
        )

        # Clear buffer
        self._buffer.clear()

        return (
            f"**Context saved.**\n\n"
            f"Written to `.armance/{path.relative_to(self.armance_root)}`\n"
            f"Type `/save` again to freeze updates."
        )

    def reset_buffer(self) -> None:
        """Clear the working buffer."""
        self._buffer.clear()
