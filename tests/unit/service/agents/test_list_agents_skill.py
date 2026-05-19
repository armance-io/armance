"""Tests for ListAgentsSkill.

Covers:
- Listing agents in active status
- Listing including archived agents
- Empty roster message
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from armance.core.models.agent import Agent
from armance.service.agents.agent_lifecycle_service import AgentLifecycleService
from armance.service.agents.list_agents_skill import ListAgentsSkill


@pytest.fixture
def temp_armance_root() -> Path:
    """Create a temporary .armance directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir) / ".armance"
        root.mkdir(parents=True, exist_ok=True)
        yield root


@pytest.fixture
def sample_agents(temp_armance_root: Path) -> list[Agent]:
    """Create and register two sample agents (one active, one archived)."""
    service = AgentLifecycleService(temp_armance_root)
    agent_active = Agent(
        name="historian-aisha",
        domain="historian",
        persona="positivist",
        provider="openai",
        model="gpt-4o",
        system_prompt="Aisha active",
    )
    agent_archived = Agent(
        name="historian-ben",
        domain="historian",
        persona="revisionist",
        provider="openai",
        model="gpt-4o",
        system_prompt="Ben archived",
        status="archived",
    )
    service.create_agent(agent_active)
    service.create_agent(agent_archived)
    return [agent_active, agent_archived]


def test_list_agents_active_only(temp_armance_root: Path, sample_agents: list[Agent]) -> None:
    skill = ListAgentsSkill(armance_root=temp_armance_root, include_archived=False)
    result = skill.run()
    assert "historian-aisha" in result
    assert "historian-ben" not in result
    assert "| Name | Role | Persona | Model |" in result


def test_list_agents_include_archived(temp_armance_root: Path, sample_agents: list[Agent]) -> None:
    skill = ListAgentsSkill(armance_root=temp_armance_root, include_archived=True)
    result = skill.run()
    assert "historian-aisha" in result
    assert "historian-ben" in result


def test_list_agents_empty(temp_armance_root: Path) -> None:
    skill = ListAgentsSkill(armance_root=temp_armance_root)
    result = skill.run()
    assert "No agents found" in result
