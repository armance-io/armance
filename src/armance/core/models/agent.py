"""Agent model: load/save markdown definitions and assemble prompts.

Agents live at .armance/agents/<name>.md as YAML frontmatter (between
"---" delimiters) followed by the system-prompt body. Worker agents
get the caveman_ultra protocol prepended to their system prompt at
runtime; user-facing agents (Context output, Judge user output) get
caveman_lite instead.
"""
from __future__ import annotations

import importlib.resources
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, Field

AgentStatus = Literal["active", "archived"]

logger = logging.getLogger(__name__)

Persona = str  # Free text — Malik picks contextual stances (e.g. positivist/revisionist, left-wing/right-wing/centrist)
CavemanLevel = Literal["ultra", "full", "none"]

ULTRA_PROTOCOL_PATH = Path("src/armance/protocols/caveman_ultra.txt")
NONE_PROTOCOL_PATH = Path("src/armance/protocols/caveman_none.txt")
FULL_PROTOCOL_PATH = Path("src/armance/protocols/caveman_full.txt")


class Agent(BaseModel):
    """Pydantic model for a specialist or staff agent.

    Supports full lifecycle operations (create, read, update, delete,
    promote, demote, archive) via the AgentLifecycleService.
    """

    name: str
    domain: str = Field(alias="domain", validation_alias="domain", serialization_alias="domain")
    role: str | None = None  # explicit role name (synched with domain)
    persona: Persona | None = None
    provider: str
    model: str
    reasoning: str | None = None
    system_prompt: str = ""
    caveman_level: CavemanLevel = "none"
    # Lifecycle fields (per 20_agent_lifecycle.md)
    status: AgentStatus = "active"
    provider_family: str | None = None  # e.g. "anthropic", "openai", "google"
    created_at: str | None = None  # ISO-8601 timestamp
    updated_at: str | None = None  # ISO-8601 timestamp
    version: int = 1
    parent_version: int | None = None
    lead_for: list[str] = Field(default_factory=list)
    description: str = ""
    created_by: str | None = None  # who/what created this agent
    # Health probe — populated by service/agents/health.py after recruit.
    # Format: "ok" or "error:<code>" (e.g. "error:429", "error:auth").
    last_health: str | None = None
    last_health_at: str | None = None  # ISO-8601

    model_config = {"populate_by_name": True}

    def __init__(self, **data: Any) -> None:
        # One-shot migration: character -> persona on input dictionary
        if "character" in data and "persona" not in data:
            data["persona"] = data.pop("character")
        # Sync role/domain on construction
        domain = data.get("domain") or data.get("role")
        if domain:
            data.setdefault("domain", domain)
            data.setdefault("role", domain)
        super().__init__(**data)

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        """Override to ensure 'role' is included alongside domain."""
        data = super().model_dump(**kwargs)
        # Keep 'role' in sync with domain if not explicitly set
        if "role" not in data and data.get("domain"):
            data["role"] = data["domain"]
        return data

    def to_dict(self) -> dict[str, Any]:
        """Serialize agent to a plain dict (JSON-safe)."""
        return self.model_dump(by_alias=True)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Agent":
        """Deserialize agent from a plain dict."""
        return cls.model_validate(data)

    def now_iso(self) -> str:
        """Return current UTC time as ISO-8601 string."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    @classmethod
    def load(cls, path: Path) -> "Agent":
        text = path.read_text(encoding="utf-8")
        frontmatter, body = _split_frontmatter(text)
        data = yaml.safe_load(frontmatter) or {}
        if "name" not in data:
            data["name"] = path.stem
        # One-shot migration of character field to persona
        if "character" in data and "persona" not in data:
            data["persona"] = data.pop("character")
            logger.warning("agent.field.migrated: Migrated legacy field 'character' to 'persona' on agent %s", data["name"])
        elif "character" in data:
            data.pop("character")
        data["system_prompt"] = body.strip()
        return cls.model_validate(data)

    @classmethod
    def from_frontmatter(cls, text: str) -> "Agent":
        frontmatter, body = _split_frontmatter(text)
        data = yaml.safe_load(frontmatter) or {}
        # One-shot migration of character field to persona
        if "character" in data and "persona" not in data:
            data["persona"] = data.pop("character")
            logger.warning("agent.field.migrated: Migrated legacy field 'character' to 'persona' on agent %s", data.get("name", "unknown"))
        elif "character" in data:
            data.pop("character")
        data["system_prompt"] = body.strip()
        return cls.model_validate(data)

    def save(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_markdown(), encoding="utf-8")
        return path

    def to_markdown(self) -> str:
        """Serialize agent to markdown format."""
        meta = self.model_dump(by_alias=True)
        body = meta.pop("system_prompt", "")
        frontmatter = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True).strip()
        return f"---\n{frontmatter}\n---\n{body}\n"

    def effective_system_prompt(
        self,
        *,
        caveman_level: CavemanLevel | None = None,
        repo_root: Path | None = None,
        protocol_path: Path | None = None,
    ) -> str:
        level = caveman_level if caveman_level is not None else self.caveman_level
        protocol_text = _load_protocol(
            level=level, repo_root=repo_root, protocol_path=protocol_path
        )
        return f"{protocol_text}\n\n{self.system_prompt}".strip()


def _split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---"):
        raise ValueError("agent file missing YAML frontmatter")
    rest = text[3:].lstrip("\n")
    end = rest.find("\n---")
    if end == -1:
        raise ValueError("agent file missing closing --- frontmatter delimiter")
    frontmatter = rest[:end]
    body = rest[end + 4 :].lstrip("\n")
    return frontmatter, body


def _load_protocol(
    *,
    level: CavemanLevel,
    repo_root: Path | None,
    protocol_path: Path | None,
) -> str:
    if protocol_path is not None:
        return protocol_path.read_text(encoding="utf-8").strip()
    filename = "caveman_full.txt" if level == "full" else "caveman_ultra.txt" if level == "ultra" else "caveman_none.txt"
    try:
        ref = importlib.resources.files("armance.protocols").joinpath(filename)
        return ref.read_text(encoding="utf-8").strip()
    except (FileNotFoundError, ModuleNotFoundError):
        pass
    # fallback: dev mode, search filesystem
    relative = ULTRA_PROTOCOL_PATH if level == "ultra" else FULL_PROTOCOL_PATH if level == "full" else NONE_PROTOCOL_PATH
    base = repo_root or Path.cwd()
    candidate = base / relative
    for parent in [base, *base.parents]:
        attempt = parent / relative
        if attempt.exists():
            candidate = attempt
            break
    return candidate.read_text(encoding="utf-8").strip()


