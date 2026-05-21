from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from armance.config import Config, ProviderConfig
from armance.core.models.agent import Agent
from armance.core.models.workflow import WorkflowStep
from armance.service.checkpoint import Checkpoint, CheckpointResponse
from armance.service.handlers import _mona_proxy_checkpoint, _cmd_workflow_run
from armance.service.workflow_runs import create_run, finalise, write_assumptions


@pytest.fixture
def cfg() -> Config:
    return Config(
        providers=[ProviderConfig(name="openrouter", api_key="t")],
        default_provider="openrouter",
        default_model="openai/gpt-4o-mini",
    )


@pytest.fixture
def armance_root(tmp_path: Path) -> Path:
    root = tmp_path
    (root / "agents").mkdir(parents=True)
    (root / ".armance" / "workflows").mkdir(parents=True)
    (root / "context" / "L0").mkdir(parents=True)
    return root


def test_write_assumptions_and_finalise(tmp_path: Path) -> None:
    # Setup tmp armance root
    root = tmp_path / "proj"
    root.mkdir()
    
    artefact = create_run(root, "test-wf")
    assert not artefact.assumptions_path().exists()
    
    # Write some assumptions
    write_assumptions(artefact, "Test assumption content")
    assert artefact.assumptions_path().exists()
    assert artefact.assumptions_path().read_text(encoding="utf-8") == "Test assumption content"
    
    # Finalise run
    finalise(artefact, status="completed")
    
    manifest_data = json.loads(artefact.manifest_path().read_text(encoding="utf-8"))
    assert manifest_data["assumptions_present"] is True


@pytest.mark.asyncio
async def test_mona_proxy_checkpoint_includes_critical_instruction(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    
    ctx = MagicMock()
    ctx.armance_root = root
    ctx.state.project_brief = "My project brief"
    ctx.cfg = Config()
    
    step = WorkflowStep(id="check1", kind="checkpoint", prompt="Should we use postgres?")
    
    mock_agent = MagicMock()
    mock_report = MagicMock()
    mock_report.content = "[ASK_USER] I cannot decide on database because it is critical. Which db?"
    
    with patch("armance.service.handlers.Path.exists", return_value=True), \
         patch("armance.core.models.agent.Agent.load", return_value=mock_agent), \
         patch("armance.service.handlers.run_specialist", new_callable=AsyncMock, return_value=mock_report) as mock_run:
         
        res = await _mona_proxy_checkpoint(step, {"upstream1": "upstream output"}, ctx)
        assert res.startswith("[ASK_USER]")
        
        args, kwargs = mock_run.call_args
        called_task = args[1]
        assert "CRITICAL" in called_task.prompt
        assert "[ASK_USER]" in called_task.prompt


@pytest.mark.asyncio
async def test_checkpoint_handler_autonomous_delegation(armance_root: Path, cfg: Config) -> None:
    # Write a workflow with a checkpoint step
    wf_path = armance_root / ".armance" / "workflows" / "check_wf.yaml"
    wf_path.write_text(
        "name: check_wf\n"
        "strategy: rapide\n"
        "steps:\n"
        "  - id: check1\n"
        "    kind: human_checkpoint\n"
        "    prompt: 'Should we use PostgreSQL?'\n"
    )

    from armance.service.loop_context import LoopContext
    from armance.service.session import Session, SessionState
    from armance.service.llm_service import TokenLedger

    state = SessionState.new()
    session = Session(state, armance_root)
    ctx = LoopContext(
        armance_root=armance_root,
        cfg=cfg,
        state=state,
        session=session,
        ledger=TokenLedger(),
        statuses=[],
        agents=[],
    )

    # Mock checkpoint handler to return a value when prompted
    mock_ch = AsyncMock()
    mock_ch.prompt.return_value = CheckpointResponse(content="postgres", is_abort=False)
    ctx.checkpoint_handler = mock_ch

    # Mock compile_assumptions to return empty/some report
    mock_compile = AsyncMock(return_value="My Executive Summary\n---\nDetailed assumptions")

    with patch("armance.service.handlers._mona_proxy_checkpoint", new_callable=AsyncMock) as mock_proxy, \
         patch("armance.service.agents.judge_agent.JudgeAgent.compile_assumptions", mock_compile):
        
        # In autonomous mode, Mona is asked first. She delegates to the user by returning [ASK_USER]
        mock_proxy.return_value = "[ASK_USER] I cannot decide on database because it is critical. Which db?"

        reply = await _cmd_workflow_run(
            "check_wf", enrich_sid=None, ctx=ctx,
            skip_preflight=True, user_prompt_override="test",
            run_mode="autonomous",
        )

        # Verify that _mona_proxy_checkpoint was called
        mock_proxy.assert_called_once()
        
        # Verify that ctx.checkpoint_handler.prompt was called because of [ASK_USER] intercept
        mock_ch.prompt.assert_called_once()
        checkpoint_arg = mock_ch.prompt.call_args[0][0]
        assert checkpoint_arg.id == "check1"
        assert "I cannot decide on database because it is critical. Which db?" in checkpoint_arg.prompt

        # Verify that reply contains Mona's Executive Summary
        assert "My Executive Summary" in reply
        
        # Verify that assumptions.md was written
        run_dirs = list((armance_root / "exports" / "check_wf").glob("run-*"))
        assert len(run_dirs) == 1
        assumptions_file = run_dirs[0] / "assumptions.md"
        assert assumptions_file.exists()
        assert "Detailed assumptions" in assumptions_file.read_text(encoding="utf-8")
