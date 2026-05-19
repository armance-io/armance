"""Integration tests for human_checkpoint workflow feature (task 4.7).

Covers:
  1. Mock checkpoint_handler returns scripted answer
  2. L1 checkpoint file written after handler call
  3. Downstream step template substitution sees checkpoint value
  4. No regression in existing workflow functionality
"""
from __future__ import annotations

from pathlib import Path

import pytest

from armance.core.models.workflow import (
    StepResult,
    execute_workflow,
    parse_workflow,
    render_template,
)

# ── Workflow fixtures ────────────────────────────────────────────────

CHECKPOINT_WORKFLOW = """\
name: checkpoint_test
steps:
  - id: explore
    kind: meeting
    domain: product
    mode: full
    prompt_template: "{{user_prompt}}"
  - id: review
    kind: human_checkpoint
    prompt: "Review brainstorm results"
    save_to_context: true
    context_layer: L1
    domain: brainstorm
    depends_on: [explore]
  - id: synthesize
    kind: task
    domain: product
    mode: light
    depends_on: [review]
    prompt_template: |
      Synthesize based on human feedback.
      
      Brainstorm output:
      {{explore.output}}
      
      Human feedback:
      {{review.output}}
"""

MULTI_CHECKPOINT_WORKFLOW = """\
name: multi_checkpoint
steps:
  - id: s1
    kind: task
    domain: m
    prompt_template: "step one"
  - id: cp1
    kind: human_checkpoint
    prompt: "First checkpoint"
    save_to_context: true
    context_layer: L1
    domain: feedback
    depends_on: [s1]
  - id: s2
    kind: task
    domain: m
    mode: full
    depends_on: [cp1]
    prompt_template: "{{cp1.output}}"
  - id: cp2
    kind: human_checkpoint
    prompt: "Second checkpoint"
    save_to_context: true
    context_layer: L1
    domain: feedback
    depends_on: [s2]
  - id: s3
    kind: task
    domain: m
    mode: full
    depends_on: [cp2]
    prompt_template: "{{cp2.output}}"
"""

# ── Requirement 1: Mock checkpoint_handler returns scripted answer ──


@pytest.mark.asyncio
async def test_handler_scripted_answer_returned_as_step_output() -> None:
    """Mock checkpoint_handler returns a scripted answer that becomes the step output."""
    wf = parse_workflow(CHECKPOINT_WORKFLOW)

    async def handler(step, prior_outputs):
        # Scripted response regardless of input
        return "APPROVED: Proceed with direction A"

    async def dummy_runner(step, prompt):
        return f"runner_out_{step.id}"

    results = await execute_workflow(
        wf, user_prompt="test prompt", runner=dummy_runner, checkpoint_handler=handler
    )

    assert results["review"].output == "APPROVED: Proceed with direction A"


@pytest.mark.asyncio
async def test_handler_receives_prior_outputs() -> None:
    """checkpoint_handler receives prior step outputs in prior_outputs dict."""
    wf = parse_workflow(CHECKPOINT_WORKFLOW)
    captured_prior: dict[str, str] = {}

    async def handler(step, prior_outputs):
        captured_prior.update(prior_outputs)
        return "ok"

    async def dummy_runner(step, prompt):
        return f"out_{step.id}"

    await execute_workflow(
        wf, user_prompt="test", runner=dummy_runner, checkpoint_handler=handler
    )

    assert "explore" in captured_prior
    assert captured_prior["explore"] == "out_explore"


@pytest.mark.asyncio
async def test_multi_checkpoint_handler_called_in_order() -> None:
    """Multiple checkpoints call handler sequentially in dependency order."""
    wf = parse_workflow(MULTI_CHECKPOINT_WORKFLOW)
    call_order: list[str] = []

    async def handler(step, prior_outputs):
        call_order.append(step.id)
        return f"response_{step.id}"

    async def dummy_runner(step, prompt):
        return f"out_{step.id}"

    results = await execute_workflow(
        wf, user_prompt="test", runner=dummy_runner, checkpoint_handler=handler
    )

    assert call_order == ["cp1", "cp2"]
    assert results["cp1"].output == "response_cp1"
    assert results["cp2"].output == "response_cp2"


