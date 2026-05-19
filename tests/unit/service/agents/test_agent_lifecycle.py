"""Tests for AgentLifecycleService CRUD operations.

Covers:
- create_agent: success, duplicate name, missing fields
- get_agent: found, not found
- list_agents: empty, with agents, archived filter
- update_agent: in-place, versioned, not found
- promote_agent / demote_agent: success, not found
- archive_agent: soft, hard, not found
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from armance.core.models.agent import Agent
from armance.service.agents.agent_lifecycle_service import (
    AgentLifecycleError,
    AgentLifecycleService,
    AgentNotFoundError,
    DuplicateAgentError,
)


@pytest.fixture
def temp_armance_root() -> Path:
    """Create a temporary .armance directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir) / ".armance"
        root.mkdir(parents=True, exist_ok=True)
        yield root


@pytest.fixture
def sample_agent() -> Agent:
    """Create a sample agent for testing."""
    return Agent(
        name="historian-aisha",
        domain="historian",
        persona="positivist",
        provider="openai",
        model="gpt-4o",
        system_prompt="You are Aisha, a historian.",
    )


class TestCreateAgent:
    """Tests for create_agent method."""

    def test_create_agent_success(self, temp_armance_root: Path, sample_agent: Agent) -> None:
        """Test successful agent creation."""
        service = AgentLifecycleService(temp_armance_root)
        service.create_agent(sample_agent)

        # Agent file should exist
        agent_file = temp_armance_root / "agents" / "historian-aisha.md"
        assert agent_file.exists()

        # Registry should have entry
        registry_file = temp_armance_root / "agents" / "registry.json"
        assert registry_file.exists()
        registry = json.loads(registry_file.read_text())
        assert len(registry["agents"]) == 1
        assert registry["agents"][0]["name"] == "historian-aisha"
        assert registry["agents"][0]["status"] == "active"

    def test_create_agent_duplicate(self, temp_armance_root: Path, sample_agent: Agent) -> None:
        """Test duplicate agent name raises error."""
        service = AgentLifecycleService(temp_armance_root)
        service.create_agent(sample_agent)

        with pytest.raises(DuplicateAgentError, match="already exists"):
            service.create_agent(sample_agent)

    def test_create_agent_missing_name(self, temp_armance_root: Path) -> None:
        """Test agent without name raises ValueError."""
        agent = Agent(
            name="",
            domain="historian",
            persona="positivist",
            provider="openai",
            model="gpt-4o",
        )
        service = AgentLifecycleService(temp_armance_root)
        with pytest.raises(ValueError, match="name is required"):
            service.create_agent(agent)

    def test_create_agent_missing_domain(self, temp_armance_root: Path, sample_agent: Agent) -> None:
        """Test agent without domain raises ValueError."""
        sample_agent.domain = ""
        service = AgentLifecycleService(temp_armance_root)
        with pytest.raises(ValueError, match="domain is required"):
            service.create_agent(sample_agent)

    def test_create_agent_sets_timestamps(self, temp_armance_root: Path, sample_agent: Agent) -> None:
        """Test that created_at and updated_at are set on creation."""
        service = AgentLifecycleService(temp_armance_root)
        service.create_agent(sample_agent)

        loaded = service.get_agent("historian-aisha")
        assert loaded is not None
        assert loaded.created_at is not None
        assert loaded.updated_at is not None


class TestGetAgent:
    """Tests for get_agent method."""

    def test_get_agent_found(self, temp_armance_root: Path, sample_agent: Agent) -> None:
        """Test getting an existing agent."""
        service = AgentLifecycleService(temp_armance_root)
        service.create_agent(sample_agent)

        agent = service.get_agent("historian-aisha")
        assert agent is not None
        assert agent.name == "historian-aisha"
        assert agent.persona == "positivist"

    def test_get_agent_not_found(self, temp_armance_root: Path) -> None:
        """Test getting a non-existent agent returns None."""
        service = AgentLifecycleService(temp_armance_root)
        agent = service.get_agent("nonexistent")
        assert agent is None


