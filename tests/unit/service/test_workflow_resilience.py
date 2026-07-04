"""Workflow run resilience (W5/W6/W8/W9).

Team metaphor: an unavailable agent is *absent* — the run warns and
continues without that contribution, it does not die.

- W5: step agent resolution prefers healthy agents of the role, and
  fails over to another same-role agent when the first call raises.
- W6: a failed step becomes an "absent contribution" note; downstream
  steps still run (the note flows into their prompts). Only 3+
  consecutive absences abort the run (provider down).
- W8: human_checkpoint steps get a default question when the YAML has
  no prompt; after a user abort, later checkpoints are not prompted.
- W9: the pre-run health gate only blocks when NO required role has a
  healthy agent; a sick agent whose role has a healthy peer never
  blocks the run.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from armance.config import Config, ProviderConfig
from armance.core.models.agent import Agent
from armance.service.checkpoint import CheckpointResponse
from armance.service.handlers import _cmd_workflow_run, _step_agent_candidates
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


def _agent(name: str, role: str, *, health: str | None = "ok") -> Agent:
    return Agent(
        name=name, role=role, persona="x",
        provider="openrouter", model="m", system_prompt="x",
        last_health=health,
    )


def _ctx(root: Path, cfg: Config, agents: list[Agent]) -> LoopContext:
    state = SessionState.new()
    session = Session(state, root)
    return LoopContext(
        armance_root=root,
        cfg=cfg,
        state=state,
        session=session,
        ledger=TokenLedger(),
        statuses=[],
        agents=agents,
    )


def _write_wf(root: Path, name: str, body: str) -> None:
    (root / ".armance" / "workflows" / f"{name}.yaml").write_text(body)


def _report(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        content=text, tokens_in=1, tokens_out=1, cost_usd=None,
        finish_reason="stop",
    )


def _manifest(root: Path, wf: str) -> dict:
    run_dirs = list((root / "exports" / wf).glob("run-*"))
    assert len(run_dirs) == 1
    return json.loads((run_dirs[0] / "manifest.json").read_text(encoding="utf-8"))


def _steps_by_id(manifest: dict) -> dict[str, dict]:
    return {s["id"]: s for s in manifest["steps"]}


# ---------------------------------------------------------------------------
# W5 — health-aware candidate resolution
# ---------------------------------------------------------------------------


def test_candidates_prefer_healthy_agents(root: Path, cfg: Config) -> None:
    nora = _agent("Nora", "securite", health="error:400")
    marc = _agent("Marc", "securite", health="ok")
    ctx = _ctx(root, cfg, [nora, marc])
    cands = _step_agent_candidates("securite", ctx)
    assert [a.name for a in cands] == ["Marc"]


def test_candidates_fall_back_to_unhealthy_when_no_healthy(
    root: Path, cfg: Config,
) -> None:
    """A fully-sick role is still *attempted* (probe may be stale) — the
    absence path catches the failure at run time."""
    nora = _agent("Nora", "securite", health="error:400")
    ctx = _ctx(root, cfg, [nora])
    cands = _step_agent_candidates("securite", ctx)
    assert [a.name for a in cands] == ["Nora"]


def test_candidates_never_probed_counts_as_healthy(root: Path, cfg: Config) -> None:
    old = _agent("Old", "securite", health=None)
    ctx = _ctx(root, cfg, [old])
    assert [a.name for a in _step_agent_candidates("securite", ctx)] == ["Old"]


@pytest.mark.asyncio
async def test_run_uses_healthy_agent_over_sick_first_match(
    root: Path, cfg: Config, monkeypatch,
) -> None:
    """runtime2 regression: Nora (error:400) listed before Marc (ok) —
    the run must pick Marc, not the first roster match."""
    _write_wf(
        root, "wf1",
        "name: wf1\nsteps:\n  - id: s1\n    kind: task\n    role: securite\n",
    )
    nora = _agent("Nora", "securite", health="error:400")
    marc = _agent("Marc", "securite", health="ok")
    ctx = _ctx(root, cfg, [nora, marc])
    called: list[str] = []

    async def fake_run(agent, task, *a, **kw):
        called.append(agent.name)
        return _report(f"out-{agent.name}")

    monkeypatch.setattr("armance.service.handlers.run_specialist", fake_run)
    await _cmd_workflow_run(
        "wf1", None, ctx, skip_preflight=True,
        user_prompt_override="t", run_mode="interactive",
    )
    assert called == ["Marc"]
    assert _manifest(root, "wf1")["status"] == "completed"


@pytest.mark.asyncio
async def test_runtime_failover_to_same_role_peer(
    root: Path, cfg: Config, monkeypatch,
) -> None:
    """First healthy agent raises at run time → the same-role peer takes
    the step; the step completes."""
    _write_wf(
        root, "wf2",
        "name: wf2\nsteps:\n  - id: s1\n    kind: task\n    role: securite\n",
    )
    a1 = _agent("Nora", "securite")
    a2 = _agent("Marc", "securite")
    ctx = _ctx(root, cfg, [a1, a2])
    called: list[str] = []

    async def fake_run(agent, task, *a, **kw):
        called.append(agent.name)
        if agent.name == "Nora":
            raise RuntimeError("400 model gone")
        return _report("marc-out")

    monkeypatch.setattr("armance.service.handlers.run_specialist", fake_run)
    await _cmd_workflow_run(
        "wf2", None, ctx, skip_preflight=True,
        user_prompt_override="t", run_mode="interactive",
    )
    assert called == ["Nora", "Marc"]
    m = _manifest(root, "wf2")
    assert m["status"] == "completed"
    assert _steps_by_id(m)["s1"]["status"] == "completed"


# ---------------------------------------------------------------------------
# W6 — absence, not abort
# ---------------------------------------------------------------------------

_WF_DIAMOND = (
    "name: wf3\n"
    "steps:\n"
    "  - id: sick\n    kind: task\n    role: securite\n"
    "  - id: indep\n    kind: task\n    role: pilote\n"
    "  - id: downstream\n    kind: task\n    role: pilote\n"
    "    depends_on: [sick, indep]\n"
)


@pytest.mark.asyncio
async def test_failed_step_does_not_kill_the_run(
    root: Path, cfg: Config, monkeypatch,
) -> None:
    _write_wf(root, "wf3", _WF_DIAMOND)
    ctx = _ctx(root, cfg, [_agent("Nora", "securite"), _agent("Elise", "pilote")])
    prompts: dict[str, str] = {}

    async def fake_run(agent, task, *a, **kw):
        if agent.name == "Nora":
            raise RuntimeError("boom 400")
        prompts[task.role] = task.prompt
        return _report(f"out-{agent.name}")

    monkeypatch.setattr("armance.service.handlers.run_specialist", fake_run)
    reply = await _cmd_workflow_run(
        "wf3", None, ctx, skip_preflight=True,
        user_prompt_override="t", run_mode="interactive",
    )
    m = _manifest(root, "wf3")
    steps = _steps_by_id(m)
    assert m["status"] == "completed"
    assert steps["sick"]["status"] == "failed"
    assert steps["indep"]["status"] == "completed"
    # Downstream ran (not skipped) and its prompt carries the absence note.
    assert steps["downstream"]["status"] == "completed"
    assert "sick" in prompts.get("pilote", "")
    # The user is told which contribution is missing.
    assert "sick" in reply


@pytest.mark.asyncio
async def test_three_consecutive_absences_abort_run(
    root: Path, cfg: Config, monkeypatch,
) -> None:
    """Circuit breaker: provider down (every step failing) must not burn
    through an 18-step workflow."""
    body = "name: wf4\nsteps:\n" + "".join(
        f"  - id: s{i}\n    kind: task\n    role: securite\n"
        + (f"    depends_on: [s{i-1}]\n" if i else "")
        for i in range(4)
    )
    _write_wf(root, "wf4", body)
    ctx = _ctx(root, cfg, [_agent("Nora", "securite")])

    async def fake_run(agent, task, *a, **kw):
        raise RuntimeError("endpoint down")

    monkeypatch.setattr("armance.service.handlers.run_specialist", fake_run)
    await _cmd_workflow_run(
        "wf4", None, ctx, skip_preflight=True,
        user_prompt_override="t", run_mode="interactive",
    )
    m = _manifest(root, "wf4")
    assert m["status"] == "failed"
    # The 4th step was never attempted.
    assert len([s for s in m["steps"] if s["status"] == "failed"]) == 3


# ---------------------------------------------------------------------------
# W8 — checkpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_checkpoint_without_prompt_gets_default_question(
    root: Path, cfg: Config,
) -> None:
    _write_wf(
        root, "wf5",
        "name: wf5\nsteps:\n  - id: gate\n    kind: human_checkpoint\n",
    )
    ctx = _ctx(root, cfg, [])
    mock_ch = AsyncMock()
    mock_ch.prompt.return_value = CheckpointResponse(content="ok", is_abort=False)
    ctx.checkpoint_handler = mock_ch
    await _cmd_workflow_run(
        "wf5", None, ctx, skip_preflight=True,
        user_prompt_override="t", run_mode="interactive",
    )
    checkpoint = mock_ch.prompt.call_args[0][0]
    assert checkpoint.prompt.strip(), "empty checkpoint question shown to user"
    assert "gate" in checkpoint.prompt


@pytest.mark.asyncio
async def test_checkpoints_after_user_abort_are_not_prompted(
    root: Path, cfg: Config,
) -> None:
    _write_wf(
        root, "wf6",
        "name: wf6\n"
        "steps:\n"
        "  - id: gate1\n    kind: human_checkpoint\n    prompt: 'q1'\n"
        "  - id: gate2\n    kind: human_checkpoint\n    prompt: 'q2'\n"
        "    depends_on: [gate1]\n",
    )
    ctx = _ctx(root, cfg, [])
    mock_ch = AsyncMock()
    mock_ch.prompt.return_value = CheckpointResponse(content="", is_abort=True)
    ctx.checkpoint_handler = mock_ch
    await _cmd_workflow_run(
        "wf6", None, ctx, skip_preflight=True,
        user_prompt_override="t", run_mode="interactive",
    )
    assert mock_ch.prompt.call_count == 1
    assert _manifest(root, "wf6")["status"] == "canceled"


# ---------------------------------------------------------------------------
# W9 — degraded health gate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gate_does_not_block_when_role_has_healthy_peer(
    root: Path, cfg: Config, monkeypatch,
) -> None:
    _write_wf(
        root, "wf7",
        "name: wf7\nsteps:\n  - id: s1\n    kind: task\n    role: securite\n",
    )
    ctx = _ctx(root, cfg, [
        _agent("Nora", "securite", health="error:400"),
        _agent("Marc", "securite", health="ok"),
    ])

    async def fake_run(agent, task, *a, **kw):
        return _report("ok")

    monkeypatch.setattr("armance.service.handlers.run_specialist", fake_run)
    await _cmd_workflow_run(
        "wf7", None, ctx, skip_preflight=True,
        user_prompt_override="t", run_mode="interactive",
    )
    # Run happened — a run dir was minted and completed.
    assert _manifest(root, "wf7")["status"] == "completed"


@pytest.mark.asyncio
async def test_gate_blocks_when_no_required_role_is_staffable(
    root: Path, cfg: Config,
) -> None:
    _write_wf(
        root, "wf8",
        "name: wf8\nsteps:\n  - id: s1\n    kind: task\n    role: securite\n",
    )
    ctx = _ctx(root, cfg, [_agent("Nora", "securite", health="error:400")])
    reply = await _cmd_workflow_run(
        "wf8", None, ctx, skip_preflight=True,
        user_prompt_override="t", run_mode="interactive",
    )
    assert "Nora" in reply
    assert not (root / "exports" / "wf8").exists()


@pytest.mark.asyncio
async def test_gate_warns_but_continues_on_partially_sick_roster(
    root: Path, cfg: Config, monkeypatch,
) -> None:
    """One role fully sick + one role healthy → run continues; the sick
    role is attempted (stale probe) and falls to the absence path."""
    _write_wf(
        root, "wf9",
        "name: wf9\n"
        "steps:\n"
        "  - id: s1\n    kind: task\n    role: securite\n"
        "  - id: s2\n    kind: task\n    role: pilote\n",
    )
    ctx = _ctx(root, cfg, [
        _agent("Nora", "securite", health="error:400"),
        _agent("Elise", "pilote", health="ok"),
    ])

    async def fake_run(agent, task, *a, **kw):
        if agent.name == "Nora":
            raise RuntimeError("still 400")
        return _report("ok")

    monkeypatch.setattr("armance.service.handlers.run_specialist", fake_run)
    await _cmd_workflow_run(
        "wf9", None, ctx, skip_preflight=True,
        user_prompt_override="t", run_mode="interactive",
    )
    m = _manifest(root, "wf9")
    steps = _steps_by_id(m)
    assert m["status"] == "completed"
    assert steps["s1"]["status"] == "failed"
    assert steps["s2"]["status"] == "completed"
