"""Tests for PromoteAgentSkill.

Covers:
- Promoting agent to lead on a topic
- Non-existent agent error handling
- Usage message on invalid args
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from armance.core.models.agent import Agent
from armance.service.agents.agent_lifecycle_service import AgentLifecycleService
from armance.service.agents.promote_agent_skill import PromoteAgentSkill


@pytest.fixture
def temp_armance_root() -> Path:
    """Create a temporary .armance directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir) / ".armance"
        root.mkdir(parents=True, exist_ok=True)
        yield root


@pytest.fixture
def skill(temp_armance_root: Path) -> PromoteAgentSkill:
    return PromoteAgentSkill(armance_root=temp_armance_root)


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
    )
    service.create_agent(agent)
    return agent


def test_promote_agent_success(skill: PromoteAgentSkill, sample_agent: Agent) -> None:
    result = skill.run("historian-aisha medieval-art")
    assert "now lead on" in result
    assert "medieval-art" in result

    # Verify updates in lifecycle service
    service = AgentLifecycleService(skill.armance_root)
    updated = service.get_agent("historian-aisha")
    assert "medieval-art" in updated.lead_for


def test_promote_agent_nonexistent(skill: PromoteAgentSkill) -> None:
    result = skill.run("nonexistent medieval-art")
    assert "Error" in result
    assert "not found" in result


def test_promote_agent_usage(skill: PromoteAgentSkill) -> None:
    result = skill.run("")
    assert "Usage" in result
