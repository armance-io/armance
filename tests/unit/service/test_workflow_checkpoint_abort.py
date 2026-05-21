"""User-driven abort at a human_checkpoint must stop the run AND finalise
the manifest with status="canceled". Previous behaviour: step was marked
canceled but downstream steps still ran and `manifest.status` ended up
`completed`. That left the web layer (and humans) unable to tell whether
a run finished cleanly or was aborted mid-flight.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from armance.config import Config, ProviderConfig
from armance.service.checkpoint import CheckpointResponse
from armance.service.handlers import _cmd_workflow_run
from armance.service.llm_service import TokenLedger
from armance.service.loop_context import LoopContext
from armance.service.session import Session, SessionState


@pytest.fixture
def cfg() -> Config:
    return Config(
        providers=[ProviderConfig(name="openrouter", api_key="t")],
        default_provider="openrouter",
        default_model="openai/gpt-4o-mini",
    )


@pytest.fixture
def root(tmp_path: Path) -> Path:
    (tmp_path / "agents").mkdir(parents=True)
    (tmp_path / ".armance" / "workflows").mkdir(parents=True)
    (tmp_path / "context" / "L0").mkdir(parents=True)
    return tmp_path


def _write_wf(root: Path, name: str, body: str) -> Path:
    wf_path = root / ".armance" / "workflows" / f"{name}.yaml"
    wf_path.write_text(body)
    return wf_path


@pytest.mark.asyncio
async def test_interactive_abort_finalises_canceled(root: Path, cfg: Config):
    _write_wf(
        root,
        "abort_wf",
        "name: abort_wf\n"
        "strategy: rapide\n"
        "steps:\n"
        "  - id: gate\n"
        "    kind: human_checkpoint\n"
        "    prompt: 'continue?'\n",
    )

    state = SessionState.new()
    session = Session(state, root)
    ctx = LoopContext(
        armance_root=root,
        cfg=cfg,
        state=state,
        session=session,
        ledger=TokenLedger(),
        statuses=[],
        agents=[],
    )

    mock_ch = AsyncMock()
    mock_ch.prompt.return_value = CheckpointResponse(content="", is_abort=True)
    ctx.checkpoint_handler = mock_ch

    reply = await _cmd_workflow_run(
        "abort_wf",
        enrich_sid=None,
        ctx=ctx,
        skip_preflight=True,
        user_prompt_override="test",
        run_mode="interactive",
    )

    # User-facing reply mentions abort
    assert "abort" in reply.lower() or "interrompu" in reply.lower()

    # Manifest status must be `canceled`
    run_dirs = list((root / "exports" / "abort_wf").glob("run-*"))
    assert len(run_dirs) == 1
    manifest_path = run_dirs[0] / "manifest.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "canceled", (
        f"Expected canceled, got {manifest['status']}. "
        "Aborting a checkpoint must propagate to the run manifest."
    )


@pytest.mark.asyncio
async def test_autonomous_ask_user_abort_finalises_canceled(root: Path, cfg: Config):
    """Autonomous mode: Mona may delegate via [ASK_USER]; if the user
    then aborts via the checkpoint handler, the run must finalise canceled.
    """
    _write_wf(
        root,
        "auto_abort_wf",
        "name: auto_abort_wf\n"
        "strategy: rapide\n"
        "steps:\n"
        "  - id: gate\n"
        "    kind: human_checkpoint\n"
        "    prompt: 'continue?'\n",
    )

    state = SessionState.new()
    session = Session(state, root)
    ctx = LoopContext(
        armance_root=root,
        cfg=cfg,
        state=state,
        session=session,
        ledger=TokenLedger(),
        statuses=[],
        agents=[],
    )

    mock_ch = AsyncMock()
    mock_ch.prompt.return_value = CheckpointResponse(content="", is_abort=True)
    ctx.checkpoint_handler = mock_ch

    from unittest.mock import patch

    with patch(
        "armance.service.handlers._mona_proxy_checkpoint",
        new_callable=AsyncMock,
        return_value="[ASK_USER] Critical unknown — please decide.",
    ):
        reply = await _cmd_workflow_run(
            "auto_abort_wf",
            enrich_sid=None,
            ctx=ctx,
            skip_preflight=True,
            user_prompt_override="test",
            run_mode="autonomous",
        )

    run_dirs = list((root / "exports" / "auto_abort_wf").glob("run-*"))
    assert len(run_dirs) == 1
    manifest = json.loads(
        (run_dirs[0] / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["status"] == "canceled"
    assert "abort" in reply.lower() or "interrompu" in reply.lower()
