"""P2 lot — model-id validation, engine ordering/cancellation, manifest
completeness, auto-Serge scoping.

- W2: recruit/swap validate model ids against the session discovery
  cache; providers without a catalogue pass (validation impossible).
- W21: auto-Serge never fires when the workflow already schedules a
  critique step; French trivial-divergence markers are recognised.
- W22: an abort mid-level cancels the in-flight sibling steps.
- W23: a level's regular steps run BEFORE its checkpoint, so the human
  answers with those outputs in hand.
- W26: the manifest lists every workflow step from the first snapshot;
  steps never reached end as `skipped`; answered checkpoints complete.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from armance.config import Config, ProviderConfig
from armance.core.models.agent import Agent
from armance.providers.base import ModelSpec
from armance.providers.discovery import _CACHE, reset_cache
from armance.service.checkpoint import CheckpointResponse
from armance.service.handlers import _cmd_workflow_run
from armance.service.llm_service import TokenLedger
from armance.service.loop_context import LoopContext
from armance.service.session import Session, SessionState


@pytest.fixture(autouse=True)
def _clean_discovery_cache():
    reset_cache()
    yield
    reset_cache()


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


def _agent(name: str, role: str, **kw) -> Agent:
    defaults = dict(
        persona="x", provider="openrouter", model="good-model",
        system_prompt="x", last_health="ok",
    )
    defaults.update(kw)
    return Agent(name=name, role=role, **defaults)


def _ctx(root: Path, cfg: Config, agents: list[Agent]) -> LoopContext:
    state = SessionState.new()
    session = Session(state, root)
    return LoopContext(
        armance_root=root, cfg=cfg, state=state, session=session,
        ledger=TokenLedger(), statuses=[], agents=agents,
    )


def _seed_catalogue(provider: str, ids: list[str]) -> None:
    _CACHE[provider] = [ModelSpec(id=i, provider=provider, tier="low") for i in ids]


def _hr(root: Path, cfg: Config):
    from armance.service.agents.recruiter_agent import RecruiterAgentService
    return RecruiterAgentService(
        agent=_agent("system-hr", "meta"), armance_root=root, config=cfg,
    )


# ---------------------------------------------------------------------------
# W2 — model-id validation
# ---------------------------------------------------------------------------


def test_recruit_rejects_model_missing_from_catalogue(root: Path, cfg: Config) -> None:
    _seed_catalogue("openrouter", ["good-model"])
    hr = _hr(root, cfg)
    yaml_text = (
        "agents:\n"
        "  - name: Nora\n    role: securite\n    persona: p\n"
        "    provider: openrouter\n    model: vertex_ai/claude3.5-sonnet-v2\n"
        "  - name: Marc\n    role: securite\n    persona: q\n"
        "    provider: openrouter\n    model: good-model\n"
    )
    created, names = hr.recruit_agents(
        yaml_text=yaml_text, role_name="specialist", agents_dir=root / "agents",
    )
    assert names == ["Marc"]
    assert not (root / "agents" / "Nora.md").exists()
    assert hr.last_rejected_models and "Nora" in hr.last_rejected_models[0]


def test_recruit_without_catalogue_passes_any_id(root: Path, cfg: Config) -> None:
    """Empty catalogue = validation impossible — never block (custom
    endpoints without /models still work, health probe catches the rest)."""
    hr = _hr(root, cfg)
    yaml_text = (
        "agents:\n"
        "  - name: Nora\n    role: securite\n    persona: p\n"
        "    provider: openrouter\n    model: anything-goes\n"
    )
    _, names = hr.recruit_agents(
        yaml_text=yaml_text, role_name="specialist", agents_dir=root / "agents",
    )
    assert names == ["Nora"]
    assert hr.last_rejected_models == []


def test_recruit_drops_invalid_boost_but_keeps_agent(root: Path, cfg: Config) -> None:
    _seed_catalogue("openrouter", ["good-model"])
    hr = _hr(root, cfg)
    yaml_text = (
        "agents:\n"
        "  - name: Nora\n    role: securite\n    persona: p\n"
        "    provider: openrouter\n    model: good-model\n"
        "    boost_provider: openrouter\n    boost_model: bogus-boost\n"
    )
    _, names = hr.recruit_agents(
        yaml_text=yaml_text, role_name="specialist", agents_dir=root / "agents",
    )
    assert names == ["Nora"]
    reloaded = Agent.load(root / "agents" / "Nora.md")
    assert not reloaded.boost_model
    assert hr.last_dropped_boosts and "Nora" in hr.last_dropped_boosts[0]


@pytest.mark.asyncio
async def test_swap_rejects_model_missing_from_catalogue(
    root: Path, cfg: Config,
) -> None:
    from armance.service.agents.agent_swap import swap_agent_model
    _seed_catalogue("openrouter", ["good-model"])
    _agent("Nora", "securite").save(root / "agents" / "Nora.md")
    res = await swap_agent_model(
        "Nora", "openrouter/bogus", None, root / "agents", cfg,
    )
    assert res.status == "bad_model"
    assert Agent.load(root / "agents" / "Nora.md").model == "good-model"


# ---------------------------------------------------------------------------
# W21 — auto-Serge scoping + FR markers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auto_serge_skipped_when_workflow_has_critique_step() -> None:
    from armance.service.workflow_hooks import check_consensus_and_maybe_invoke_serge

    steps = [
        SimpleNamespace(id=f"j{i}", kind="judge") for i in range(3)
    ] + [SimpleNamespace(id="crit", kind="critique")]
    wf = SimpleNamespace(steps=steps)
    results = {
        f"j{i}": SimpleNamespace(output="## Divergence\n\nNone identified.")
        for i in range(3)
    }
    runner = AsyncMock(return_value="pushback")
    out = await check_consensus_and_maybe_invoke_serge(
        wf, results, critique_runner=runner,
    )
    assert out is None
    runner.assert_not_awaited()


def test_french_trivial_divergence_markers() -> None:
    from armance.service.workflow_hooks import detect_empty_divergence
    assert detect_empty_divergence("## Divergence\n\nAucune.")
    assert detect_empty_divergence("## Divergence\n\nAucune divergence identifiée.")
    assert not detect_empty_divergence(
        "## Divergence\n\nSam et Claire divergent sur le chiffrage."
    )


# ---------------------------------------------------------------------------
# W22 — abort cancels in-flight siblings
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_abort_cancels_sibling_steps() -> None:
    from armance.core.models.workflow import execute_workflow, parse_workflow

    wf = parse_workflow(
        "name: w\nsteps:\n"
        "  - id: fast_fail\n    kind: task\n    role: r\n"
        "  - id: slow\n    kind: task\n    role: r\n"
    )
    slow_cancelled = asyncio.Event()
    slow_started = asyncio.Event()

    async def runner(step, prompt):
        if step.id == "fast_fail":
            await slow_started.wait()
            raise RuntimeError("abort now")
        slow_started.set()
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            slow_cancelled.set()
            raise
        return "never"

    with pytest.raises(RuntimeError):
        await execute_workflow(wf, user_prompt="t", runner=runner)
    assert slow_cancelled.is_set(), "sibling step kept running after the abort"


# ---------------------------------------------------------------------------
# W23 — regular steps run before the level's checkpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_checkpoint_sees_same_level_outputs() -> None:
    from armance.core.models.workflow import execute_workflow, parse_workflow

    wf = parse_workflow(
        "name: w\nsteps:\n"
        "  - id: work\n    kind: task\n    role: r\n"
        "  - id: gate\n    kind: human_checkpoint\n    prompt: 'ok?'\n"
    )
    seen: dict = {}

    async def runner(step, prompt):
        return f"out-{step.id}"

    async def checkpoint_handler(step, prior_outputs):
        seen.update(prior_outputs)
        return "yes"

    await execute_workflow(
        wf, user_prompt="t", runner=runner, checkpoint_handler=checkpoint_handler,
    )
    assert seen.get("work") == "out-work"


# ---------------------------------------------------------------------------
# W26 — complete manifest
# ---------------------------------------------------------------------------


def _manifest(root: Path, wf: str) -> dict:
    run_dirs = list((root / "exports" / wf).glob("run-*"))
    assert len(run_dirs) == 1
    return json.loads((run_dirs[0] / "manifest.json").read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_manifest_lists_unreached_steps_as_skipped(
    root: Path, cfg: Config, monkeypatch,
) -> None:
    """User aborts at the checkpoint → the steps behind it must still
    appear in the manifest (skipped), not vanish (runtime2 showed 9/18)."""
    (root / ".armance" / "workflows" / "wfm.yaml").write_text(
        "name: wfm\nsteps:\n"
        "  - id: s1\n    kind: task\n    role: pilote\n"
        "  - id: gate\n    kind: human_checkpoint\n    prompt: 'ok?'\n"
        "    depends_on: [s1]\n"
        "  - id: s2\n    kind: task\n    role: pilote\n    depends_on: [gate]\n"
    )
    ctx = _ctx(root, cfg, [_agent("Elise", "pilote")])
    mock_ch = AsyncMock()
    mock_ch.prompt.return_value = CheckpointResponse(content="", is_abort=True)
    ctx.checkpoint_handler = mock_ch

    async def fake_run(agent, task, *a, **kw):
        return SimpleNamespace(
            content="ok", tokens_in=1, tokens_out=1, cost_usd=None,
            finish_reason="stop",
        )

    monkeypatch.setattr("armance.service.handlers.run_specialist", fake_run)
    await _cmd_workflow_run(
        "wfm", None, ctx, skip_preflight=True,
        user_prompt_override="t", run_mode="interactive",
    )
    m = _manifest(root, "wfm")
    steps = {s["id"]: s for s in m["steps"]}
    assert set(steps) == {"s1", "gate", "s2"}
    assert steps["s1"]["status"] == "completed"
    assert steps["s2"]["status"] == "skipped"
    assert m["status"] == "canceled"


@pytest.mark.asyncio
async def test_answered_checkpoint_marked_completed_with_answerer(
    root: Path, cfg: Config, monkeypatch,
) -> None:
    (root / ".armance" / "workflows" / "wfk.yaml").write_text(
        "name: wfk\nsteps:\n"
        "  - id: gate\n    kind: human_checkpoint\n    prompt: 'ok?'\n"
    )
    ctx = _ctx(root, cfg, [])
    mock_ch = AsyncMock()
    mock_ch.prompt.return_value = CheckpointResponse(content="go", is_abort=False)
    ctx.checkpoint_handler = mock_ch
    await _cmd_workflow_run(
        "wfk", None, ctx, skip_preflight=True,
        user_prompt_override="t", run_mode="interactive",
    )
    m = _manifest(root, "wfk")
    steps = {s["id"]: s for s in m["steps"]}
    assert steps["gate"]["status"] == "completed"
    assert steps["gate"]["agent"] == "user"
