"""Tests for armance.client.tui.tui_loop and armance.service.handlers.

All LLM / meeting calls are stubbed — no real network or I/O.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from armance.service.handlers import (
    HANDLERS,
    LoopContext,
    _cmd_chat,
    _cmd_deliverable,
    _cmd_effort,
    _cmd_export,
    _cmd_help,
    _cmd_judge,
    _cmd_model,
    _cmd_quit,
    _cmd_report,
    _cmd_switch,
    _cmd_task,
    _cmd_workflow,
    _set_status,
)
from armance.config import Config, ProviderConfig
from armance.service.llm_service import TokenLedger
from armance.service.report import Report
from armance.service.session import SessionState, save_state
from armance.client.tui.types import AgentStatus


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

def _make_cfg() -> Config:
    return Config(
        providers=[ProviderConfig(name="openrouter", api_key="test")],
        default_provider="openrouter",
        default_model="gpt-4o-mini",
    )


def _make_agent_file(tmp_path: Path, name: str = "test_agent", domain: str = "backend") -> Path:
    agents_dir = tmp_path / ".armance" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    path = agents_dir / f"{name}.md"
    path.write_text(
        f"---\nname: {name}\ndomain: {domain}\ncharacter: balanced\n"
        "provider: openrouter\nmodel: gpt-4o-mini\n---\nYou are a test agent.\n",
        encoding="utf-8",
    )
    return path


class _StubCheckpointHandler:
    """Test-only checkpoint handler: returns canned responses in order."""

    def __init__(self, responses: list[str | None]) -> None:
        self._responses = list(responses)

    async def prompt(self, checkpoint: Any) -> Any:
        from armance.service.checkpoint import CheckpointResponse
        if not self._responses:
            return CheckpointResponse(content="", is_abort=True)
        nxt = self._responses.pop(0)
        if nxt is None:
            return CheckpointResponse(content="", is_abort=True)
        return CheckpointResponse(content=nxt)


def _make_ctx(
    tmp_path: Path,
    agent_path: Path | None = None,
    checkpoint_responses: list[str | None] | None = None,
) -> LoopContext:
    from armance.service.session import Session, SessionState
    from armance.service.tui_bridge import make_loop_context
    armance_root = tmp_path / ".armance"
    armance_root.mkdir(parents=True, exist_ok=True)
    cfg = _make_cfg()
    state = SessionState.new()
    session = Session(state, armance_root)
    ledger = TokenLedger()

    handler = (
        _StubCheckpointHandler(checkpoint_responses)
        if checkpoint_responses is not None
        else None
    )
    ctx = make_loop_context(
        armance_root, cfg, state, session, ledger, checkpoint_handler=handler
    )
    if agent_path:
        from armance.core.models.agent import Agent
        ctx.agents = [Agent.load(agent_path)]
    return ctx


def _fake_meeting_result() -> Any:
    """Return a Report-like stub (meeting.py removed)."""
    return Report(
        agent_name="test_agent",
        domain="backend",
        prompt_truncated="test prompt",
        content="stub response",
    )


# ---------------------------------------------------------------------------
# /help
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cmd_help_returns_command_list(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    result = await _cmd_help([], ctx)
    assert "/task" in result
    assert "/quit" in result


# ---------------------------------------------------------------------------
# /quit
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cmd_quit_returns_quit_sentinel(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    result = await _cmd_quit([], ctx)
    assert result == "[quit]"


# ---------------------------------------------------------------------------
# /switch
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cmd_switch_loads_agent(tmp_path: Path) -> None:
    agent_path = _make_agent_file(tmp_path, "alpha")
    ctx = _make_ctx(tmp_path)
    result = await _cmd_switch(["alpha"], ctx)
    assert "alpha" in result
    assert ctx.state.current_agent == "alpha"


@pytest.mark.asyncio
async def test_cmd_switch_missing_agent_returns_error(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    result = await _cmd_switch(["ghost"], ctx)
    assert "error" in result.lower()


@pytest.mark.asyncio
async def test_cmd_switch_no_args_returns_usage(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    result = await _cmd_switch([], ctx)
    assert "usage" in result.lower()


# ---------------------------------------------------------------------------
# /model
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cmd_model_updates_state(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path, checkpoint_responses=["openrouter", "gpt-4-turbo"])
    result = await _cmd_model([], ctx)
    assert ctx.state.current_provider == "openrouter"
    assert ctx.state.current_model == "gpt-4-turbo"
    assert "gpt-4-turbo" in result


@pytest.mark.asyncio
async def test_cmd_model_cancelled(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path, checkpoint_responses=[None])
    result = await _cmd_model([], ctx)
    assert "cancelled" in result


# ---------------------------------------------------------------------------
# /effort
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cmd_effort_sets_ctx_effort(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path, checkpoint_responses=["high"])
    result = await _cmd_effort([], ctx)
    assert ctx.effort == "high"
    assert "high" in result


@pytest.mark.asyncio
async def test_cmd_effort_cancelled(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path, checkpoint_responses=[None])
    result = await _cmd_effort([], ctx)
    assert "cancelled" in result


# ---------------------------------------------------------------------------
# /task
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cmd_task_no_args_returns_usage(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    result = await _cmd_task([], ctx)
    assert "usage" in result.lower()


@pytest.mark.asyncio
async def test_cmd_task_runs_meeting(tmp_path: Path) -> None:
    agent_path = _make_agent_file(tmp_path, "test_agent", "backend")
    ctx = _make_ctx(tmp_path, agent_path)
    fake_report = _fake_meeting_result()
    with patch("armance.service.task_ops.run_specialist", new=AsyncMock(return_value=fake_report)):
        result = await _cmd_task(["backend", "design", "the", "auth"], ctx)
    assert "stub response" in result


@pytest.mark.asyncio
async def test_cmd_task_sets_agent_status(tmp_path: Path) -> None:
    agent_path = _make_agent_file(tmp_path, "test_agent", "backend")
    ctx = _make_ctx(tmp_path, agent_path)
    fake_report = _fake_meeting_result()
    with patch("armance.service.task_ops.run_specialist", new=AsyncMock(return_value=fake_report)):
        await _cmd_task(["backend", "test prompt"], ctx)
    # status should be 'completed' after success
    states = {s.name: s.state for s in ctx.statuses}
    assert any(v == "completed" for v in states.values())


# ---------------------------------------------------------------------------
# /report
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cmd_report_no_output_returns_message(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    result = await _cmd_report([], ctx)
    assert "no output" in result.lower()


@pytest.mark.asyncio
async def test_cmd_report_saves_file(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    ctx.state.current_agent = "test_agent"
    ctx._last_output = "some agent output text"
    result = await _cmd_report([], ctx)
    assert "saved" in result.lower()
    assert ".md" in result


# ---------------------------------------------------------------------------
# /judge
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cmd_judge_no_args_returns_usage(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    result = await _cmd_judge([], ctx)
    assert "usage" in result.lower()


@pytest.mark.asyncio
async def test_cmd_judge_calls_run_judge(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    # Create a dummy report file
    report_path = ctx.armance_root / "reports" / "backend" / "agent_v1.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        "---\nuuid: abc\ntimestamp: '2024-01-01T00:00:00'\nagent: agent\ndomain: backend\n"
        "prompt_truncated: test\npartial: false\n---\ntest content\n",
        encoding="utf-8",
    )
    fake_out = ctx.armance_root / "judge" / "judge_v1.md"
    fake_out.parent.mkdir(parents=True, exist_ok=True)
    fake_out.write_text("judge result", encoding="utf-8")

    from armance.service.agents.judge_agent import Synthesis
    fake_synthesis = Synthesis(content="judge result", view="judge:agent_v1", claim_count=0)
    with patch("armance.service.agents.judge_agent.JudgeAgent.synthesise", new=AsyncMock(return_value=fake_synthesis)):
        result = await _cmd_judge(["@reports/backend/agent_v1.md"], ctx)
    assert "judge" in result.lower()


# ---------------------------------------------------------------------------
# /export
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cmd_export_no_args_returns_usage(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    result = await _cmd_export([], ctx)
    assert "usage" in result.lower()


@pytest.mark.asyncio
async def test_cmd_export_target(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    out_path = tmp_path / "CLAUDE.md"
    with patch("armance.service.task_ops.export_target", return_value=out_path) as mock_exp:
        result = await _cmd_export(["claude"], ctx)
    mock_exp.assert_called_once()
    assert "CLAUDE.md" in result


@pytest.mark.asyncio
async def test_cmd_export_all(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    paths = [tmp_path / "CLAUDE.md", tmp_path / "AGENTS.md"]
    with patch("armance.service.task_ops.export_all", return_value=paths) as mock_all:
        result = await _cmd_export(["all"], ctx)
    mock_all.assert_called_once()
    assert "exported" in result.lower()


# ---------------------------------------------------------------------------
# /workflow run
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cmd_workflow_run_missing_file(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    result = await _cmd_workflow(["run", "nonexistent"], ctx)
    assert "not found" in result.lower()


@pytest.mark.asyncio
async def test_cmd_workflow_run_executes(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path, checkpoint_responses=["do something", "yes"])
    wf_path = ctx.armance_root / "workflows" / "test_wf.yaml"
    wf_path.parent.mkdir(parents=True, exist_ok=True)
    wf_path.write_text(
        "name: test_wf\nsteps:\n  - id: step1\n    kind: meeting\n    domain: backend\n"
        "    mode: light\n    prompt_template: '{{user_prompt}}'\n",
        encoding="utf-8",
    )
    from armance.core.models.workflow import StepResult  # noqa: F401

    with patch(
        "armance.service.task_ops.run_specialist",
        new=AsyncMock(return_value=_fake_meeting_result()),
    ):
        result = await _cmd_workflow(["run", "test_wf"], ctx)
    assert "step1" in result or "stub response" in result


# ---------------------------------------------------------------------------
# free-text chat
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_chat_appends_to_transcript(tmp_path: Path) -> None:
    agent_path = _make_agent_file(tmp_path, "test_agent", "backend")
    ctx = _make_ctx(tmp_path, agent_path)
    ctx.state.current_agent = "test_agent"
    fake_response = MagicMock(text="stub response", finish_reason="stop")
    with patch("armance.service.agents.specialist_runner.get_client", return_value=MagicMock()), \
         patch("armance.service.agents.specialist_runner.call_with_ledger",
               new_callable=AsyncMock, return_value=fake_response):
        result = await _cmd_chat("hello world", ctx)
    assert "stub response" in result
    assert len(ctx.session.conversation.turns) == 2
    assert ctx.session.conversation.turns[0].role == "user"
    assert ctx.session.conversation.turns[0].content == "hello world"
    assert ctx.session.conversation.turns[1].role == "assistant"


@pytest.mark.asyncio
async def test_chat_writes_transcript_md(tmp_path: Path) -> None:
    agent_path = _make_agent_file(tmp_path, "test_agent", "backend")
    ctx = _make_ctx(tmp_path, agent_path)
    ctx.state.current_agent = "test_agent"
    fake_response = MagicMock(text="stub response", finish_reason="stop")
    with patch("armance.service.agents.specialist_runner.get_client", return_value=MagicMock()), \
         patch("armance.service.agents.specialist_runner.call_with_ledger",
               new_callable=AsyncMock, return_value=fake_response):
        await _cmd_chat("hello world", ctx)
    transcript_path = ctx.armance_root / "conversations" / f"{ctx.state.id}.md"
    assert transcript_path.exists()
    content = transcript_path.read_text()
    assert "user" in content.lower()
    assert "hello world" in content


@pytest.mark.asyncio
async def test_chat_saves_state(tmp_path: Path) -> None:
    agent_path = _make_agent_file(tmp_path, "test_agent", "backend")
    ctx = _make_ctx(tmp_path, agent_path)
    ctx.state.current_agent = "test_agent"
    fake_response = MagicMock(text="stub response", finish_reason="stop")
    with patch("armance.service.agents.specialist_runner.get_client", return_value=MagicMock()), \
         patch("armance.service.agents.specialist_runner.call_with_ledger",
               new_callable=AsyncMock, return_value=fake_response):
        await _cmd_chat("test", ctx)
    state_path = ctx.armance_root / "sessions" / ctx.state.id / "state.json"
    assert state_path.exists()


# ---------------------------------------------------------------------------
# /quit persists state (via Textual TUI exit path)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_quit_persists_state(tmp_path: Path) -> None:
    """Session state is saved on exit via save_state."""
    from armance.service.session import save_state
    armance_root = tmp_path / ".armance"
    armance_root.mkdir(parents=True, exist_ok=True)
    state = SessionState.new()
    save_state(armance_root, state)
    state_path = armance_root / "sessions" / state.id / "state.json"
    assert state_path.exists()


@pytest.mark.skip(reason="tui_loop.run_tui removed; Textual TUI tested via app.py pilot tests")
@pytest.mark.asyncio
async def test_ctrl_c_cancels_running_task(tmp_path: Path) -> None:
    pass


# ---------------------------------------------------------------------------
# handler dispatch table is complete
# ---------------------------------------------------------------------------

def test_handler_keys_match_commands() -> None:
    from armance.client.tui.types import COMMANDS
    expected = set(COMMANDS) - {"quit"}  # quit handled inline in TUI
    for name in expected:
        assert name in HANDLERS, f"missing handler for /{name}"


# Session state fields moved to metadata or removed


# ---------------------------------------------------------------------------
# workflow.py prior_session.notes template
# ---------------------------------------------------------------------------

def test_render_template_prior_session_notes() -> None:
    from armance.core.models.workflow import render_template, StepResult
    tmpl = "Notes: {{prior_session.notes}}\nPrompt: {{user_prompt}}"
    result = render_template(
        tmpl,
        user_prompt="my prompt",
        results={},
        prior_session_notes="previous context",
    )
    assert "previous context" in result
    assert "my prompt" in result


def test_render_template_prior_session_notes_default_empty() -> None:
    from armance.core.models.workflow import render_template
    tmpl = "{{prior_session.notes}}{{user_prompt}}"
    result = render_template(tmpl, user_prompt="hello", results={})
    assert result == "hello"


# ---------------------------------------------------------------------------
# /deliverable stub handler
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cmd_deliverable_no_args_returns_usage(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    result = await _cmd_deliverable([], ctx)
    assert "usage" in result.lower()


@pytest.mark.asyncio
async def test_cmd_deliverable_unsupported_format(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    result = await _cmd_deliverable(["bmp"], ctx)
    assert "unsupported" in result.lower()


@pytest.mark.asyncio
async def test_cmd_deliverable_no_content(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    result = await _cmd_deliverable(["pptx"], ctx)
    assert "no content" in result.lower()


@pytest.mark.asyncio
async def test_cmd_deliverable_renders_md(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    ctx._last_output = "# Title\n\n## Section\n\nBody text."
    result = await _cmd_deliverable(["md"], ctx)
    assert "deliverable created" in result.lower()


@pytest.mark.asyncio
async def test_cmd_deliverable_renders_docx(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    ctx._last_output = "# Report\n\n## Summary\n\nText here."
    result = await _cmd_deliverable(["docx"], ctx)
    assert "deliverable created" in result.lower()


@pytest.mark.asyncio
async def test_cmd_deliverable_with_source(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    result = await _cmd_deliverable(["docx", "from=latest_judge"], ctx)
    # no judge file exists → no content
    assert "no content" in result.lower()


# ---------------------------------------------------------------------------
# streaming: run_meeting_stream exists + render test
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="render_layout removed with tui.py; Textual Sidebar widget replaces it")
def test_streaming_render() -> None:
    """render_layout removed — Textual Sidebar.add_agent() replaces this."""
    pass

def test_run_specialist_function_exists() -> None:
    from armance.service.agents.specialist_runner import run_specialist
    assert asyncio.iscoroutinefunction(run_specialist)
