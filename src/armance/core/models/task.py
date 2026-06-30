from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
import uuid

from pydantic import BaseModel, Field

Mode = Literal["full", "light"]
TaskState = Literal[
    "submitted", "working", "input-required", "completed", "failed", "canceled"
]


class Task(BaseModel):
    """Task model — a unit of work given to an agent or meeting."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    prompt: str
    role: str
    mode: Mode = "full"
    requested_agent: str | None = None
    state: TaskState = "submitted"
    progress: float = 0.0  # 0.0 to 1.0
    error: str | None = None
    result: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)
