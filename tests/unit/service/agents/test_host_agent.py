"""Tests for the system-context agent service.

Verifies the complete flow of Armance:
1. User provides input / command.
2. Armance handles saving context or routing.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from armance.core.models.agent import Agent
from armance.config import Config
from armance.service.agents.host_agent import HostAgentService


@pytest.fixture
def mock_agent():
    """Create a mock system-context agent."""
    return Agent(
        name="system-context",
        domain="meta",
        persona="balanced",
        provider="openrouter",
        model="openai/gpt-4o-mini",
        reasoning="medium",
        system_prompt="You are System Context.",
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
    roles_dir = tmp_path / "roles"
    context_dir = tmp_path / "context"
    agents_dir.mkdir()
    roles_dir.mkdir()
    context_dir.mkdir()
    return tmp_path


@pytest.fixture
def host_service(mock_agent, mock_config, temp_armance_root):
    """Create a HostAgentService instance."""
    return HostAgentService(
        agent=mock_agent,
        armance_root=temp_armance_root,
        config=mock_config,
    )


class TestGreetingDetection:
    """Test _is_greeting detection logic."""

    def test_bare_greetings_detected(self, host_service):
        """Bare greetings must be identified so they don't pollute the buffer."""
        assert host_service._is_greeting("hi") is True
        assert host_service._is_greeting("hello") is True
        assert host_service._is_greeting("hey there") is True
        assert host_service._is_greeting("bonjour") is True

    def test_substantive_text_not_greeting(self, host_service):
        """Project descriptions are not bare greetings."""
        assert host_service._is_greeting("I want to build a web app") is False
        assert host_service._is_greeting("My project is a mobile app") is False
        assert host_service._is_greeting("We need a consulting framework") is False



class TestIntentDetection:
    """Test slash command intent detection."""

    def test_save_intent(self, host_service):
        assert host_service._detect_intent("/save") == "save"
        assert host_service._detect_intent("/save --layer L1") == "save"

    def test_switch_intent(self, host_service):
        assert host_service._detect_intent("/switch design") == "switch"
        assert host_service._detect_intent("/switch content") == "switch"

    def test_quit_intent(self, host_service):
        assert host_service._detect_intent("/quit") == "quit"
        assert host_service._detect_intent("/exit") == "quit"

    def test_help_intent(self, host_service):
        assert host_service._detect_intent("/help") == "help"

    def test_role_intent(self, host_service):
        assert host_service._detect_intent("/role list") == "role"
        assert host_service._detect_intent("/role show design") == "role"

    def test_chat_intent(self, host_service):
        assert host_service._detect_intent("Hello, how are you?") == "chat"
        assert host_service._detect_intent("Tell me more about Armance") == "chat"


class TestHandoffFlow:
    """Test recruitment redirection handoff to Malik."""

    @pytest.mark.asyncio
    async def test_explicit_recruit_goes_through_llm(self, host_service):
        """Recruitment requests now go through the LLM (Armance decides semantically).

        With the pure-LLM architecture, there's no Python short-circuit.
        Armance's response comes from the LLM, which may mention Malik.
        """
        with patch("armance.service.agents.host_agent.get_client") as mock_gc, \
             patch("armance.service.agents.host_agent.call_with_ledger", new_callable=AsyncMock) as mock_call:
            mock_response = MagicMock()
            mock_response.text = "Je vais demander à Malik de s'en occuper."
            mock_call.return_value = mock_response
            response = await host_service.dialogue("recrute une équipe pour ce projet")
            assert mock_call.called
            assert "Malik" in response


class TestRoleCreationFlow:
    """Test role commands."""

    @pytest.mark.asyncio
    async def test_role_list(self, host_service, temp_armance_root):
        """Test /role list command."""
        # Create a sample role file
        role_file = temp_armance_root / "roles" / "design.md"
        role_file.write_text("---\nname: design\n---\n# Role: Design")

        response = await host_service.dialogue("/role list")

        assert "Roles:" in response
        assert "design" in response

    @pytest.mark.asyncio
    async def test_role_list_empty(self, host_service, temp_armance_root):
        """Test /role list when no roles exist."""
        response = await host_service.dialogue("/role list")

        assert "No roles found" in response

    @pytest.mark.asyncio
    async def test_role_show(self, host_service, temp_armance_root):
        """Test /role show command."""
        role_file = temp_armance_root / "roles" / "design.md"
        role_file.write_text("---\nname: design\n---\n# Role: Design\n\nDesign role description")

        response = await host_service.dialogue("/role show design")

        assert "Role 'design'" in response
        assert "Design role description" in response

    @pytest.mark.asyncio
    async def test_role_show_not_found(self, host_service, temp_armance_root):
        """Test /role show for non-existent role."""
        response = await host_service.dialogue("/role show nonexistent")

        assert "not found" in response


