"""Conversation model for multi-turn dialogues."""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field

from armance.core.models.turn import Turn


class Conversation(BaseModel):
    """A multi-turn conversation with an agent."""

    agent: str
    turns: list[Turn] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    def append(self, role: str, content: str, agent: str | None = None) -> None:
        """Add a turn to the conversation."""
        self.turns.append(
            Turn(role=role, content=content, agent=agent or self.agent)
        )
        self.updated_at = datetime.now()

    def switch(self, new_agent: str) -> None:
        """Switch to a different agent while preserving history."""
        self.agent = new_agent
        self.updated_at = datetime.now()
