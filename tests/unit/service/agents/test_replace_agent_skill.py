"""Tests for ReplaceAgentSkill.

Covers:
- Successful replacement (archives old, creates new)
- Error handling for non-existent agents
- Argument parsing
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from armance.core.models.agent import Agent
from armance.service.agents.agent_lifecycle_service import (
    AgentLifecycleService,
    AgentNotFoundError,
)
from armance.service.agents.replace_agent_skill import ReplaceAgentSkill


@pytest.fixture
def temp_armance_root() -> Path:
    """Create a temporary .armance directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir) / ".armance"
        root.mkdir(parents=True, exist_ok=True)
        yield root


@pytest.fixture
def skill(temp_armance_root: Path) -> ReplaceAgentSkill:
    return ReplaceAgentSkill(armance_root=temp_armance_root)


@pytest.fixture
def sample_agent(temp_armance_root: Path) -> Agent:
    """Create and register a sample agent."""
    service = AgentLifecycleService(temp_armance_root)
    agent = Agent(
        name="historian-aisha",
        role="historian",
        persona="positivist",
        provider="openai",
        model="gpt-4o",
        system_prompt="You are Aisha, a historian.",
    )
    service.create_agent(agent)
    return agent


class TestReplaceAgentSkill:
    """Tests for ReplaceAgentSkill.run()."""

    def test_replace_success(self, skill: ReplaceAgentSkill, sample_agent: Agent) -> None:
        """Test successful agent replacement."""
        result = skill.run("historian-aisha with revisionist")

        assert "historian-aisha" in result
        assert "archived" in result
        assert "revisionist" in result

        # Verify old agent is archived
        service = AgentLifecycleService(skill.armance_root)
        archived = service.list_agents(include_archived=True)
        names = {a.name for a in archived}
        assert "historian-aisha" in names

        # Verify new agent exists and is active
        active = service.list_agents()
        assert len(active) == 1
        assert active[0].role == "historian"
        assert active[0].persona == "revisionist"

    def test_replace_nonexistent_agent(self, skill: ReplaceAgentSkill) -> None:
        """Test replacing a non-existent agent returns error."""
        result = skill.run("nonexistent with persona")
        assert "Error" in result
        assert "not found" in result

    def test_replace_no_args(self, skill: ReplaceAgentSkill) -> None:
        """Test calling without args returns usage."""
        result = skill.run("")
        assert "Usage" in result

    def test_replace_missing_persona(self, skill: ReplaceAgentSkill) -> None:
        """Test calling with only old_name returns usage."""
        result = skill.run("historian-aisha")
        assert "Usage" in result


class TestReplaceAgentService:
    """Tests for AgentLifecycleService.replace_agent()."""

    def test_replace_agent_creates_new_with_same_role(
        self, temp_armance_root: Path, sample_agent: Agent
    ) -> None:
        """Test that replacement preserves role/domain."""
        service = AgentLifecycleService(temp_armance_root)
        old_name, new_agent = service.replace_agent("historian-aisha", "revisionist")

        assert old_name == "historian-aisha"
        assert new_agent.role == "historian"
        assert new_agent.persona == "revisionist"
        # New agent should have a different name
        assert new_agent.name != "historian-aisha"

    def test_replace_agent_preserves_provider(
        self, temp_armance_root: Path, sample_agent: Agent
    ) -> None:
        """Test that replacement preserves provider and model."""
        service = AgentLifecycleService(temp_armance_root)
        _, new_agent = service.replace_agent("historian-aisha", "new")

        assert new_agent.provider == "openai"
        assert new_agent.model == "gpt-4o"

    def test_replace_nonexistent_raises(self, temp_armance_root: Path) -> None:
        """Test replacing non-existent agent raises AgentNotFoundError."""
        service = AgentLifecycleService(temp_armance_root)
        with pytest.raises(AgentNotFoundError, match="not found"):
            service.replace_agent("ghost-agent", "persona")

    def test_replace_archives_old_agent(
        self, temp_armance_root: Path, sample_agent: Agent
    ) -> None:
        """Test that the old agent is archived (not hard-deleted)."""
        service = AgentLifecycleService(temp_armance_root)
        service.replace_agent("historian-aisha", "new")

        # Old agent should be in archived list
        archived = service.list_agents(include_archived=True)
        archived_names = [a.name for a in archived if a.status == "archived"]
        assert "historian-aisha" in archived_names

        # Only one active agent (the new one)
        active = service.list_agents()
        assert len(active) == 1
