"""Service-layer checkpoint contract.

A `CheckpointHandler` is the *only* way the service layer asks the user
for input. Frontends (Textual TUI, FastAPI/web, CLI test) implement the
protocol once; handlers stay frontend-agnostic.

Three checkpoint kinds:
  - `text`   — free-form string (default).
  - `select` — pick one option from `options["choices"]`.
  - `confirm`— yes/no, returns "yes" or "no" in `content`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol


class CheckpointAbort(BaseException):
    """Raised when the user aborts a checkpoint. Aborts the whole workflow."""


CheckpointKind = Literal["text", "select", "confirm"]


@dataclass
class Checkpoint:
    id: str
    prompt: str
    kind: CheckpointKind = "text"
    options: dict[str, Any] = field(default_factory=dict)


@dataclass
class CheckpointResponse:
    content: str
    is_abort: bool = False


class CheckpointHandler(Protocol):
    async def prompt(self, checkpoint: Checkpoint) -> CheckpointResponse:
        """Prompt the user. Frontend-specific implementation."""
        ...
