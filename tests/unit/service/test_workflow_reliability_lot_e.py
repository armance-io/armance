"""Lot E — reliability of contradictory pairs, run-error transparency, and
the broken-workflow validation gate.

Design: roadmap/03_workflow_quality_refonte.md §7.

1. A contradictory second-regard candidate that fails must surface a VISIBLE
   warning in the conversation AND the manifest — not vanish silently.
2. A step that ends up absent carries the REAL upstream error into its note
   and the manifest (no opaque "step X failed").
3. The A2 validation catches the two bugs in the real broken workflow
   (`reponse-technique-short.yaml`): a `depends_on` → step that exists
   nowhere, and a `role` that is actually another step's id.
"""
from __future__ import annotations

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
from armance.service.workflow_validation import validate_step_structure


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
        armance_root=root, cfg=cfg, state=state, session=session,
        ledger=TokenLedger(), statuses=[], agents=agents,
    )


def _write_wf(root: Path, name: str, body: str) -> None:
    (root / ".armance" / "workflows" / f"{name}.yaml").write_text(body)


def _report(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        content=text, tokens_in=1, tokens_out=1, cost_usd=None, finish_reason="stop",
    )


def _manifest(root: Path, wf: str) -> dict:
    run_dirs = list((root / "exports" / wf).glob("run-*"))
    assert len(run_dirs) == 1
    return json.loads((run_dirs[0] / "manifest.json").read_text(encoding="utf-8"))


def _steps_by_id(m: dict) -> dict[str, dict]:
    return {s["id"]: s for s in m["steps"]}


# --- E.1 — a failed contradictory candidate warns visibly ------------------

@pytest.mark.asyncio
async def test_failed_candidate_warns_in_conversation_and_manifest(
    root: Path, cfg: Config, monkeypatch,
) -> None:
    """First candidate (Claire) errors, same-role peer (Nora) takes over.
    The step completes, but Claire's lost second regard must be visible."""
    _write_wf(
        root, "wfe1",
        "name: wfe1\nsteps:\n  - id: s1\n    kind: task\n    role: securite\n",
    )
    claire = _agent("Claire", "securite")
    nora = _agent("Nora", "securite")
    ctx = _ctx(root, cfg, [claire, nora])

    async def fake_run(agent, task, *a, **kw):
        if agent.name == "Claire":
            raise RuntimeError("erreur 400")
        return _report("out-nora")

    monkeypatch.setattr("armance.service.handlers.run_specialist", fake_run)
    await _cmd_workflow_run(
        "wfe1", None, ctx, skip_preflight=True,
        user_prompt_override="t", run_mode="interactive",
    )

    # Visible in conversation: names the lost candidate + the real error.
    joined = "\n".join(ctx.output_lines)
    assert "Claire" in joined
    assert "400" in joined

    m = _manifest(root, "wfe1")
    s1 = _steps_by_id(m)["s1"]
    # Step still completed (Nora took over) but carries the warning.
    assert s1["status"] == "completed"
    assert s1["agent"] == "Nora"
    assert any("Claire" in w for w in s1.get("warnings", []))


# --- E.2 — real error propagated when the step ends up absent --------------

@pytest.mark.asyncio
async def test_absent_step_carries_real_error(
    root: Path, cfg: Config, monkeypatch,
) -> None:
    _write_wf(
        root, "wfe2",
        "name: wfe2\nsteps:\n  - id: s1\n    kind: task\n    role: securite\n",
    )
    ctx = _ctx(root, cfg, [_agent("Nora", "securite")])

    async def fake_run(agent, task, *a, **kw):
        raise RuntimeError("openrouter 400 model_not_found")

    monkeypatch.setattr("armance.service.handlers.run_specialist", fake_run)
    await _cmd_workflow_run(
        "wfe2", None, ctx, skip_preflight=True,
        user_prompt_override="t", run_mode="interactive",
    )
    m = _manifest(root, "wfe2")
    s1 = _steps_by_id(m)["s1"]
    assert s1["status"] == "failed"
    # The manifest carries the REAL provider error, not an opaque "failed".
    assert "model_not_found" in (s1["error"] or "")


# --- E.3 — validation catches the broken real workflow ---------------------

def test_validation_catches_dep_on_nonexistent_step() -> None:
    steps = [
        {"id": "qualifier_ia", "kind": "task", "role": "ml",
         "depends_on": ["extraire_exigences"]},
    ]
    err = validate_step_structure(steps)
    assert err
    assert "extraire_exigences" in err


def test_validation_catches_role_equals_step_id() -> None:
    steps = [
        {"id": "synthese_mona", "kind": "judge", "role": "mona", "depends_on": []},
        {"id": "revision_finale", "kind": "task", "role": "synthese_mona",
         "depends_on": ["synthese_mona"]},
    ]
    err = validate_step_structure(steps)
    assert err
    assert "synthese_mona" in err


def test_validation_passes_on_sound_structure() -> None:
    steps = [
        {"id": "a", "kind": "task", "role": "ml", "depends_on": []},
        {"id": "b", "kind": "judge", "role": "mona", "depends_on": ["a"]},
    ]
    assert validate_step_structure(steps) == ""
