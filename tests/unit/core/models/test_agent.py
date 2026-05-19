"""Tests for armance.core.models.agent.Agent."""
from __future__ import annotations
from pathlib import Path
import pytest
from armance.core.models.agent import Agent

AGENT_FILE = """---
name: alpha
domain: backend
persona: audacious
provider: openrouter
model: model-a
reasoning: high
---
You are the audacious backend agent.
Always push the envelope.
"""

def test_load_rejects_missing_domain(tmp_path: Path) -> None:
    """Files without 'domain' now fail to load — no silent migration."""
    from pydantic import ValidationError
    p = tmp_path / "legacy.md"
    p.write_text(
        "---\nname: alpha\nmétier: backend\npersona: audacious\n"
        "provider: openrouter\nmodel: model-a\n---\nLegacy file.\n",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        Agent.load(p)


def test_load_parses_frontmatter_and_body(tmp_path: Path) -> None:
    p = tmp_path / "alpha.md"
    p.write_text(AGENT_FILE, encoding="utf-8")
    agent = Agent.load(p)
    assert agent.name == "alpha"
    assert agent.domain == "backend"
    assert agent.persona == "audacious"
    assert agent.provider == "openrouter"
    assert agent.reasoning == "high"
    assert "audacious backend agent" in agent.system_prompt

def test_save_then_load_round_trip(tmp_path: Path) -> None:
    src = tmp_path / "alpha.md"
    src.write_text(AGENT_FILE, encoding="utf-8")
    a = Agent.load(src)
    out = tmp_path / "out.md"
    a.save(out)
    b = Agent.load(out)
    assert b.domain == a.domain
    assert b.persona == a.persona
    assert b.system_prompt == a.system_prompt

def test_effective_prompt_injects_ultra_protocol(tmp_path: Path) -> None:
    proto = tmp_path / "ultra.txt"
    proto.write_text("ULTRA RULES", encoding="utf-8")

    a = Agent(
        name="a", domain="m", persona="balanced",
        provider="openrouter", model="x", system_prompt="BODY",
    )
    full = a.effective_system_prompt(protocol_path=proto)
    assert full.startswith("ULTRA RULES")
    assert "BODY" in full

def test_effective_prompt_injects_none_protocol(tmp_path: Path) -> None:
    proto = tmp_path / "none.txt"
    proto.write_text("NONE", encoding="utf-8")

    a = Agent(
        name="a", domain="m", persona="balanced",
        provider="openrouter", model="x", system_prompt="BODY",
    )
    out = a.effective_system_prompt(caveman_level="none", protocol_path=proto)
    assert out.startswith("NONE")
    assert "BODY" in out

def test_load_rejects_missing_frontmatter(tmp_path: Path) -> None:
    p = tmp_path / "bad.md"
    p.write_text("no frontmatter here", encoding="utf-8")
    with pytest.raises(ValueError):
        Agent.load(p)
