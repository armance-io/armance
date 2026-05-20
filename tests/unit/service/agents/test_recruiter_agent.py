"""Tests for the system-HR agent service.

Verifies:
- propose_jobs returns JobProposal list
- create_agents creates 2-4 agents per role
- archive moves agent files
"""
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from armance.core.models.agent import Agent
from armance.config import Config
from armance.service.agents.recruiter_agent import RecruiterAgentService, JobProposal


@pytest.fixture
def mock_agent():
    """Create a mock system-hr agent."""
    return Agent(
        name="system-hr",
        domain="meta",
        persona="balanced",
        provider="openrouter",
        model="openai/gpt-4o-mini",
        reasoning="medium",
        system_prompt="You are System HR.",
    )


@pytest.fixture
def mock_config():
    """Create a mock config."""
    config = MagicMock(spec=Config)
    config.default_provider = "openrouter"
    config.default_model = "openai/gpt-4o-mini"
    return config


@pytest.fixture
def temp_armance_root(tmp_path):
    """Create a temporary armance root directory."""
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    return tmp_path


@pytest.fixture
def hr_service(mock_agent, mock_config, temp_armance_root):
    """Create an RecruiterAgentService instance."""
    return RecruiterAgentService(
        agent=mock_agent,
        armance_root=temp_armance_root,
        config=mock_config,
    )


class TestProposeJobs:
    """Test job proposal functionality."""

    def test_empty_brief_raises_error(self, hr_service):
        """Empty brief should raise ValueError."""
        with pytest.raises(ValueError, match="empty"):
            # Need to use asyncio.run for sync call of async method
            import asyncio
            asyncio.run(hr_service.propose_jobs(""))

    def test_whitespace_only_brief_raises_error(self, hr_service):
        """Whitespace-only brief should raise ValueError."""
        import asyncio
        with pytest.raises(ValueError, match="empty"):
            asyncio.run(hr_service.propose_jobs("   "))

    @pytest.mark.asyncio
    async def test_propose_jobs_parses_yaml_response(self, hr_service, mock_agent):
        """Test propose_jobs parses LLM YAML response correctly."""
        yaml_response = """
jobs:
  - name: design
    description: UI/UX design system for the application
  - name: content
    description: Content strategy and copywriting
  - name: infrastructure
    description: Backend infrastructure and DevOps
"""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.text = yaml_response
        mock_client.return_value = mock_response

        with patch("armance.service.agents.recruiter_agent.get_client", return_value=mock_client):
            with patch("armance.service.agents.recruiter_agent.call_with_ledger", new_callable=AsyncMock) as mock_call:
                mock_call.return_value = mock_response
                proposals = await hr_service.propose_jobs("Build a web application")

        assert len(proposals) == 3
        assert proposals[0].name == "design"
        assert proposals[0].description == "UI/UX design system for the application"
        # agents_needed defaults to empty list — Malik picks contextual personalities
        assert proposals[0].agents_needed == []
        assert proposals[1].name == "content"
        assert proposals[2].name == "infrastructure"

    @pytest.mark.asyncio
    async def test_propose_jobs_invalid_yaml_raises_error(self, hr_service):
        """Invalid YAML response should raise ValueError."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.text = "This is not valid YAML"

        with patch("armance.service.agents.recruiter_agent.get_client", return_value=mock_client):
            with patch("armance.service.agents.recruiter_agent.call_with_ledger", new_callable=AsyncMock) as mock_call:
                mock_call.return_value = mock_response

                with pytest.raises(ValueError, match="Could not parse"):
                    await hr_service.propose_jobs("Build a web application")


class TestCreateAgents:
    """Test agent creation functionality."""

    @pytest.mark.asyncio
    async def test_create_agents_parses_yaml_response(self, hr_service, mock_agent):
        """Test create_agents parses LLM YAML response correctly."""
        yaml_response = """