class TestListAgents:
    """Tests for list_agents method."""

    def test_list_agents_empty(self, temp_armance_root: Path) -> None:
        """Test listing agents when none exist."""
        service = AgentLifecycleService(temp_armance_root)
        agents = service.list_agents()
        assert agents == []

    def test_list_agents_with_agents(self, temp_armance_root: Path) -> None:
        """Test listing multiple agents."""
        service = AgentLifecycleService(temp_armance_root)
        service.create_agent(Agent(
            name="historian-aisha",
            domain="historian",
            persona="positivist",
            provider="openai",
            model="gpt-4o",
        ))
        service.create_agent(Agent(
            name="designer-kojo",
            domain="designer",
            persona="minimalist",
            provider="anthropic",
            model="claude-3.5-sonnet",
        ))

        agents = service.list_agents()
        assert len(agents) == 2
        names = {a.name for a in agents}
        assert "historian-aisha" in names
        assert "designer-kojo" in names

    def test_list_agents_excludes_archived_by_default(self, temp_armance_root: Path) -> None:
        """Test that archived agents are excluded by default."""
        service = AgentLifecycleService(temp_armance_root)
        service.create_agent(Agent(
            name="historian-aisha",
            domain="historian",
            persona="positivist",
            provider="openai",
            model="gpt-4o",
        ))
        service.archive_agent("historian-aisha")

        agents = service.list_agents()
        assert len(agents) == 0

    def test_list_agents_includes_archived_when_requested(self, temp_armance_root: Path) -> None:
        """Test that archived agents are included when include_archived=True."""
        service = AgentLifecycleService(temp_armance_root)
        service.create_agent(Agent(
            name="historian-aisha",
            domain="historian",
            persona="positivist",
            provider="openai",
            model="gpt-4o",
        ))
        service.archive_agent("historian-aisha")

        agents = service.list_agents(include_archived=True)
        assert len(agents) == 1
        assert agents[0].name == "historian-aisha"


class TestUpdateAgent:
    """Tests for update_agent method."""

    def test_update_agent_in_place(self, temp_armance_root: Path, sample_agent: Agent) -> None:
        """Test in-place update (no version bump for new agent)."""
        service = AgentLifecycleService(temp_armance_root)
        service.create_agent(sample_agent)

        updated = service.update_agent("historian-aisha", persona="revisionist")
        assert updated.persona == "revisionist"
        assert updated.version == 1  # No version bump for in-place

    def test_update_agent_versioned(self, temp_armance_root: Path, sample_agent: Agent) -> None:
        """Test versioned update (force_version=True)."""
        service = AgentLifecycleService(temp_armance_root)
        service.create_agent(sample_agent)

        updated = service.update_agent(
            "historian-aisha",
            persona="cultural",
            force_version=True,
        )
        assert updated.persona == "cultural"
        assert updated.version == 2
        assert updated.parent_version == 1

    def test_update_agent_model(self, temp_armance_root: Path, sample_agent: Agent) -> None:
        """Test updating the model."""
        service = AgentLifecycleService(temp_armance_root)
        service.create_agent(sample_agent)

        updated = service.update_agent("historian-aisha", model="gpt-4o-mini")
        assert updated.model == "gpt-4o-mini"

    def test_update_agent_not_found(self, temp_armance_root: Path) -> None:
        """Test updating a non-existent agent raises error."""
        service = AgentLifecycleService(temp_armance_root)
        with pytest.raises(AgentNotFoundError, match="not found"):
            service.update_agent("nonexistent", persona="test")

    def test_update_agent_system_prompt(self, temp_armance_root: Path, sample_agent: Agent) -> None:
        """Test updating the system prompt."""
        service = AgentLifecycleService(temp_armance_root)
        service.create_agent(sample_agent)

        updated = service.update_agent(
            "historian-aisha",
            system_prompt="New system prompt",
        )
        assert updated.system_prompt == "New system prompt"


class TestPromoteDemoteAgent:
    """Tests for promote_agent and demote_agent methods."""

    def test_promote_agent(self, temp_armance_root: Path, sample_agent: Agent) -> None:
        """Test promoting an agent to lead on a topic."""
        service = AgentLifecycleService(temp_armance_root)
        service.create_agent(sample_agent)

        updated = service.promote_agent("historian-aisha", "textiles")
        assert "textiles" in updated.lead_for

    def test_promote_agent_already_lead(self, temp_armance_root: Path, sample_agent: Agent) -> None:
        """Test promoting an agent who is already lead (idempotent)."""
        service = AgentLifecycleService(temp_armance_root)
        service.create_agent(sample_agent)
        service.promote_agent("historian-aisha", "textiles")

        updated = service.promote_agent("historian-aisha", "textiles")
        assert updated.lead_for.count("textiles") == 1  # No duplicates

    def test_promote_agent_not_found(self, temp_armance_root: Path) -> None:
        """Test promoting a non-existent agent raises error."""
        service = AgentLifecycleService(temp_armance_root)
        with pytest.raises(AgentNotFoundError, match="not found"):
            service.promote_agent("nonexistent", "textiles")

    def test_demote_agent(self, temp_armance_root: Path, sample_agent: Agent) -> None:
        """Test demoting an agent from a lead topic."""
        service = AgentLifecycleService(temp_armance_root)
        service.create_agent(sample_agent)
        service.promote_agent("historian-aisha", "textiles")

        updated = service.demote_agent("historian-aisha", "textiles")
        assert "textiles" not in updated.lead_for

    def test_demote_agent_not_lead(self, temp_armance_root: Path, sample_agent: Agent) -> None:
        """Test demoting an agent who is not lead (no-op)."""
        service = AgentLifecycleService(temp_armance_root)
        service.create_agent(sample_agent)

        updated = service.demote_agent("historian-aisha", "textiles")
        assert updated.lead_for == []

    def test_demote_agent_not_found(self, temp_armance_root: Path) -> None:
        """Test demoting a non-existent agent raises error."""
        service = AgentLifecycleService(temp_armance_root)
        with pytest.raises(AgentNotFoundError, match="not found"):
            service.demote_agent("nonexistent", "textiles")


