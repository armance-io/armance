"""Markdown renderer — passthrough / concatenation.

Spec: docs/spec/22_circular_outputs.md § Supported formats (md)
"""
from __future__ import annotations

from pathlib import Path

from .base import Deliverable, RenderResult


class MdRenderer:
    """Concatenates deliverables into a single markdown file."""

    format = "md"

    async def render(
        self,
        deliverables: list[Deliverable],
        template: Path | None,
        options: dict,
        output_path: Path,
    ) -> RenderResult:
        separator = options.get("separator", "\n\n---\n\n")
        content = separator.join(d.content for d in deliverables)

        if template and template.exists():
            tpl = template.read_text(encoding="utf-8")
            content = tpl.replace("{{content}}", content)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        return RenderResult(
            output_path=output_path,
            bytes_written=len(content.encode()),
            pages_or_slides=1,
        )