agents:
  - name: design_audacious
    domain: design
    persona: audacious
    provider: openrouter
    model: openai/gpt-4o-mini
    reasoning: high
    system_prompt: |
      You are the audacious design agent.
  - name: design_prudent
    domain: design
    persona: prudent
    provider: openrouter
    model: openai/gpt-4o-mini
    reasoning: high
    system_prompt: |
      You are the prudent design agent.
  - name: design_balanced
    domain: design
    persona: balanced
    provider: openrouter
    model: openai/gpt-4o-mini
    reasoning: medium
    system_prompt: |
      You are the balanced design agent.
"""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.text = yaml_response

        with patch("armance.service.agents.recruiter_agent.get_client", return_value=mock_client):
            with patch("armance.service.agents.recruiter_agent.call_with_ledger", new_callable=AsyncMock) as mock_call:
                mock_call.return_value = mock_response
                agents = await hr_service.create_agents("design")

        assert len(agents) == 3
        # Malik now replaces snake_case role-tagged names with diverse first
        # names from the international pool. We only assert characters survive
        # and names are non-empty / unique.
        names = [a.name for a in agents]
        assert len(set(names)) == 3
        assert all(n for n in names)
        # Personas are preserved from YAML (can be contextual, not just default trio)
        assert agents[0].persona == "audacious"
        assert agents[1].persona == "prudent"
        assert agents[2].persona == "balanced"

    @pytest.mark.asyncio
    async def test_create_agents_defaults_domain(self, hr_service, mock_agent):
        """Test create_agents defaults domain to role_name when not specified."""
        yaml_response = """
agents:
  - name: design_audacious
    persona: audacious
    provider: openrouter
    model: openai/gpt-4o-mini
    system_prompt: |
      You are the audacious design agent.
  - name: design_prudent
    persona: prudent
    provider: openrouter
    model: openai/gpt-4o-mini
    system_prompt: |
      You are the prudent design agent.
  - name: design_balanced
    persona: balanced
    provider: openrouter
    model: openai/gpt-4o-mini
    system_prompt: |
      You are the balanced design agent.
"""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.text = yaml_response

        with patch("armance.service.agents.recruiter_agent.get_client", return_value=mock_client):
            with patch("armance.service.agents.recruiter_agent.call_with_ledger", new_callable=AsyncMock) as mock_call:
                mock_call.return_value = mock_response
                agents = await hr_service.create_agents("design")

        for agent in agents:
            assert agent.domain == "design"

    @pytest.mark.asyncio
    async def test_create_agents_invalid_yaml_raises_error(self, hr_service):
        """Invalid YAML response should raise ValueError."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.text = "This is not valid YAML"

        with patch("armance.service.agents.recruiter_agent.get_client", return_value=mock_client):
            with patch("armance.service.agents.recruiter_agent.call_with_ledger", new_callable=AsyncMock) as mock_call:
                mock_call.return_value = mock_response

                with pytest.raises(ValueError, match="Could not parse agents"):
                    await hr_service.create_agents("design")


class TestArchive:
    """Test agent archive functionality."""

    @pytest.mark.asyncio
    async def test_archive_moves_agent_file(self, hr_service, temp_armance_root):
        """Test archive moves agent file to .archive directory."""
        # Create an agent file
        agents_dir = temp_armance_root / "agents"
        agent_file = agents_dir / "test_agent.md"
        agent_file.write_text("---\nname: test_agent\n---\nTest agent body")

        agent = Agent(
            name="test_agent",
            domain="test",
            persona="balanced",
            provider="openrouter",
            model="openai/gpt-4o-mini",
        )

        result = await hr_service.archive(agent)

        # Verify file was moved
        archive_dir = temp_armance_root / ".archive"
        assert archive_dir.exists()
        assert (archive_dir / "test_agent.md").exists()
        assert not agent_file.exists()
        assert result == archive_dir / "test_agent.md"

    @pytest.mark.asyncio
    async def test_archive_nonexistent_agent_raises_error(self, hr_service):
        """Test archive raises error for non-existent agent."""
        agent = Agent(
            name="nonexistent_agent",
            domain="test",
            persona="balanced",
            provider="openrouter",
            model="openai/gpt-4o-mini",
        )

        with pytest.raises(FileNotFoundError, match="not found"):
            await hr_service.archive(agent)


