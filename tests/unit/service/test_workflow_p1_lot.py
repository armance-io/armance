"""P1 lot — real stop, boost applied in runs, repair redirect, boost probe.

- Stop: cancelling the run task finalises the manifest as `canceled`
  (the web Stop button used to be a silent no-op).
- Boost: `--deep` boosts boostable agents whose ROLE appears in the
  workflow (Kim assigns steps by role, never by `agents:` lists), and the
  runner forwards `boosted_agents` so the boost pair is actually used.
- Repair redirect: a /recruit proposing a NEW name for a role staffed by
  a SICK agent swaps that agent's model in place (name + persona kept).
- Manifest records who actually spoke (`agent` on the step record).
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from armance.config import Config, ProviderConfig
from armance.core.models.agent import Agent
from armance.service.handlers import _cmd_workflow_run
from armance.service.llm_service import TokenLedger
from armance.service.loop_context import LoopContext
from armance.service.session import Session, SessionState


@pytest.fixture(autouse=True)
def _clean_discovery_cache():
    """The recruit validator reads the discovery session cache — isolate it
    from catalogues seeded by other test modules."""
    from armance.providers.discovery import reset_cache
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
        persona="x", provider="openrouter", model="m",
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


# ---------------------------------------------------------------------------
# W17 — real stop: cancellation finalises the manifest as canceled
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancelling_run_task_finalises_manifest_canceled(
    root: Path, cfg: Config, monkeypatch,
) -> None:
    _write_wf(
        root, "wfc",
        "name: wfc\nsteps:\n  - id: s1\n    kind: task\n    role: pilote\n",
    )
    ctx = _ctx(root, cfg, [_agent("Elise", "pilote")])
    started = asyncio.Event()

    async def slow_run(agent, task, *a, **kw):
        started.set()
        await asyncio.sleep(30)
        return _report("never")

    monkeypatch.setattr("armance.service.handlers.run_specialist", slow_run)
    run_task = asyncio.create_task(_cmd_workflow_run(
        "wfc", None, ctx, skip_preflight=True,
        user_prompt_override="t", run_mode="interactive",
    ))
    await asyncio.wait_for(started.wait(), 5)
    run_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await run_task
    assert _manifest(root, "wfc")["status"] == "canceled"


# ---------------------------------------------------------------------------
# W20 — boost applied in deep runs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deep_run_boosts_agents_by_role_and_forwards_set(
    root: Path, cfg: Config, monkeypatch,
) -> None:
    _write_wf(
        root, "wfb",
        "name: wfb\nsteps:\n  - id: s1\n    kind: task\n    role: pilote\n",
    )
    boostable = _agent(
        "Elise", "pilote",
        boost_provider="openrouter", boost_model="big-model",
    )
    ctx = _ctx(root, cfg, [boostable])
    seen: dict = {}

    async def fake_run(agent, task, *a, **kw):
        seen["boosted_agents"] = set(kw.get("boosted_agents") or set())
        return _report("ok")

    monkeypatch.setattr("armance.service.handlers.run_specialist", fake_run)
    await _cmd_workflow_run(
        "wfb", None, ctx, skip_preflight=True,
        user_prompt_override="t", run_mode="interactive", depth="deep",
    )
    assert "Elise" in ctx.state.boosted_agents
    assert "Elise" in seen["boosted_agents"]


@pytest.mark.asyncio
async def test_quick_run_does_not_boost(
    root: Path, cfg: Config, monkeypatch,
) -> None:
    _write_wf(
        root, "wfq",
        "name: wfq\nsteps:\n  - id: s1\n    kind: task\n    role: pilote\n",
    )
    boostable = _agent(
        "Elise", "pilote",
        boost_provider="openrouter", boost_model="big-model",
    )
    ctx = _ctx(root, cfg, [boostable])

    async def fake_run(agent, task, *a, **kw):
        return _report("ok")

    monkeypatch.setattr("armance.service.handlers.run_specialist", fake_run)
    await _cmd_workflow_run(
        "wfq", None, ctx, skip_preflight=True,
        user_prompt_override="t", run_mode="interactive", depth="quick",
    )
    assert "Elise" not in ctx.state.boosted_agents


# ---------------------------------------------------------------------------
# Manifest — who actually spoke
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_manifest_records_the_agent_who_spoke(
    root: Path, cfg: Config, monkeypatch,
) -> None:
    """Failover-aware: Nora fails, Marc takes over → manifest says Marc."""
    _write_wf(
        root, "wfa",
        "name: wfa\nsteps:\n  - id: s1\n    kind: task\n    role: securite\n",
    )
    ctx = _ctx(root, cfg, [_agent("Nora", "securite"), _agent("Marc", "securite")])

    async def fake_run(agent, task, *a, **kw):
        if agent.name == "Nora":
            raise RuntimeError("400")
        return _report("ok")

    monkeypatch.setattr("armance.service.handlers.run_specialist", fake_run)
    await _cmd_workflow_run(
        "wfa", None, ctx, skip_preflight=True,
        user_prompt_override="t", run_mode="interactive",
    )
    steps = {s["id"]: s for s in _manifest(root, "wfa")["steps"]}
    assert steps["s1"]["agent"] == "Marc"


# ---------------------------------------------------------------------------
# W3 — repair redirect in recruit_agents
# ---------------------------------------------------------------------------


def _hr(root: Path, cfg: Config):
    from armance.service.agents.recruiter_agent import RecruiterAgentService
    hr_agent = _agent("system-hr", "meta")
    return RecruiterAgentService(agent=hr_agent, armance_root=root, config=cfg)


def test_recruit_new_name_for_sick_role_repairs_in_place(
    root: Path, cfg: Config,
) -> None:
    """runtime2 regression: Malik renamed Leo → 'Anais' for the same role
    instead of swapping Leo's model. The redirect must absorb the new
    name into the sick agent: same file, new model, persona preserved."""
    agents_dir = root / "agents"
    leo = _agent("Leo", "methodologue", model="dead-model", last_health="error:400")
    leo.system_prompt = "PERSONA-LEO"
    leo.save(agents_dir / "Leo.md")

    hr = _hr(root, cfg)
    yaml_text = (
        "agents:\n"
        "  - name: Anais\n"
        "    role: methodologue\n"
        "    persona: méthodologue preuves\n"
        "    provider: openrouter\n"
        "    model: good-model\n"
    )
    created, created_names = hr.recruit_agents(
        yaml_text=yaml_text, role_name="specialist", agents_dir=agents_dir,
    )

    assert not (agents_dir / "Anais.md").exists()
    reloaded = Agent.load(agents_dir / "Leo.md")
    assert reloaded.model == "good-model"
    assert reloaded.system_prompt == "PERSONA-LEO"
    assert hr.last_repaired_names == ["Leo"]
    assert created_names == ["Leo"]


def test_recruit_new_name_for_healthy_role_still_creates(
    root: Path, cfg: Config,
) -> None:
    """No sick peer → a genuinely new profile is created as before."""
    agents_dir = root / "agents"
    _agent("Leo", "methodologue", last_health="ok").save(agents_dir / "Leo.md")

    hr = _hr(root, cfg)
    yaml_text = (
        "agents:\n"
        "  - name: Anais\n"
        "    role: methodologue\n"
        "    persona: méthodologue preuves\n"
        "    provider: openrouter\n"
        "    model: good-model\n"
    )
    hr.recruit_agents(
        yaml_text=yaml_text, role_name="specialist", agents_dir=agents_dir,
    )
    assert (agents_dir / "Anais.md").exists()
    assert hr.last_repaired_names == []


# ---------------------------------------------------------------------------
# W4 — boost pair probed too
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_probe_covers_boost_pair(monkeypatch) -> None:
    from armance.service.agents import health as health_mod

    calls: list[str] = []

    async def fake_probe(provider, model, cfg, timeout):
        calls.append(model)
        return ("ok", "") if model == "base-m" else ("error:400", "boom")

    monkeypatch.setattr(health_mod, "_probe", fake_probe)
    agent = _agent(
        "Elise", "pilote", model="base-m",
        boost_provider="openrouter", boost_model="boost-m",
    )
    result = await health_mod.check_agent_health(agent, None)
    assert calls == ["base-m", "boost-m"]
    assert result.ok is True
    assert result.boost_ok is False
    assert result.boost_status == "error:400"
