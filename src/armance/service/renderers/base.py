"""Common protocol and data types for all renderers.

Spec: docs/spec/22_circular_outputs.md § Render module
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass
class Deliverable:
    """A single input deliverable for the renderer."""

    content: str
    step_id: str


@dataclass
class RenderResult:
    """Outcome of a render operation."""

    output_path: Path
    bytes_written: int = 0
    pages_or_slides: int = 0
    warnings: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


@runtime_checkable
class Renderer(Protocol):
    """Common interface every renderer must satisfy."""

    format: str

    async def render(
        self,
        deliverables: list[Deliverable],
        template: Path | None,
        options: dict,
        output_path: Path,
    ) -> RenderResult: ...