class TestJobProposalModel:
    """Test JobProposal model."""

    def test_job_proposal_defaults(self):
        """Test JobProposal has correct defaults."""
        proposal = JobProposal(name="test", description="Test description")
        assert proposal.name == "test"
        assert proposal.description == "Test description"
        # agents_needed defaults to empty list — Malik picks contextual personalities
        assert proposal.agents_needed == []

    def test_job_proposal_custom_agents(self):
        """Test JobProposal with custom agents list."""
        proposal = JobProposal(
            name="test",
            description="Test description",
            agents_needed=["specialist"],
        )
        assert proposal.agents_needed == ["specialist"]


class TestRecruiterAgentServiceIntegration:
    """Integration tests for HR agent service."""

    @pytest.mark.asyncio
    async def test_full_job_and_agent_creation_flow(self, hr_service, mock_agent, temp_armance_root):
        """Test complete flow: propose jobs → create agents."""
        jobs_yaml = """
jobs:
  - name: design
    description: UI/UX design system
  - name: content
    description: Content strategy
"""
        agents_yaml = """
agents:
  - name: design_audacious
    domain: design
    persona: audacious
    provider: openrouter
    model: openai/gpt-4o-mini
    system_prompt: |
      You are the audacious design agent.
  - name: design_prudent
    domain: design
    persona: prudent
    provider: openrouter
    model: openai/gpt-4o-mini
    system_prompt: |
      You are the prudent design agent.
  - name: design_balanced
    domain: design
    persona: balanced
    provider: openrouter
    model: openai/gpt-4o-mini
    system_prompt: |
      You are the balanced design agent.
"""
        mock_response = MagicMock()
        mock_response.text = jobs_yaml

        with patch("armance.service.agents.recruiter_agent.get_client") as mock_get_client:
            with patch("armance.service.agents.recruiter_agent.call_with_ledger", new_callable=AsyncMock) as mock_call:
                mock_client = AsyncMock()
                mock_get_client.return_value = mock_client

                # First call: propose jobs
                mock_call.return_value = MagicMock(text=jobs_yaml)
                proposals = await hr_service.propose_jobs("Build a web application")

                assert len(proposals) == 2
                assert proposals[0].name == "design"
                assert proposals[1].name == "content"

                # Second call: create agents
                mock_call.return_value = MagicMock(text=agents_yaml)
                agents = await hr_service.create_agents("design")

                assert len(agents) == 3
                # Characters can be contextual — test with default trio still works
                assert {a.persona for a in agents} == {"audacious", "prudent", "balanced"}


