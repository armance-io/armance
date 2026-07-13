"""Creuset engine foundations (Lot F wave 1): stage/run_if/gate pass-through.

Covers the core/models/workflow.py additions: new fields + backward compat,
parse-time run_if validation, and the run_if pass-through skip semantics in
execute_workflow (skipped steps never call the runner).
"""
from __future__ import annotations

import pytest
from armance.core.models.workflow import (
    RubricCriterion,
    StepResult,
    Workflow,
    WorkflowStep,
    execute_workflow,
    parse_workflow,
)

# A legacy (pre-Creuset) workflow: every step must parse as stage="standard".
LEGACY = """\
name: legacy
steps:
  - id: a
    kind: task
    role: backend
    prompt_template: "{{user_prompt}}"
  - id: b
    kind: task
    role: backend
    depends_on: [a]
    prompt_template: "use {{a.output}}"
"""


def test_backward_compat_all_standard() -> None:
    wf = parse_workflow(LEGACY)
    assert all(s.stage == "standard" for s in wf.steps)
    assert all(s.run_if == "" for s in wf.steps)
    assert all(s.rubric == [] for s in wf.steps)


def test_new_fields_and_rubric_parse() -> None:
    yaml_text = """\
name: crucible
steps:
  - id: da
    kind: task
    role: backend
    stage: draft
    prompt_template: "{{user_prompt}}"
  - id: db
    kind: task
    role: backend
    stage: draft
    prompt_template: "{{user_prompt}}"
  - id: crit
    kind: critique
    role: backend
    stage: critique
    depends_on: [da, db]
    prompt_template: "compare {{da.output}} {{db.output}}"
  - id: syn
    kind: task
    role: backend
    stage: synthesis
    depends_on: [da, db, crit]
    prompt_template: "synth {{crit.output}}"
  - id: g
    kind: judge
    role: mona
    stage: gate
    depends_on: [syn]
    gate_threshold: 8.0
    rubric:
      - name: coverage
        description: covers all requirements
        weight: 2.0
      - name: clarity
    prompt_template: "grade {{syn.output}}"
"""
    wf = parse_workflow(yaml_text)
    gate = next(s for s in wf.steps if s.id == "g")
    assert gate.stage == "gate"
    assert gate.gate_threshold == 8.0
    assert [c.name for c in gate.rubric] == ["coverage", "clarity"]
    assert gate.rubric[0].weight == 2.0
    assert gate.rubric[1].weight == 1.0  # default


def test_rubric_criterion_model() -> None:
    c = RubricCriterion(name="x")
    assert c.description == "" and c.weight == 1.0


def _crucible_with_run_if(run_if: str, *, gate_id: str = "g") -> str:
    return f"""\
name: rev
steps:
  - id: syn
    kind: task
    role: backend
    stage: synthesis
    prompt_template: "{{{{user_prompt}}}}"
  - id: {gate_id}
    kind: judge
    role: mona
    stage: gate
    depends_on: [syn]
    prompt_template: "grade {{{{syn.output}}}}"
  - id: syn2
    kind: task
    role: backend
    stage: synthesis
    depends_on: [syn, {gate_id}]
    passthrough_from: syn
    run_if: "{run_if}"
    prompt_template: "revise {{{{syn.output}}}}"
"""


def test_run_if_valid_parses() -> None:
    wf = parse_workflow(_crucible_with_run_if("gate:g:REVISE"))
    syn2 = next(s for s in wf.steps if s.id == "syn2")
    assert syn2.run_if == "gate:g:REVISE"


def test_run_if_dangling_gate_raises() -> None:
    with pytest.raises(ValueError, match="unknown gate step"):
        parse_workflow(_crucible_with_run_if("gate:nope:REVISE"))


def test_run_if_malformed_raises() -> None:
    with pytest.raises(ValueError, match="malformed run_if"):
        parse_workflow(_crucible_with_run_if("g:REVISE"))


def test_run_if_references_non_gate_raises() -> None:
    # `syn` exists but is a synthesis, not a gate → structural error.
    with pytest.raises(ValueError, match="not a gate"):
        parse_workflow(_crucible_with_run_if("gate:syn:REVISE", gate_id="g"))


def test_run_if_no_passthrough_source_raises() -> None:
    yaml_text = """\
name: nope
steps:
  - id: g
    kind: judge
    role: mona
    stage: gate
    prompt_template: "x"
  - id: orphan
    kind: task
    role: backend
    run_if: "gate:g:REVISE"
    prompt_template: "y"
"""
    with pytest.raises(ValueError, match="no resolvable pass-through"):
        parse_workflow(yaml_text)


@pytest.mark.asyncio
async def test_gate_accept_skips_revision_passthrough() -> None:
    """gate emits ACCEPT → syn2 (run_if REVISE) is skipped, output = syn output,
    skipped is True, and the runner is NEVER called for syn2."""
    wf = parse_workflow(_crucible_with_run_if("gate:g:REVISE"))
    called: list[str] = []

    async def runner(step: WorkflowStep, prompt: str) -> str:
        called.append(step.id)
        if step.id == "syn":
            return "SYN_V1"
        if step.id == "g":
            return "verdict: [GATE:ACCEPT]"
        return "SYN_V2_SHOULD_NOT_RUN"

    results = await execute_workflow(wf, user_prompt="go", runner=runner)
    assert "syn2" not in called  # runner never dispatched for the skipped step
    assert results["syn2"].skipped is True
    assert results["syn2"].output == "SYN_V1"  # pass-through of its depends_on[0]


@pytest.mark.asyncio
async def test_gate_revise_runs_revision() -> None:
    wf = parse_workflow(_crucible_with_run_if("gate:g:REVISE"))
    called: list[str] = []

    async def runner(step: WorkflowStep, prompt: str) -> str:
        called.append(step.id)
        if step.id == "syn":
            return "SYN_V1"
        if step.id == "g":
            return "verdict: [GATE:REVISE]"
        return "SYN_V2"

    results = await execute_workflow(wf, user_prompt="go", runner=runner)
    assert "syn2" in called
    assert results["syn2"].skipped is False
    assert results["syn2"].output == "SYN_V2"


@pytest.mark.asyncio
async def test_gate_absent_tag_treated_as_revise() -> None:
    """No [GATE:...] tag ⇒ REVISE ⇒ a run_if:...:REVISE step still runs."""
    wf = parse_workflow(_crucible_with_run_if("gate:g:REVISE"))
    called: list[str] = []

    async def runner(step: WorkflowStep, prompt: str) -> str:
        called.append(step.id)
        return "SYN_V1" if step.id == "syn" else "no verdict tag here"

    await execute_workflow(wf, user_prompt="go", runner=runner)
    assert "syn2" in called


def test_passthrough_from_explicit_source() -> None:
    step = WorkflowStep(id="s", kind="task", passthrough_from="src", depends_on=["dep"])
    from armance.core.models.workflow import _passthrough_output

    results = {
        "src": StepResult(id="src", output="FROM_SRC"),
        "dep": StepResult(id="dep", output="FROM_DEP"),
    }
    assert _passthrough_output(step, results) == "FROM_SRC"


def test_stepresult_default_not_skipped() -> None:
    assert StepResult(id="x", output="o").skipped is False


def test_workflow_model_directly() -> None:
    # A Workflow built directly (not via YAML) exposes the new fields.
    wf = Workflow(name="w", steps=[WorkflowStep(id="a", kind="task", stage="draft")])
    assert wf.steps[0].stage == "draft"
