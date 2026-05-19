"""SetL1Skill — /save --layer=L1 writes per-role L1 context.

Implements T-15d: L1 per-role dialogue (no RAG).
The skill is triggered by:
- Slash: `/save --layer=L1` (with explicit role or current view role)
- NL: "fige ce qu'on vient de poser sur <role>", "save L1 for <role>"

Spec refs: 05_context.md (Freezing flow, L1 sections)
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

# Natural-language patterns: "fige ce qu'on vient de poser sur X"
# or "save L1 for X" or "freeze L1 for X"
NL_PATTERNS = [
    r"fige\s+(?:ce\s+(?:qu'?on\s+vient\s+de\s+poser|le\s+contexte))\s+(?:sur|pour)\s+(.+)",
    r"save\s+(?:the\s+)?L1\s+(?:for|of)\s+(.+)",
    r"freeze\s+(?:the\s+)?L1\s+(?:for|of)\s+(.+)",
    r"fige\s+(?:la\s+)?L1\s+(?:pour|de)\s+(.+)",
]


class SetL1Skill(Skill):
    """Handles /save --layer=L1 to freeze per-role context."""

    description = "Freeze per-role dialogue as an L1 context file (context/L1/<role>/v<N>_<date>_<slug>.md)."
    input_schema = {
        "type": "object",
        "properties": {
            "role": {"type": "string", "description": "Role name for the L1 file."},
            "content": {"type": "string", "description": "Markdown body to freeze as L1."},
            "slug": {"type": "string", "description": "Short slug for the filename (optional)."},
        },
        "required": ["role", "content"],
    }
    output_schema = {"type": "string", "description": "Path of the written L1 file or error."}

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
        # Working buffer of role-specific facts
        self._buffer: list[str] = []
        # The role currently being worked on (set from view or explicit arg)
        self._current_role: str | None = None

    def set_role(self, role: str) -> None:
        """Set the current role context."""
        self._current_role = role

    def add_to_buffer(self, fact: str) -> None:
        """Add a role-specific fact to the working buffer."""
        self._buffer.append(fact)

    def run(
        self,
        args: str = "",
        ctx: dict[str, Any] | None = None,
    ) -> str:
        """Execute the L1 save operation.

        Flow:
        1. Determine role from args, ctx, or current_role
        2. Compose L1 body from buffer + prior L1 body
        3. Write v<N+1> with confirmed_by_user=true
        4. Update manifest
        """
        # Determine role
        role = self._extract_role(args, ctx)
        if not role:
            return (
                "**Cannot save L1: no role specified.**\n\n"
                "Usage: `/save --layer=L1 --role=woodworking`\n"
                "Or set the role via `/role woodworking` first."
            )

        # Compose body from buffer + prior L1
        prior_body = self.context_service.read_current_l1(role) or ""
        buffer_text = "\n".join(self._buffer).strip()

        slug = None
        if args:
            slug_match = re.search(r"--slug=(\S+)", args)
            if slug_match:
                slug = slug_match.group(1)
        if not slug:
            source = buffer_text or prior_body
            slug = _slugify(f"{role}-{source[:40]}", max_len=40)

        body_lines = []
        body_lines.append(f"# L1: {role.title()}\n")

        if prior_body:
            body_lines.append("## Previous L1 (updated)\n")
            body_lines.append(prior_body)
            body_lines.append("")
            body_lines.append("---")
            body_lines.append("")

        if buffer_text:
            body_lines.append("## Updated facts\n")
            body_lines.append(buffer_text)
            body_lines.append("")

        body = "\n".join(body_lines)

        # Write L1 with confirmed_by_user=true
        path = self.context_service.write_l1(
            role=role,
            body=body,
            slug=slug,
            confirmed_by_user=True,
        )

        # Clear buffer
        self._buffer.clear()

        return (
            f"**L1 context saved for `{role}`.**\n\n"
            f"Written to `.armance/{path.relative_to(self.armance_root)}`\n"
            f"Type `/save --layer=L1` again to freeze updates."
        )

    def _extract_role(self, args: str, ctx: dict[str, Any] | None) -> str | None:
        """Extract role from args, ctx, or current_role."""
        # Check args for --role=
        role_match = re.search(r"--role=(\S+)", args)
        if role_match:
            return role_match.group(1).lower()

        # Check args for explicit role as first word (e.g. "woodworking some text")
        stripped = args.strip()
        if stripped and not stripped.startswith("--"):
            first_word = stripped.split()[0].lower()
            # Avoid treating flags as roles
            if not first_word.startswith("-"):
                return first_word

        # Check ctx for role
        if ctx and isinstance(ctx, dict):
            role = ctx.get("role") or ctx.get("current_role")
            if role:
                return str(role).lower()

        # Fall back to current_role
        return self._current_role

    def reset_buffer(self) -> None:
        """Clear the working buffer."""
        self._buffer.clear()
