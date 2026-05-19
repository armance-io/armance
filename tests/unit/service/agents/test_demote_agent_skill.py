"""Tests for DemoteAgentSkill.

Covers:
- Demoting agent from lead on a topic
- Non-existent agent error handling
- Usage message on invalid args
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from armance.core.models.agent import Agent
from armance.service.agents.agent_lifecycle_service import AgentLifecycleService
from armance.service.agents.demote_agent_skill import DemoteAgentSkill


@pytest.fixture
def temp_armance_root() -> Path:
    """Create a temporary .armance directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir) / ".armance"
        root.mkdir(parents=True, exist_ok=True)
        yield root


@pytest.fixture
def skill(temp_armance_root: Path) -> DemoteAgentSkill:
    return DemoteAgentSkill(armance_root=temp_armance_root)


@pytest.fixture
def sample_agent(temp_armance_root: Path) -> Agent:
    service = AgentLifecycleService(temp_armance_root)
    agent = Agent(
        name="historian-aisha",
        domain="historian",
        persona="positivist",
        provider="openai",
        model="gpt-4o",
        system_prompt="Initial prompt",
        lead_for=["medieval-art"],
    )
    service.create_agent(agent)
    return agent


def test_demote_agent_success(skill: DemoteAgentSkill, sample_agent: Agent) -> None:
    # Initially is lead
    service = AgentLifecycleService(skill.armance_root)
    assert "medieval-art" in service.get_agent("historian-aisha").lead_for

    result = skill.run("historian-aisha medieval-art")
    assert "no longer lead on" in result
    assert "medieval-art" in result

    # Verify updates in lifecycle service
    updated = service.get_agent("historian-aisha")
    assert "medieval-art" not in updated.lead_for


def test_demote_agent_nonexistent(skill: DemoteAgentSkill) -> None:
    result = skill.run("nonexistent medieval-art")
    assert "Error" in result
    assert "not found" in result


def test_demote_agent_usage(skill: DemoteAgentSkill) -> None:
    result = skill.run("")
    assert "Usage" in result