class TestArchiveAgent:
    """Tests for archive_agent method."""

    def test_archive_agent_soft(self, temp_armance_root: Path, sample_agent: Agent) -> None:
        """Test soft archive (move to .archive/)."""
        service = AgentLifecycleService(temp_armance_root)
        service.create_agent(sample_agent)

        archived = service.archive_agent("historian-aisha")
        assert archived.status == "archived"

        # Original file should be gone
        original = temp_armance_root / "agents" / "historian-aisha.md"
        assert not original.exists()

        # Archived file should exist
        archive_dir = temp_armance_root / ".archive"
        archive_files = list(archive_dir.glob("historian-aisha*.md"))
        assert len(archive_files) == 1

    def test_archive_agent_hard(self, temp_armance_root: Path, sample_agent: Agent) -> None:
        """Test hard archive (delete file)."""
        service = AgentLifecycleService(temp_armance_root)
        service.create_agent(sample_agent)

        archived = service.archive_agent("historian-aisha", hard=True)
        assert archived.status == "archived"

        # Both original and archive files should be gone
        original = temp_armance_root / "agents" / "historian-aisha.md"
        assert not original.exists()

        archive_dir = temp_armance_root / ".archive"
        archive_files = list(archive_dir.glob("historian-aisha*.md"))
        assert len(archive_files) == 0

    def test_archive_agent_not_found(self, temp_armance_root: Path) -> None:
        """Test archiving a non-existent agent raises error."""
        service = AgentLifecycleService(temp_armance_root)
        with pytest.raises(AgentNotFoundError, match="not found"):
            service.archive_agent("nonexistent")

    def test_delete_agent_alias(self, temp_armance_root: Path, sample_agent: Agent) -> None:
        """Test that delete_agent is an alias for archive_agent."""
        service = AgentLifecycleService(temp_armance_root)
        service.create_agent(sample_agent)

        # delete_agent should archive (soft) by default
        service.delete_agent("historian-aisha")

        # Should be archived
        archived = service.get_agent("historian-aisha")
        # get_agent returns None for archived agents (file moved)
        # but the registry should show archived status
        registry_file = temp_armance_root / "agents" / "registry.json"
        registry = json.loads(registry_file.read_text())
        assert registry["agents"][0]["status"] == "archived"


class TestAgentModel:
    """Tests for Agent model lifecycle fields."""

    def test_agent_to_dict(self, sample_agent: Agent) -> None:
        """Test Agent.to_dict serialization."""
        d = sample_agent.to_dict()
        assert d["name"] == "historian-aisha"
        assert d["domain"] == "historian"
        assert d["status"] == "active"
        assert d["version"] == 1

    def test_agent_from_dict(self) -> None:
        """Test Agent.from_dict deserialization."""
        data = {
            "name": "designer-kojo",
            "domain": "designer",
            "persona": "minimalist",
            "provider": "anthropic",
            "model": "claude-3.5-sonnet",
            "system_prompt": "You are Kojo.",
        }
        agent = Agent.from_dict(data)
        assert agent.name == "designer-kojo"
        assert agent.domain == "designer"
        assert agent.persona == "minimalist"

    def test_agent_sync_role_domain(self) -> None:
        """Test that role/domain are synced on construction."""
        agent = Agent(
            name="test",
            domain="historian",
            persona="test",
            provider="openai",
            model="gpt-4o",
        )
        assert agent.domain == "historian"
        assert agent.role == "historian"

    def test_agent_now_iso(self, sample_agent: Agent) -> None:
        """Test Agent.now_iso returns ISO-8601 string."""
        ts = sample_agent.now_iso()
        assert len(ts) > 0
        assert "T" in ts
        assert ts.endswith("Z")
