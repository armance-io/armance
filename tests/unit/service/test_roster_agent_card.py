"""Tests for R-04: agent_card.json sidecar generation in RosterService.refresh()."""
from __future__ import annotations

import json
from pathlib import Path


from armance.core.models.agent import Agent
from armance.service.shared_memory_service import RosterService
from armance.storage.paths import agent_card_path


def _make_agent(agents_dir: Path, name: str, role: str, character: str = "balanced") -> None:
    agent = Agent(
        name=name,
        role=role,
        character=character,
        provider="openrouter",
        model="openai/gpt-4o-mini",
        system_prompt=f"You are {name}.",
    )
    agent.save(agents_dir / f"{name}.md")


# ---------------------------------------------------------------------------
# agent_card_path helper
# ---------------------------------------------------------------------------


def test_agent_card_path_returns_correct_path(tmp_path: Path) -> None:
    armance = tmp_path / ".armance"
    path = agent_card_path(armance, "historian-aisha")
    assert path == armance / "agents" / "historian-aisha.agent_card.json"


# ---------------------------------------------------------------------------
# RosterService.refresh() generates agent_card.json sidecars
# ---------------------------------------------------------------------------


def test_refresh_writes_agent_card_for_each_active_agent(tmp_path: Path) -> None:
    armance = tmp_path / ".armance"
    agents_dir = armance / "agents"
    agents_dir.mkdir(parents=True)
    (armance / "shared_memory").mkdir()

    _make_agent(agents_dir, "aisha", "historian")
    _make_agent(agents_dir, "luca", "finance")

    RosterService(armance).refresh()

    for name in ("aisha", "luca"):
        card_path = agent_card_path(armance, name)
        assert card_path.exists(), f"missing agent_card for {name}"
        card = json.loads(card_path.read_text(encoding="utf-8"))
        assert card["name"] == name
        assert "skills" in card
        assert isinstance(card["skills"], list)
        assert len(card["skills"]) >= 1
        assert "capabilities" in card


def test_refresh_agent_card_minimum_shape(tmp_path: Path) -> None:
    armance = tmp_path / ".armance"
    agents_dir = armance / "agents"
    agents_dir.mkdir(parents=True)
    (armance / "shared_memory").mkdir()

    _make_agent(agents_dir, "felix", "marketing", character="audacious")
    RosterService(armance).refresh()

    card = json.loads(agent_card_path(armance, "felix").read_text(encoding="utf-8"))
    assert card["version"] == "1"
    assert card["capabilities"]["streaming"] is True
    assert card["capabilities"]["push_notifications"] is False
    assert card["endpoint"] is None
    assert card["auth"] is None


def test_refresh_skips_archived_agents(tmp_path: Path) -> None:
    armance = tmp_path / ".armance"
    agents_dir = armance / "agents"
    agents_dir.mkdir(parents=True)
    (armance / "shared_memory").mkdir()

    agent = Agent(
        name="retired",
        role="finance",
        character="balanced",
        provider="openrouter",
        model="openai/gpt-4o-mini",
        system_prompt="retired agent",
        status="archived",
    )
    agent.save(agents_dir / "retired.md")
    RosterService(armance).refresh()

    assert not agent_card_path(armance, "retired").exists()


def test_refresh_generates_system_agent_cards_too(tmp_path: Path) -> None:
    armance = tmp_path / ".armance"
    agents_dir = armance / "agents"
    agents_dir.mkdir(parents=True)
    (armance / "shared_memory").mkdir()

    # system agent (system- prefix)
    sys_agent = Agent(
        name="system-host",
        role="meta",
        character="balanced",
        provider="openrouter",
        model="openai/gpt-4o-mini",
        system_prompt="You are Armance.",
    )
    sys_agent.save(agents_dir / "system-host.md")
    RosterService(armance).refresh()

    card_path = agent_card_path(armance, "system-host")
    assert card_path.exists()
