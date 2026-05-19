"""Tests for ArchiveAgentSkill with confirmation logic.

Covers:
- Soft archive (no confirmation needed)
- Hard archive without confirmation raises ValueError
- Hard archive with confirmation succeeds
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
from armance.service.agents.archive_agent_skill import ArchiveAgentSkill


@pytest.fixture
def temp_armance_root() -> Path:
    """Create a temporary .armance directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir) / ".armance"
        root.mkdir(parents=True, exist_ok=True)
        yield root


@pytest.fixture
def skill(temp_armance_root: Path) -> ArchiveAgentSkill:
    return ArchiveAgentSkill(armance_root=temp_armance_root)


@pytest.fixture
def sample_agent(temp_armance_root: Path) -> Agent:
    """Create and register a sample agent."""
    service = AgentLifecycleService(temp_armance_root)
    agent = Agent(
        name="historian-aisha",
        domain="historian",
        persona="positivist",
        provider="openai",
        model="gpt-4o",
        system_prompt="You are Aisha, a historian.",
    )
    service.create_agent(agent)
    return agent


class TestArchiveAgentSkill:
    """Tests for ArchiveAgentSkill.run()."""

    def test_soft_archive_success(
        self, skill: ArchiveAgentSkill, sample_agent: Agent
    ) -> None:
        """Test soft archive (no confirmation needed)."""
        result = skill.run("historian-aisha")

        assert "archived" in result

        # Verify agent is archived
        service = AgentLifecycleService(skill.armance_root)
        archived = service.list_agents(include_archived=True)
        assert len(archived) == 1
        assert archived[0].status == "archived"

    def test_hard_archive_without_confirmation_raises(
        self, skill: ArchiveAgentSkill, sample_agent: Agent
    ) -> None:
        """Test that hard archive without --confirm raises ValueError."""
        with pytest.raises(ValueError, match="Hard delete requires confirmation"):
            skill.run("historian-aisha --hard")

    def test_hard_archive_with_confirmation_succeeds(
        self, skill: ArchiveAgentSkill, sample_agent: Agent
    ) -> None:
        """Test that hard archive with --confirm succeeds."""
        result = skill.run("historian-aisha --hard --confirm")

        assert "hard-deleted" in result

        # Verify agent file is gone
        service = AgentLifecycleService(skill.armance_root)
        all_agents = service.list_agents(include_archived=True)
        # Agent should not appear (hard delete removes file)
        assert len(all_agents) == 0

    def test_no_args_returns_usage(self, skill: ArchiveAgentSkill) -> None:
        """Test calling without args returns usage."""
        result = skill.run("")
        assert "Usage" in result

    def test_nonexistent_agent_returns_error(
        self, skill: ArchiveAgentSkill
    ) -> None:
        """Test archiving non-existent agent returns error."""
        result = skill.run("ghost-agent")
        assert "Error" in result
        assert "not found" in result


class TestArchiveAgentSkillParsing:
    """Tests for argument parsing."""

    def test_parse_hard_flag(self, temp_armance_root: Path) -> None:
        """Test --hard flag is parsed."""
        skill = ArchiveAgentSkill(armance_root=temp_armance_root)
        parsed = skill._parse_args("agent-name --hard")
        assert parsed is not None
        assert parsed.name == "agent-name"
        assert parsed.hard is True
        assert parsed.confirm is False

    def test_parse_confirm_flag(self, temp_armance_root: Path) -> None:
        """Test --confirm flag is parsed."""
        skill = ArchiveAgentSkill(armance_root=temp_armance_root)
        parsed = skill._parse_args("agent-name --hard --confirm")
        assert parsed is not None
        assert parsed.name == "agent-name"
        assert parsed.hard is True
        assert parsed.confirm is True

    def test_parse_soft_archive(self, temp_armance_root: Path) -> None:
        """Test soft archive (no flags) is parsed."""
        skill = ArchiveAgentSkill(armance_root=temp_armance_root)
        parsed = skill._parse_args("agent-name")
        assert parsed is not None
        assert parsed.name == "agent-name"
        assert parsed.hard is False