class TestR13ValidationAndRetries:
    """Unit tests for Sprint V2.R2 - Task R-13: ASCII first names + Persona Uniqueness."""

    def test_validate_ascii_name_transliterates_successfully(self, hr_service):
        """Should transliterate accented names to pure ASCII."""
        assert hr_service._validate_ascii_name("Tomás") == "Tomas"
        assert hr_service._validate_ascii_name("François") == "Francois"
        assert hr_service._validate_ascii_name("Müller") == "Muller"

    def test_validate_ascii_name_raises_on_empty(self, hr_service):
        """Should raise ValueError if the name contains no transliteratable ASCII letters."""
        with pytest.raises(ValueError, match="no valid ASCII letters"):
            hr_service._validate_ascii_name("汉字")

    def test_validate_persona_uniqueness_raises_on_duplicates(self, hr_service):
        """Should raise PersonaCollisionError when there are duplicate personas."""
        from armance.service.agents.recruiter_agent import PersonaCollisionError
        agents = [
            Agent(name="Aisha", domain="design", persona="minimalist", provider="openrouter", model="m"),
            Agent(name="Yuki", domain="design", persona="minimalist", provider="openrouter", model="m"),
        ]
        with pytest.raises(PersonaCollisionError, match="Duplicate personas"):
            hr_service._validate_persona_uniqueness(agents)

    @pytest.mark.asyncio
    async def test_persona_collision_retry_loop_success_after_retry(self, hr_service):
        """Should retry once and succeed when duplicate personas are resolved."""
        from armance.service.agents.recruiter_agent import PersonaCollisionError

        # Mock first response with duplicate personas, second with unique
        resp1 = MagicMock()
        resp1.text = """
agents:
  - name: Aisha
    domain: design
    persona: minimalist
    provider: openrouter
    model: m
    system_prompt: |
      Aisha.
  - name: Yuki
    domain: design
    persona: minimalist
    provider: openrouter
    model: m
    system_prompt: |
      Yuki.
"""
        resp2 = MagicMock()
        resp2.text = """
agents:
  - name: Aisha
    domain: design
    persona: minimalist
    provider: openrouter
    model: m
    system_prompt: |
      Aisha.
  - name: Yuki
    domain: design
    persona: brutalist
    provider: openrouter
    model: m
    system_prompt: |
      Yuki.
"""
        mock_client = AsyncMock()
        with patch("armance.service.agents.recruiter_agent.get_client", return_value=mock_client):
            with patch("armance.service.agents.recruiter_agent.call_with_ledger", new_callable=AsyncMock) as mock_call:
                mock_call.side_effect = [resp1, resp2]
                agents = await hr_service.create_agents("design")
                
                assert len(agents) == 2
                assert agents[0].persona == "minimalist"
                assert agents[1].persona == "brutalist"
                assert mock_call.call_count == 2

    @pytest.mark.asyncio
    async def test_persona_collision_exhausts_retries_proposes_best_effort(self, hr_service):
        """Should exhaust retries and return downsized/best-effort unique panel."""
        resp = MagicMock()
        resp.text = """
agents:
  - name: Aisha
    domain: design
    persona: minimalist
    provider: openrouter
    model: m
    system_prompt: |
      Aisha.
  - name: Yuki
    domain: design
    persona: minimalist
    provider: openrouter
    model: m
    system_prompt: |
      Yuki.
"""
        mock_client = AsyncMock()
        with patch("armance.service.agents.recruiter_agent.get_client", return_value=mock_client):
            with patch("armance.service.agents.recruiter_agent.call_with_ledger", new_callable=AsyncMock) as mock_call:
                # Always returns duplicates
                mock_call.return_value = resp
                agents = await hr_service.create_agents("design")
                
                # Should downsize to unique personas only (keep 1)
                assert len(agents) == 1
                assert agents[0].name == "Aisha"
                assert agents[0].persona == "minimalist"
                assert mock_call.call_count == 3


