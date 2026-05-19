"""Role model — a domain/group of agents."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

class Role(BaseModel):
    """A role (domain group) containing related agents."""

    name: str
    description: str = ""
    agents: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    @classmethod
    def from_frontmatter(cls, text: str) -> "Role":
        """Load Role from YAML frontmatter."""
        import yaml
        from armance.core.models.agent import _split_frontmatter

        frontmatter, _ = _split_frontmatter(text)
        data = yaml.safe_load(frontmatter) or {}
        return cls.model_validate(data)

    def to_frontmatter(self) -> str:
        """Export Role to YAML frontmatter."""
        import yaml

        data = self.model_dump()
        # Convert datetimes to ISO strings for YAML
        data["created_at"] = self.created_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        return yaml.safe_dump(data, sort_keys=False, allow_unicode=True).strip()