class TestHelpCommand:
    """Test /help command output."""

    def test_help_shows_all_commands(self, host_service):
        response = host_service._handle_help()

        assert "/save" in response
        assert "/switch" in response
        assert "/role list" in response
        assert "/role show" in response
        assert "/quit" in response
        assert "/help" in response


class TestSwitchCommand:
    """Test /switch command handling."""

    def test_switch_with_agent_name(self, host_service):
        response = host_service._handle_switch("/switch design")
        assert "Switching to agent: design" in response

    def test_switch_without_agent_name(self, host_service):
        response = host_service._handle_switch("/switch")
        assert "Usage" in response


class TestSaveCommand:
    """Test /save command handling."""

    @pytest.mark.asyncio
    async def test_save_freezes_context(self, host_service, mock_agent, mock_config, temp_armance_root, monkeypatch):
        """Test /save command freezes context to L0."""
        host_service._buffer = ["We want to study the conjoint history of France and Scotland during medieval times, specifically focusing on the Auld Alliance."]

        # Stub LLM call used inside freeze()
        from armance.service.agents import host_agent as _ha

        class _Resp:
            text = "## L0\n\n### Goal\nstudy France/Scotland medieval ties.\n"

        async def _fake_call(*a, **kw):
            return _Resp()

        async def _fake_get_client(*a, **kw):
            return object()

        monkeypatch.setattr(_ha, "call_with_ledger", _fake_call)
        monkeypatch.setattr(_ha, "get_client", lambda *a, **kw: object())

        response = await host_service.dialogue("/save")

        assert "context saved as L0_v" in response.lower() or "context saved" in response.lower()
        assert host_service._buffer == []

    @pytest.mark.asyncio
    async def test_freeze_empty_buffer_produces_goal_placeholder(self, host_service, mock_agent, mock_config, temp_armance_root):
        """Regression: freeze() with empty buffer and no prior L0 must still produce a non-empty body."""
        # Ensure buffer is empty and no prior L0 exists
        host_service._buffer = []
        # Call freeze directly (not via dialogue)
        result = await host_service.freeze()
        assert result is not None
        # Check the written file has Goal section
        l0_dir = temp_armance_root / "context" / "L0"
        l0_files = list(l0_dir.glob("v*.md"))
        assert len(l0_files) == 1
        content = l0_files[0].read_text(encoding="utf-8")
        assert "## L0" in content
        assert "### Goal" in content
        assert "Project context to be defined" in content


class TestContextAgentIntegration:
    """Integration tests for context agent with mock LLM."""

    @pytest.mark.asyncio
    async def test_start_returns_welcome_message(self, host_service):
        """Test start() returns welcome message."""
        response = await host_service.start()

        assert "Welcome to Armance" in response
        assert "project description" in response.lower() or "context" in response.lower()


class TestAgentsExist:
    """Test _agents_exist detection logic."""

    def test_no_agents_dir(self, host_service):
        """No agents directory means no agents."""
        assert host_service._agents_exist() is False

    def test_empty_agents_dir(self, host_service, temp_armance_root):
        """Empty agents directory means no agents."""
        assert host_service._agents_exist() is False

    def test_only_system_agents(self, host_service, temp_armance_root):
        """Only system agents means no user agents."""
        agents_dir = temp_armance_root / "agents"
        (agents_dir / "system-context.md").write_text("system context")
        (agents_dir / "system-hr.md").write_text("system hr")
        assert host_service._agents_exist() is False

    def test_user_agent_exists(self, host_service, temp_armance_root):
        """User agent means agents exist."""
        agents_dir = temp_armance_root / "agents"
        (agents_dir / "design_audacious.md").write_text("design audacious")
        assert host_service._agents_exist() is True


class TestAsksWhatToDo:
    """Test _asks_what_to_do detection logic."""

    def test_what_can_i_do(self, host_service):
        assert host_service._asks_what_to_do("What can I do next?") is True
        assert host_service._asks_what_to_do("what can i do") is True

    def test_what_should_i_do(self, host_service):
        assert host_service._asks_what_to_do("What should I do now?") is True
        assert host_service._asks_what_to_do("what should i do") is True

    def test_whats_next(self, host_service):
        assert host_service._asks_what_to_do("What's next?") is True
        assert host_service._asks_what_to_do("what next") is True

    def test_how_to_start(self, host_service):
        assert host_service._asks_what_to_do("How do I start?") is True
        assert host_service._asks_what_to_do("how to start") is True

    def test_not_asking_what_to_do(self, host_service):
        assert host_service._asks_what_to_do("Hello there") is False
        assert host_service._asks_what_to_do("Tell me about Armance") is False
        assert host_service._asks_what_to_do("I want to build a project") is False