class TestModelUpdateRegression:
    """Regression tests: re-recruiting an existing agent must update its model on disk."""

    def test_model_swap_writes_new_model_to_disk(self, hr_service, temp_armance_root):
        """When Malik re-recruits Theo with a new model, Theo.md on disk must have the new model."""
        agents_dir = temp_armance_root / "agents"

        yaml_v1 = """
agents:
  - name: Theo
    role: historien
    persona: culturel
    provider: openrouter
    model: deepseek/deepseek-v4-flash:free
    description: "quotidien, traditions populaires"
"""
        created_v1, _ = hr_service.recruit_agents(yaml_v1, "historien", agents_dir)
        assert len(created_v1) == 1
        theo_v1 = Agent.load(agents_dir / "Theo.md")
        assert theo_v1.model == "deepseek/deepseek-v4-flash:free"

        # Simulate Malik re-recruiting Theo with a different model.
        yaml_v2 = """
agents:
  - name: Theo
    role: historien
    persona: culturel
    provider: openrouter
    model: google/gemma-4-26b-a4b-it:free
    description: "quotidien, traditions populaires"
"""
        created_v2, names_v2 = hr_service.recruit_agents(yaml_v2, "historien", agents_dir)
        assert len(created_v2) == 1
        assert names_v2 == ["Theo"]

        # The returned agent object must have the new model.
        assert created_v2[0].model == "google/gemma-4-26b-a4b-it:free"

        # The file on disk must have the new model.
        theo_v2 = Agent.load(agents_dir / "Theo.md")
        assert theo_v2.model == "google/gemma-4-26b-a4b-it:free", (
            f"Expected google/gemma-4-26b-a4b-it:free but got {theo_v2.model} — "
            "model swap did not persist to disk"
        )

    def test_stale_persona_file_removed_on_update(self, hr_service, temp_armance_root):
        """Old Theo-culturel.md must be deleted when Theo.md is written."""
        agents_dir = temp_armance_root / "agents"
        # Simulate an old-style file with persona suffix.
        stale = agents_dir / "Theo-culturel.md"
        stale.write_text(
            "---\nname: Theo\nrole: historien\npersona: culturel\n"
            "provider: openrouter\nmodel: old/model:free\ndomain: historien\n---\nOld persona.\n"
        )
        yaml_v2 = """
agents:
  - name: Theo
    role: historien
    persona: culturel
    provider: openrouter
    model: google/gemma-4-26b-a4b-it:free
    description: "quotidien"
"""
        hr_service.recruit_agents(yaml_v2, "historien", agents_dir)
        assert not stale.exists(), "Stale Theo-culturel.md must be deleted after update"
        assert (agents_dir / "Theo.md").exists()
        assert Agent.load(agents_dir / "Theo.md").model == "google/gemma-4-26b-a4b-it:free"

    def test_criticalist_recruit_redirects_to_system_challenger(
        self, hr_service, temp_armance_root,
    ):
        """role=criticalist must update system-challenger.md (model swap),
        never create a user agent named Serge/Kai/whatever."""
        agents_dir = temp_armance_root / "agents"
        # Seed system-challenger.md (minimal frontmatter) so redirect has target.
        (agents_dir / "system-challenger.md").write_text(
            "---\nname: system-challenger\ndomain: meta\nrole: meta\n"
            "persona: null\nprovider: openrouter\nmodel: old/m:free\n"
            "reasoning: null\nstatus: active\nprovider_family: null\n"
            "created_at: null\nupdated_at: null\nversion: 1\nparent_version: null\n"
            "lead_for: []\ndescription: ''\ncreated_by: null\n"
            "last_health: null\nlast_health_at: null\n---\nbody\n",
            encoding="utf-8",
        )
        yaml_kai = """
agents:
  - name: Kai
    role: criticalist
    persona: adversarial-criticalist
    provider: openrouter
    model: openai/gpt-4o-mini:free
    description: "adversarial red-teamer"
"""
        created, names = hr_service.recruit_agents(yaml_kai, "criticalist", agents_dir)
        assert names == []
        assert not (agents_dir / "Serge.md").exists()
        assert not (agents_dir / "Kai.md").exists()
        updated = Agent.load(agents_dir / "system-challenger.md")
        assert updated.model == "openai/gpt-4o-mini:free"


class TestStaffRoleRedirect:
    """When Malik 'recruits' a staff role (host/recruiter/operator/vp),
    the recruit must rewrite the existing system-*.md model field instead
    of creating a new user agent."""

    def _seed_staff(self, agents_dir, stem: str) -> None:
        """Create a minimal system-*.md frontmatter so the redirect path
        has something to update."""
        frontmatter = (
            "---\n"
            f"name: {stem}\n"
            "domain: meta\n"
            "role: meta\n"
            "persona: null\n"
            "provider: openrouter\n"
            "model: old/model:free\n"
            "reasoning: null\n"
            "status: active\n"
            "provider_family: null\n"
            "created_at: null\n"
            "updated_at: null\n"
            "version: 1\n"
            "parent_version: null\n"
            "lead_for: []\n"
            "description: ''\n"
            "created_by: null\n"
            "last_health: null\n"
            "last_health_at: null\n"
            "---\n"
            "body\n"
        )
        (agents_dir / f"{stem}.md").write_text(frontmatter, encoding="utf-8")

    @pytest.mark.parametrize("role,system_stem", [
        ("host",           "system-context"),
        ("recruiter",      "system-hr"),
        ("operator",       "system-orchestrator"),
        ("vice-president", "system-judge"),
        ("criticalist",    "system-challenger"),
    ])
    def test_staff_role_redirects_to_system_file(
        self, hr_service, temp_armance_root, role, system_stem,
    ):
        agents_dir = temp_armance_root / "agents"
        self._seed_staff(agents_dir, system_stem)

        yaml_text = f"""
agents:
  - name: Astrid
    role: {role}
    persona: alt
    provider: openrouter
    model: new/model:free
    description: "x"
"""
        created, names = hr_service.recruit_agents(yaml_text, role, agents_dir)
        # No new user agent file created
        assert names == []
        assert not (agents_dir / "Astrid.md").exists()
        # system-*.md model field updated in place
        updated = Agent.load(agents_dir / f"{system_stem}.md")
        assert updated.model == "new/model:free"


