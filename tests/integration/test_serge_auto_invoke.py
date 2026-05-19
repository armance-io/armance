"""T-25d: consensus heuristic auto-invokes Serge.

Drives the hooks against `core.execute_workflow` directly — the same
path production uses through `handlers._cmd_workflow_run`.
"""
from __future__ import annotations

import pytest

from armance.core.models.workflow import (
    StepResult,
    Workflow,
    WorkflowStep,
    execute_workflow,
)
from armance.service.workflow_hooks import (
    check_consensus_and_maybe_invoke_serge,
    detect_empty_divergence,
)


SYNTHESIS_WITH_DIVERGENCE = """\
## Consensus
Consensus here.
## Divergence
- Lars disagrees on something.
## Recommendation
Do this.
"""

SYNTHESIS_NO_DIVERGENCE = """\
## Consensus
Strong consensus.
## Divergence

## Recommendation
Proceed.
"""

SYNTHESIS_SHALLOW_DIVERGENCE = """\
## Consensus
Solid.
## Divergence
None identified.
## Recommendation
Go ahead.
"""


def test_empty_divergence_detected_on_blank_section() -> None:
    assert detect_empty_divergence(SYNTHESIS_NO_DIVERGENCE) is True


def test_empty_divergence_detected_on_none_identified() -> None:
    assert detect_empty_divergence(SYNTHESIS_SHALLOW_DIVERGENCE) is True


def test_nonempty_divergence_not_flagged() -> None:
    assert detect_empty_divergence(SYNTHESIS_WITH_DIVERGENCE) is False


@pytest.mark.asyncio
async def test_three_empty_divergence_triggers_serge(tmp_path) -> None:
    """3 judge steps with empty divergence → critique runner is invoked."""
    events: list[tuple[str, dict]] = []

    async def notify(kind: str, payload: dict) -> None:
        events.append((kind, payload))

    critique_calls: list[tuple[str, str]] = []

    async def critique_runner(step, payload: str) -> str:
        critique_calls.append((step.id, payload[:50]))
        return "## Assumptions\nCritique output."

    workflow = Workflow(
        name="consensus_test",
        steps=[
            WorkflowStep(id="s_j1", kind="judge"),
            WorkflowStep(id="s_j2", kind="judge", depends_on=["s_j1"]),
            WorkflowStep(id="s_j3", kind="judge", depends_on=["s_j2"]),
        ],
    )
    results = {
        "s_j1": StepResult(id="s_j1", output=SYNTHESIS_NO_DIVERGENCE),
        "s_j2": StepResult(id="s_j2", output=SYNTHESIS_NO_DIVERGENCE),
        "s_j3": StepResult(id="s_j3", output=SYNTHESIS_NO_DIVERGENCE),
    }

    outcome = await check_consensus_and_maybe_invoke_serge(
        workflow, results, critique_runner=critique_runner, notify=notify,
    )

    assert outcome is not None
    auto_id, output = outcome
    assert auto_id == "auto_serge_critique"
    assert "Critique" in output
    assert any(k == "serge_auto_invoked" for k, _ in events)
    assert len(critique_calls) == 1


@pytest.mark.asyncio
async def test_fewer_than_three_empty_divergence_no_auto_invoke() -> None:
    """Only 2 empty divergence judge steps → no auto-invoke."""
    workflow = Workflow(
        name="two_empty",
        steps=[
            WorkflowStep(id="s_j1", kind="judge"),
            WorkflowStep(id="s_j2", kind="judge", depends_on=["s_j1"]),
        ],
    )
    results = {
        "s_j1": StepResult(id="s_j1", output=SYNTHESIS_NO_DIVERGENCE),
        "s_j2": StepResult(id="s_j2", output=SYNTHESIS_NO_DIVERGENCE),
    }

    async def critique_runner(step, payload: str) -> str:
        raise AssertionError("should not be called")

    outcome = await check_consensus_and_maybe_invoke_serge(
        workflow, results, critique_runner=critique_runner,
    )
    assert outcome is None


@pytest.mark.asyncio
async def test_e2e_post_run_hook_appends_auto_step(tmp_path) -> None:
    """End-to-end: execute_workflow with the post_run_hook injects an
    auto_serge_critique step result into the results dict."""

    workflow = Workflow(
        name="e2e",
        steps=[
            WorkflowStep(id="j1", kind="judge"),
            WorkflowStep(id="j2", kind="judge", depends_on=["j1"]),
            WorkflowStep(id="j3", kind="judge", depends_on=["j2"]),
        ],
    )

    async def runner(step, prompt: str) -> str:
        # Both the regular judge steps AND the auto critique step go through here.
        if step.kind == "judge":
            return SYNTHESIS_NO_DIVERGENCE
        return "## Assumptions\nauto critique."

    async def post(wf, results, runner_fn):
        async def critique(auto_step, payload):
            return await runner_fn(auto_step, payload)
        outcome = await check_consensus_and_maybe_invoke_serge(
            wf, results, critique_runner=critique,
        )
        if outcome is not None:
            auto_id, output = outcome
            results[auto_id] = StepResult(id=auto_id, output=output)

    results = await execute_workflow(
        workflow,
        user_prompt="hi",
        runner=runner,
        post_run_hook=post,
        armance_root=tmp_path,
    )

    assert "auto_serge_critique" in results
    assert "auto critique" in results["auto_serge_critique"].output
