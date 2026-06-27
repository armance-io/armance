"""End-to-end MVP: Malik recruits → Kim designs YAML → workflow runs.

Reproduces the exact scenario from session 23cb54b372b2 (tmp/) with the
LLM mocked. Guards three things at once:

  1. Malik's `domain:` is normalised to a short slug at recruit time.
  2. Kim's workflow YAML is accepted whether she writes `role:` or
     `domain:`, and even if she puts an agent name in `role:`.
  3. The workflow runner resolves steps to agents by role match, both
     for user-recruited agents and for staff (`mona` / `serge`).

No network call. No filesystem assumption beyond `tmp_path`.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from armance.config import Config, ProviderConfig
from armance.core.models.agent import Agent
from armance.core.models.workflow import load_workflow


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


def test_malik_recruit_normalises_french_domain(armance_root: Path, cfg: Config) -> None:
    """Malik writes `domain: historien des temps modernes` → recruit_agents
    slugifies it down to a short ASCII role like `historien-temps`."""
    from armance.service.agents.recruiter_agent import RecruiterAgentService
    from armance.core.models.agent import Agent as AgentModel

    malik_agent = AgentModel(
        name="system-hr", role="meta", persona="recruiter",
        provider="openrouter", model="x", system_prompt="malik",
    )
    hr = RecruiterAgentService(agent=malik_agent, armance_root=armance_root, config=cfg)

    yaml_text = """
agents:
  - name: Theodore
    persona: positiviste
    domain: Historien des temps modernes
    description: archives primaires
    provider: openrouter
    model: google/gemma-2-9b-it:free
"""
    created, _ = hr.recruit_agents(
        yaml_text=yaml_text, role_name="specialist",
        agents_dir=armance_root / "agents",
    )
    assert len(created) == 1
    a = created[0]
    # `é` stripped, "des" stop-word dropped, kebab-case.
    assert a.role.startswith("historien")
    assert "é" not in a.role
    assert "des" not in a.role.split("-")
    assert a.role == a.role


def test_kim_yaml_with_role_alias_validates(armance_root: Path, cfg: Config) -> None:
    """Kim emits `role:` (user-facing alias) — skill accepts it."""
    from armance.service.skills.design_workflow import DesignWorkflowSkill

    theodore = Agent(
        name="Theodore", role="historian", persona="positivist",
        provider="openrouter", model="x", system_prompt="t",
    )
    skill = DesignWorkflowSkill(
        armance_root=armance_root, config=cfg, agents=[theodore],
    )
    kim_reply = (
        "Voici :\n\n"
        "```yaml\n"
        "name: dossier-historique\n"
        "strategy: rapide\n"
        "steps:\n"
        "  - id: research\n"
        "    kind: task\n"
        "    role: historian\n"
        "    depends_on: []\n"
        "  - id: judge\n"
        "    kind: judge\n"
        "    role: mona\n"
        "    depends_on: [research]\n"
        "```\n"
    )
    out = skill.run(args=kim_reply)
    assert "créé" in out.lower() or "created" in out.lower()

    yamls = list((armance_root / ".armance" / "workflows").glob("*.yaml"))
    assert yamls
    wf = load_workflow(yamls[0])
    assert wf.steps[0].role == "historian"
    assert wf.steps[1].role == "mona"


def test_kim_yaml_with_agent_name_in_role_is_remapped(
    armance_root: Path, cfg: Config,
) -> None:
    """Kim confuses agent name and role (writes `role: theodore`) —
    the skill remaps to the agent's actual role and accepts the workflow."""
    from armance.service.skills.design_workflow import DesignWorkflowSkill

    theodore = Agent(
        name="Theodore", role="historian", persona="positivist",
        provider="openrouter", model="x", system_prompt="t",
    )
    skill = DesignWorkflowSkill(
        armance_root=armance_root, config=cfg, agents=[theodore],
    )
    kim_reply = (
        "```yaml\n"
        "name: dossier-historique\n"
        "strategy: rapide\n"
        "steps:\n"
        "  - id: research\n"
        "    kind: task\n"
        "    role: theodore\n"
        "    depends_on: []\n"
        "  - id: judge\n"
        "    kind: judge\n"
        "    role: mona\n"
        "    depends_on: [research]\n"
        "```\n"
    )
    out = skill.run(args=kim_reply)
    assert "créé" in out.lower() or "created" in out.lower(), out

    yamls = list((armance_root / ".armance" / "workflows").glob("*.yaml"))
    assert yamls
    wf = load_workflow(yamls[0])
    # Step `research` had role=`theodore` (a name) — remapped to historian.
    assert wf.steps[0].role == "historian"


def test_legacy_yaml_with_domain_key_still_loads(
    armance_root: Path, cfg: Config,
) -> None:
    """Old workflows on disk with `domain:` keep working — the model accepts
    `domain` as a synonym for `role`."""
    wf_file = armance_root / ".armance" / "workflows" / "legacy.yaml"
    wf_file.write_text(
        "name: legacy\n"
        "steps:\n"
        "  - id: a\n"
        "    kind: task\n"
        "    domain: historian\n"
        "    depends_on: []\n"
    )
    wf = load_workflow(wf_file)
    assert wf.steps[0].role == "historian"
    assert wf.steps[0].role == "historian"


@pytest.mark.asyncio
async def test_workflow_run_resolves_steps_to_agents(
    armance_root: Path, cfg: Config,
) -> None:
    """A workflow whose steps reference roster roles (and `mona`/`serge`)
    runs without a single 'no agent for role' error."""
    # Recruit Theodore (historian) on disk so ctx.agents picks him up.
    theodore_path = armance_root / "agents" / "Theodore.md"
    theodore = Agent(
        name="Theodore", role="historian",
        persona="positivist", provider="openrouter",
        model="google/gemma-2-9b-it:free", system_prompt="historian",
    )
    theodore.save(theodore_path)

    # Write a minimal workflow YAML — historian + mona + serge.
    wf_path = armance_root / ".armance" / "workflows" / "mvp.yaml"
    wf_path.write_text(
        "name: mvp\n"
        "strategy: rapide\n"
        "steps:\n"
        "  - id: research\n"
        "    kind: task\n"
        "    role: historian\n"
        "    depends_on: []\n"
        "  - id: critique\n"
        "    kind: critique\n"
        "    role: serge\n"
        "    depends_on: [research]\n"
        "  - id: judge\n"
        "    kind: judge\n"
        "    role: mona\n"
        "    depends_on: [critique]\n"
    )

    # Stub run_specialist so the executor doesn't make network calls.
    fake_report = MagicMock()
    fake_report.content = "stub output"
    with patch(
        "armance.service.handlers.run_specialist",
        new=AsyncMock(return_value=fake_report),
    ):
        from armance.service.handlers import _cmd_workflow_run
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
            agents=[theodore],
        )

        reply = await _cmd_workflow_run(
            "mvp", enrich_sid=None, ctx=ctx,
            skip_preflight=True, user_prompt_override="test",
        )

    # No 'no agent' / abort message in the output.
    low = reply.lower()
    assert "no agent" not in low
    assert "aucun agent" not in low
    assert "abort" not in low
    # T5: reply is now a preview + Mona offer, not full content dump
    assert "run" in low  # run_finished / run_preview key
    assert "mona" in low  # mona offer present