class TestRoleCollisionAndTelemetry:
    """Tests for similar role updates, true collisions, and telemetry tracking."""

    def test_similar_role_update_succeeds(self, hr_service, temp_armance_root):
        """Updating an existing agent with a similar role (same first token) should succeed."""
        agents_dir = temp_armance_root / "agents"
        # Seed Theo with "architecte-systeme"
        (agents_dir / "Theo.md").write_text(
            "---\nname: Theo\nrole: architecte-systeme\npersona: audacieux\n"
            "provider: openrouter\nmodel: old/model:free\n---\nBody\n",
            encoding="utf-8"
        )
        yaml_text = """
agents:
  - name: Theo
    role: architecte
    persona: audacieux
    provider: openrouter
    model: new/model:free
"""
        created, names = hr_service.recruit_agents(yaml_text, "architecte", agents_dir)
        assert names == ["Theo"]
        assert hr_service.last_new_names == []
        assert hr_service.last_updated_names == ["Theo"]
        assert hr_service.last_skipped_collisions == []
        
        # Verify the file was updated with the new model
        updated = Agent.load(agents_dir / "Theo.md")
        assert updated.model == "new/model:free"
        assert updated.role == "architecte"

    def test_true_role_collision_blocked(self, hr_service, temp_armance_root):
        """Updating an existing agent with a completely different role should be blocked."""
        agents_dir = temp_armance_root / "agents"
        # Seed Theo with "architecte-systeme"
        (agents_dir / "Theo.md").write_text(
            "---\nname: Theo\nrole: architecte-systeme\npersona: audacieux\n"
            "provider: openrouter\nmodel: old/model:free\n---\nBody\n",
            encoding="utf-8"
        )
        
        with patch.object(hr_service, "_parse_agents_yaml") as mock_parse:
            mock_parse.return_value = [
                Agent(
                    name="Theo",
                    role="historien",
                    persona="audacieux",
                    provider="openrouter",
                    model="new/model:free",
                    system_prompt="New prompt",
                )
            ]
            
            created, names = hr_service.recruit_agents("dummy yaml", "historien", agents_dir)
            assert names == []
            assert hr_service.last_new_names == []
            assert hr_service.last_updated_names == []
            assert hr_service.last_skipped_collisions == ["Theo"]
            
            # Verify the file was NOT updated and kept the old model/role
            unchanged = Agent.load(agents_dir / "Theo.md")
            assert unchanged.model == "old/model:free"
            assert unchanged.role == "architecte-systeme"

    def test_staff_and_new_agent_telemetry(self, hr_service, temp_armance_root):
        """Verify new agents and staff updates are tracked correctly in telemetry."""
        agents_dir = temp_armance_root / "agents"
        # Seed system-context
        frontmatter = (
            "---\nname: system-context\ndomain: meta\nrole: meta\n"
            "persona: null\nprovider: openrouter\nmodel: old/model:free\n"
            "reasoning: null\nstatus: active\nprovider_family: null\n"
            "created_at: null\nupdated_at: null\nversion: 1\nparent_version: null\n"
            "lead_for: []\ndescription: ''\ncreated_by: null\n"
            "last_health: null\nlast_health_at: null\n---\nbody\n"
        )
        (agents_dir / "system-context.md").write_text(frontmatter, encoding="utf-8")

        yaml_text = """
agents:
  - name: Priya
    role: developpeur
    persona: innovateur
    provider: openrouter
    model: new/model:free
  - name: Astrid
    role: host
    persona: context
    provider: openrouter
    model: host/model:free
"""
        created, names = hr_service.recruit_agents(yaml_text, "developpeur", agents_dir)
        assert names == ["Priya"]
        assert hr_service.last_new_names == ["Priya"]
        assert hr_service.last_updated_names == []
        assert hr_service.last_staff_updates == ["system-context(host/model:free)"]
        assert hr_service.last_skipped_collisions == []
