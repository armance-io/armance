"""Tests for EditAgentSkill.

Covers:
- Editing agent persona, model and system prompt
- Non-existent agent error handling
- Usage message on invalid args
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from armance.core.models.agent import Agent
from armance.service.agents.agent_lifecycle_service import AgentLifecycleService
from armance.service.agents.edit_agent_skill import EditAgentSkill


@pytest.fixture
def temp_armance_root() -> Path:
    """Create a temporary .armance directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir) / ".armance"
        root.mkdir(parents=True, exist_ok=True)
        yield root


@pytest.fixture
def skill(temp_armance_root: Path) -> EditAgentSkill:
    return EditAgentSkill(armance_root=temp_armance_root)


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


def test_edit_agent_success(skill: EditAgentSkill, sample_agent: Agent) -> None:
    result = skill.run("historian-aisha --persona revisionist --model claude-3-5 --system-prompt New-one")
    assert "updated" in result
    assert "revisionist" in result
    assert "claude-3-5" in result

    # Verify updates in lifecycle service
    service = AgentLifecycleService(skill.armance_root)
    updated = service.get_agent("historian-aisha")
    assert updated.persona == "revisionist"
    assert updated.model == "claude-3-5"
    assert updated.system_prompt == "New-one"


def test_edit_agent_nonexistent(skill: EditAgentSkill) -> None:
    result = skill.run("nonexistent --persona revisionist")
    assert "Error" in result
    assert "not found" in result


def test_edit_agent_usage(skill: EditAgentSkill) -> None:
    result = skill.run("")
    assert "Usage" in result
