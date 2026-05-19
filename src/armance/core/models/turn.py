"""Turn model for conversations."""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


class Turn(BaseModel):
    """A single turn in a conversation."""

    role: str  # "user", "assistant", "system"
    content: str
    timestamp: datetime = datetime.now()
    agent: str | None = None
