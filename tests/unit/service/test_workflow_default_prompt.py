"""Default prompt composition + scope injection — the root cause behind
the disaster runs where specialists answered with their persona seed only.
"""
from __future__ import annotations

from armance.core.models.workflow import (
    StepResult,
    Workflow,
    WorkflowStep,
    _compose_default_prompt,
)


def _wf(scope: str = "") -> Workflow:
    return Workflow(
        name="test", scope=scope,
        steps=[
            WorkflowStep(id="research", kind="task", role="historian"),
            WorkflowStep(id="judge", kind="judge", role="mona",
                         depends_on=["research"]),
        ],
    )


def test_task_step_prompt_contains_scope_and_instructions() -> None:
    wf = _wf("produce a sourced 5000-word dossier on France-Scotland conflicts")
    prompt = _compose_default_prompt(
        wf, wf.steps[0], user_prompt="préparer la conférence", results={},
    )
    assert "5000-word" in prompt
    assert "Scope" in prompt
    # Task instructions push for substantive output, not 1-line persona reply.
    assert "500" in prompt or "1000" in prompt or "2000" in prompt
    assert "Do NOT just acknowledge" in prompt


def test_judge_step_pulls_in_upstream_outputs() -> None:
    wf = _wf("dossier historique")
    results = {"research": StepResult(id="research", output="Long research text.")}
    prompt = _compose_default_prompt(
        wf, wf.steps[1], user_prompt="préparer", results=results,
    )
    assert "Long research text." in prompt
    assert "Synthesise" in prompt or "synthesise" in prompt.lower()


def test_critique_step_warns_to_stay_in_scope() -> None:
    wf = Workflow(
        name="t", scope="dossier historique uniquement",
        steps=[WorkflowStep(id="c", kind="critique", role="serge")],
    )
    prompt = _compose_default_prompt(wf, wf.steps[0], user_prompt="x", results={})
    assert "scope" in prompt.lower()
    assert "Stress-test" in prompt or "stress" in prompt.lower()


def test_empty_scope_still_produces_useful_prompt() -> None:
    """Even with no scope set, the prompt must still tell the agent to
    produce substantive content — otherwise we regress to the 1-line
    persona-seed-only disaster."""
    wf = _wf("")
    prompt = _compose_default_prompt(
        wf, wf.steps[0], user_prompt="préparer la conférence", results={},
    )
    assert "préparer la conférence" in prompt
    assert "Do NOT just acknowledge" in prompt


def test_upstream_section_instructs_extend_not_rewrite() -> None:
    """A3 — the upstream section header must tell the agent to extend the
    prior deliverable, not restate/rewrite it (root cause of the 5
    specialists each re-writing a full memo in the 353-miroirs run)."""
    wf = _wf("dossier historique")
    results = {"research": StepResult(id="research", output="Long research text.")}
    prompt = _compose_default_prompt(
        wf, wf.steps[1], user_prompt="préparer", results=results,
    )
    assert "Deliverable from step `research`" in prompt
    assert "extend it" in prompt
    assert "do NOT rewrite or restate it" in prompt


def test_task_step_warns_against_standalone_document_and_stay_on_axis() -> None:
    """A3 — anti-redundancy guardrail: stay on the role's axis, don't
    produce a standalone full document that duplicates peers' work."""
    wf = _wf("dossier historique")
    prompt = _compose_default_prompt(
        wf, wf.steps[0], user_prompt="préparer", results={},
    )
    assert "stay strictly on your `historian` axis" in prompt.lower() or \
        "stay strictly on your" in prompt.lower()
    assert "standalone full document" in prompt.lower()


def test_task_step_has_output_contract() -> None:
    """A3 — minimal output contract per kind so downstream steps get a
    predictable shape to reference, instead of free-text prose."""
    wf = _wf("dossier historique")
    prompt = _compose_default_prompt(
        wf, wf.steps[0], user_prompt="préparer", results={},
    )
    assert "## Findings" in prompt or "Produce exactly these sections" in prompt


def test_judge_step_has_output_contract() -> None:
    wf = _wf("dossier historique")
    prompt = _compose_default_prompt(
        wf, wf.steps[1], user_prompt="préparer", results={},
    )
    assert "Produce exactly these sections" in prompt or "## Synthesis" in prompt


def test_critique_step_has_output_contract() -> None:
    wf = Workflow(
        name="t", scope="dossier historique uniquement",
        steps=[WorkflowStep(id="c", kind="critique", role="serge")],
    )
    prompt = _compose_default_prompt(wf, wf.steps[0], user_prompt="x", results={})
    assert "Produce exactly these sections" in prompt or "## Deltas" in prompt