class TestWorkflowSuggestion:
    """Test workflow suggestion after agents exist."""

    @pytest.mark.asyncio
    async def test_suggest_workflows_when_agents_exist(self, host_service, temp_armance_root):
        """_suggest_workflows() lists workflows and roles when agents exist."""
        # Create a user agent
        agents_dir = temp_armance_root / "agents"
        (agents_dir / "design_audacious.md").write_text("design audacious")

        response = await host_service._suggest_workflows()

        assert "Now that you have agents" in response
        assert "workflow" in response.lower()

    @pytest.mark.asyncio
    async def test_dialogue_always_calls_llm(self, host_service, mock_agent, mock_config):
        """dialogue() always routes through the LLM (no Python short-circuits)."""
        with patch("armance.service.agents.host_agent.get_client") as mock_get_client:
            with patch("armance.service.agents.host_agent.call_with_ledger", new_callable=AsyncMock) as mock_call:
                mock_call.return_value = MagicMock(text="Let me understand your project better.")
                mock_get_client.return_value = AsyncMock()

                response = await host_service.dialogue("What can I do?")

        mock_call.assert_called_once()

    @pytest.mark.asyncio
    async def test_workflow_suggestion_lists_roles(self, host_service, temp_armance_root):
        """_suggest_workflows() should list available roles when called directly."""
        # Create agent and role
        agents_dir = temp_armance_root / "agents"
        (agents_dir / "design_audacious.md").write_text("design audacious")
        roles_dir = temp_armance_root / "roles"
        (roles_dir / "design.md").write_text("---\nname: design\n---\n# Role: Design")

        response = await host_service._suggest_workflows()

        assert "design" in response


class TestBuildSystemPrompt:
    """Test _build_system_prompt guardrails."""

    def test_no_team_has_context_first_mandate(self, host_service, temp_armance_root):
        """When no team yet, prompt warns about empty roster + forbids invention."""
        prompt = host_service._build_system_prompt()
        assert "Team currently on board" in prompt
        assert "ROSTER IS EMPTY" in prompt
        assert "@Malik" in prompt

    def test_team_roster_injected(self, host_service, temp_armance_root):
        """Injected team roster (set on the service) appears in the prompt."""
        from armance.core.models.agent import Agent
        host_service._team_roster = [
            Agent(
                name="Tom", domain="woodworker", role="woodworker",
                persona="audacious", provider="openrouter", model="m",
            ),
        ]
        prompt = host_service._build_system_prompt()
        assert "Tom" in prompt
        assert "woodworker" in prompt

    def test_project_brief_injected(self, host_service, temp_armance_root):
        """When a project brief is set, Armance sees it in the system prompt."""
        host_service._project_brief = "Build a custom oak coffee table."
        prompt = host_service._build_system_prompt()
        assert "oak coffee table" in prompt


class TestIngestDocsFlow:
    """Test [EXECUTE:/ingest-docs] interception and _handle_ingest_docs."""

    @pytest.mark.asyncio
    async def test_ingest_docs_called_on_execute_tag(self, host_service, monkeypatch):
        """dialogue() must intercept [EXECUTE:/ingest-docs] and call _handle_ingest_docs."""
        ingest_calls: list[int] = []

        async def fake_handle_ingest(self_):
            ingest_calls.append(1)
            return "*(Système : ✅ indexation terminée — 2 document(s) indexé(s))*"

        monkeypatch.setattr(
            "armance.service.agents.host_agent.HostAgentService._handle_ingest_docs",
            fake_handle_ingest,
        )

        with patch("armance.service.agents.host_agent.get_client"), \
             patch("armance.service.agents.host_agent.call_with_ledger", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = MagicMock(
                text="Indexation en cours…\n[EXECUTE:/ingest-docs]"
            )
            reply = await host_service.dialogue("oui")

        assert "[EXECUTE:/ingest-docs]" not in reply
        assert len(ingest_calls) == 1
        assert "library" in reply.lower() or "added" in reply.lower() or "indexé" in reply.lower()

    @pytest.mark.asyncio
    async def test_handle_ingest_docs_no_docs_dir(self, host_service, temp_armance_root):
        """_handle_ingest_docs returns friendly message when docs dir is absent."""
        # temp_armance_root has no docs/ subdir
        result = await host_service._handle_ingest_docs()
        assert "no documents" in result.lower() or "aucun document" in result.lower()

    @pytest.mark.asyncio
    async def test_handle_ingest_docs_with_file(self, host_service, temp_armance_root, monkeypatch):
        """_handle_ingest_docs returns success message when a file is indexed."""
        docs_dir = temp_armance_root / "docs"
        docs_dir.mkdir()
        (docs_dir / "spec.md").write_text("# My spec\nSome content here.")

        def fake_sync(root, config=None, **kw):
            return {"indexed": 1, "skipped": 0, "deleted": 0}

        monkeypatch.setattr("armance.storage.ingestion.sync_docs", fake_sync)

        result = await host_service._handle_ingest_docs()
        assert "1" in result
        assert "added" in result.lower() or "library" in result.lower() or "indexé" in result.lower()