# ── Requirement 2: Assert L1 file written ───────────────────────────


@pytest.mark.asyncio
async def test_l1_checkpoint_file_written(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Checkpoint with save_to_context=True writes L1_checkpoint_v<N>.md."""
    monkeypatch.chdir(tmp_path)

    wf = parse_workflow(CHECKPOINT_WORKFLOW)

    async def handler(step, prior_outputs):
        return "Budget cut 30%, refocus on cost"

    async def dummy_runner(step, prompt):
        return f"out_{step.id}"

    await execute_workflow(
        wf, user_prompt="test", runner=dummy_runner, checkpoint_handler=handler
    )

    ctx_dir = tmp_path / "context"
    assert ctx_dir.exists()
    checkpoint_files = sorted(ctx_dir.glob("L1_brainstorm_v*.md"))
    assert len(checkpoint_files) == 1
    content = checkpoint_files[0].read_text(encoding="utf-8")
    assert "Budget cut 30%" in content


@pytest.mark.asyncio
async def test_l1_not_written_when_save_to_context_false(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No file written when checkpoint save_to_context=False."""
    monkeypatch.chdir(tmp_path)

    yaml_text = """\
name: no_save
steps:
  - id: explore
    kind: meeting
    domain: product
    mode: full
    prompt_template: "{{user_prompt}}"
  - id: review
    kind: human_checkpoint
    prompt: "Review"
    save_to_context: false
    domain: brainstorm
    depends_on: [explore]
"""
    wf = parse_workflow(yaml_text)

    async def handler(step, prior_outputs):
        return "skip"

    async def dummy_runner(step, prompt):
        return f"out_{step.id}"

    await execute_workflow(
        wf, user_prompt="test", runner=dummy_runner, checkpoint_handler=handler
    )

    assert not (tmp_path / "context").exists()


@pytest.mark.asyncio
async def test_l1_not_written_on_empty_response(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No file written when checkpoint response is whitespace-only."""
    monkeypatch.chdir(tmp_path)

    wf = parse_workflow(CHECKPOINT_WORKFLOW)

    async def handler(step, prior_outputs):
        return "   \n  "

    async def dummy_runner(step, prompt):
        return f"out_{step.id}"

    await execute_workflow(
        wf, user_prompt="test", runner=dummy_runner, checkpoint_handler=handler
    )

    assert not (tmp_path / "context").exists()


@pytest.mark.asyncio
async def test_l1_uses_custom_domain_theme(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Domain field controls the theme in the versioned filename."""
    monkeypatch.chdir(tmp_path)

    yaml_text = """\
name: custom_theme
steps:
  - id: explore
    kind: meeting
    domain: product
    mode: full
    prompt_template: "{{user_prompt}}"
  - id: review
    kind: human_checkpoint
    prompt: "Review"
    save_to_context: true
    domain: budget_review
    depends_on: [explore]
"""
    wf = parse_workflow(yaml_text)

    async def handler(step, prior_outputs):
        return "reduce budget"

    async def dummy_runner(step, prompt):
        return f"out_{step.id}"

    await execute_workflow(
        wf, user_prompt="test", runner=dummy_runner, checkpoint_handler=handler
    )

    ctx_dir = tmp_path / "context"
    checkpoint_files = list(ctx_dir.glob("L1_budget_review_v*.md"))
    assert len(checkpoint_files) == 1
    assert "L1_budget_review_v1" in checkpoint_files[0].name


@pytest.mark.asyncio
async def test_l1_uses_custom_context_layer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """context_layer field controls the layer prefix."""
    monkeypatch.chdir(tmp_path)

    yaml_text = """\
name: custom_layer
steps:
  - id: explore
    kind: meeting
    domain: product
    mode: full
    prompt_template: "{{user_prompt}}"
  - id: review
    kind: human_checkpoint
    prompt: "Review"
    save_to_context: true
    context_layer: L2
    domain: notes
    depends_on: [explore]
"""
    wf = parse_workflow(yaml_text)

    async def handler(step, prior_outputs):
        return "add testing"

    async def dummy_runner(step, prompt):
        return f"out_{step.id}"

    await execute_workflow(
        wf, user_prompt="test", runner=dummy_runner, checkpoint_handler=handler
    )

    ctx_dir = tmp_path / "context"
    checkpoint_files = list(ctx_dir.glob("L2_notes_v*.md"))
    assert len(checkpoint_files) == 1
    assert "L2_notes_v1" in checkpoint_files[0].name


@pytest.mark.asyncio
async def test_version_increments_across_checkpoints(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Multiple checkpoint writes increment version numbers."""
    monkeypatch.chdir(tmp_path)

    wf = parse_workflow(MULTI_CHECKPOINT_WORKFLOW)

    async def handler(step, prior_outputs):
        return f"response_{step.id}"

    async def dummy_runner(step, prompt):
        return f"out_{step.id}"

    await execute_workflow(
        wf, user_prompt="test", runner=dummy_runner, checkpoint_handler=handler
    )

    ctx_dir = tmp_path / "context"
    checkpoint_files = sorted(ctx_dir.glob("L1_feedback_v*.md"))
    assert len(checkpoint_files) == 2
    assert "v1" in checkpoint_files[0].name
    assert "v2" in checkpoint_files[1].name


# ── Requirement 3: Downstream template substitution sees checkpoint value ──


@pytest.mark.asyncio
async def test_downstream_step_sees_checkpoint_output() -> None:
    """Step depending on checkpoint receives checkpoint output via template."""
    wf = parse_workflow(CHECKPOINT_WORKFLOW)
    captured_prompts: list[str] = []

    async def handler(step, prior_outputs):
        return "HUMAN_FEEDBACK_APPROVED"

    async def dummy_runner(step, prompt):
        captured_prompts.append(prompt)
        return f"out_{step.id}"

    await execute_workflow(
        wf, user_prompt="test", runner=dummy_runner, checkpoint_handler=handler
    )

    # synthesize step prompt should contain both explore.output and review.output
    assert len(captured_prompts) == 2
    explore_prompt = captured_prompts[0]
    synthesize_prompt = captured_prompts[1]

    assert "test" in explore_prompt  # user_prompt in explore
    assert "HUMAN_FEEDBACK_APPROVED" in synthesize_prompt  # review.output in synthesize
    assert "explore.output" not in synthesize_prompt  # template was substituted


@pytest.mark.asyncio
async def test_template_substitution_exact_value() -> None:
    """Downstream template substitution produces exact handler output."""
    yaml_text = """\
name: exact_sub
steps:
  - id: s1
    kind: task
    domain: m
    prompt_template: "s1"
  - id: cp
    kind: human_checkpoint
    prompt: "cp"
    save_to_context: false
    depends_on: [s1]
  - id: s2
    kind: task
    domain: m
    depends_on: [cp]
    prompt_template: "Result: {{cp.output}}"
"""
    wf = parse_workflow(yaml_text)
    captured_prompts: list[str] = []

    async def handler(step, prior_outputs):
        return "EXACT_SCRIPTED_VALUE"

    async def dummy_runner(step, prompt):
        captured_prompts.append(prompt)
        return f"out_{step.id}"

    await execute_workflow(
        wf, user_prompt="test", runner=dummy_runner, checkpoint_handler=handler
    )

    # s2 prompt should have exact handler output substituted
    assert len(captured_prompts) == 2
    assert captured_prompts[1] == "Result: EXACT_SCRIPTED_VALUE"


@pytest.mark.asyncio
async def test_checkpoint_output_chained_through_multiple_steps() -> None:
    """Checkpoint output propagates through multiple downstream steps."""
    wf = parse_workflow(MULTI_CHECKPOINT_WORKFLOW)
    captured_prompts: list[str] = []

    async def handler(step, prior_outputs):
        return f"VALUE_FROM_{step.id}"

    async def dummy_runner(step, prompt):
        captured_prompts.append((step.id, prompt))
        return f"out_{step.id}"

    await execute_workflow(
        wf, user_prompt="test", runner=dummy_runner, checkpoint_handler=handler
    )

    # s2 depends on cp1, should see cp1 output
    s2_id, s2_prompt = captured_prompts[1]
    assert s2_id == "s2"
    assert s2_prompt == "VALUE_FROM_cp1"

    # s3 depends on cp2, should see cp2 output
    s3_id, s3_prompt = captured_prompts[2]
    assert s3_id == "s3"
    assert s3_prompt == "VALUE_FROM_cp2"


# ── Requirement 4: No regression in existing workflow functionality ──


@pytest.mark.asyncio
async def test_regular_workflow_without_checkpoint_still_works() -> None:
    """Workflows without human_checkpoint steps execute normally."""
    yaml_text = """\
name: regular
steps:
  - id: a
    kind: meeting
    domain: backend
    mode: full
    prompt_template: "{{user_prompt}}"
  - id: b
    kind: task
    domain: backend
    mode: light
    depends_on: [a]
    prompt_template: "use {{a.output}}"
"""
    wf = parse_workflow(yaml_text)
    call_log: list[str] = []

    async def runner(step, prompt):
        call_log.append(f"{step.id}:{prompt}")
        return f"out_{step.id}"

    results = await execute_workflow(
        wf, user_prompt="HELLO", runner=runner
    )

    assert call_log[0] == "a:HELLO"
    assert call_log[1] == "b:use out_a"
    assert results["b"].output == "out_b"


@pytest.mark.asyncio
async def test_concurrent_steps_still_run_concurrently() -> None:
    """Parallel step execution is unaffected by checkpoint code paths."""
    yaml_text = """\
name: para
steps:
  - id: a
    kind: task
    domain: m
    prompt_template: x
  - id: b
    kind: task
    domain: m
    prompt_template: x
"""
    import asyncio
    wf = parse_workflow(yaml_text)
    started: list[str] = []
    release = asyncio.Event()

    async def runner(step, prompt):
        started.append(step.id)
        if len(started) < 2:
            await release.wait()
        else:
            release.set()
        return step.id

    await execute_workflow(wf, user_prompt="x", runner=runner)
    assert sorted(started) == ["a", "b"]


def test_render_template_checkpoint_output_in_chain() -> None:
    """render_template correctly substitutes checkpoint step output."""
    out = render_template(
        "Before: {{a.output}} | After: {{cp.output}}",
        user_prompt="hello",
        results={
            "a": StepResult(id="a", output="step_a_result"),
            "cp": StepResult(id="cp", output="human_approved"),
        },
    )
    assert out == "Before: step_a_result | After: human_approved"


def test_render_template_checkpoint_with_prior_session() -> None:
    """render_template combines checkpoint output with prior_session.notes."""
    out = render_template(
        "Notes: {{prior_session.notes}} | Feedback: {{cp.output}}",
        user_prompt="hello",
        results={"cp": StepResult(id="cp", output="approved")},
        prior_session_notes="Budget cut 30%",
    )
    assert out == "Notes: Budget cut 30% | Feedback: approved"


@pytest.mark.asyncio
async def test_checkpoint_required_error_message() -> None:
    """Error message clearly states checkpoint_handler is required."""
    wf = parse_workflow(CHECKPOINT_WORKFLOW)

    async def dummy_runner(step, prompt):
        return f"out_{step.id}"

    with pytest.raises(ValueError, match="checkpoint_handler required"):
        await execute_workflow(wf, user_prompt="test", runner=dummy_runner)


@pytest.mark.asyncio
async def test_checkpoint_step_skips_regular_runner() -> None:
    """human_checkpoint step does not call the regular runner."""
    wf = parse_workflow(CHECKPOINT_WORKFLOW)
    runner_calls: list[str] = []

    async def handler(step, prior_outputs):
        return "handler_response"

    async def dummy_runner(step, prompt):
        runner_calls.append(step.id)
        return f"out_{step.id}"

    await execute_workflow(
        wf, user_prompt="test", runner=dummy_runner, checkpoint_handler=handler
    )

    # explore and synthesize call runner, review (checkpoint) does not
    assert runner_calls == ["explore", "synthesize"]
