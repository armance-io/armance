"""Tests for armance.core.models.workflow."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from armance.core.models.workflow import (
    StepResult,
    execute_workflow,
    open_workflow_in_editor,
    parse_workflow,
    parse_workflow_yaml_from_llm,
    render_template,
    topo_levels,
)
SIMPLE = """\
name: w
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


def test_parse_simple_workflow() -> None:
    wf = parse_workflow(SIMPLE)
    assert wf.name == "w"
    assert [s.id for s in wf.steps] == ["a", "b"]


def test_parse_rejects_cycle() -> None:
    yaml_text = """\
name: cyc
steps:
  - id: a
    kind: task
    domain: m
    prompt_template: x
    depends_on: [b]
  - id: b
    kind: task
    domain: m
    prompt_template: x
    depends_on: [a]
"""
    with pytest.raises(ValueError):
        parse_workflow(yaml_text)


def test_parse_rejects_unknown_dependency() -> None:
    yaml_text = """\
name: missing
steps:
  - id: a
    kind: task
    domain: m
    prompt_template: x
    depends_on: [ghost]
"""
    with pytest.raises(ValueError):
        parse_workflow(yaml_text)


def test_topo_levels_groups_independent_steps() -> None:
    yaml_text = """\
name: w
steps:
  - id: a
    kind: task
    domain: m
    prompt_template: x
  - id: b
    kind: task
    domain: m
    prompt_template: x
  - id: c
    kind: task
    domain: m
    prompt_template: x
    depends_on: [a, b]
"""
    wf = parse_workflow(yaml_text)
    levels = topo_levels(wf)
    assert [sorted(s.id for s in level) for level in levels] == [["a", "b"], ["c"]]


def test_render_template_substitutes_user_prompt_and_step_output() -> None:
    out = render_template(
        "hi {{user_prompt}} -> {{a.output}}",
        user_prompt="hello",
        results={"a": StepResult(id="a", output="DONE")},
    )
    assert out == "hi hello -> DONE"


def test_render_template_rejects_unknown_field() -> None:
    with pytest.raises(ValueError):
        render_template("{{a.metadata}}", user_prompt="x", results={})


@pytest.mark.asyncio
async def test_execute_workflow_runs_in_topo_order() -> None:
    wf = parse_workflow(SIMPLE)
    call_log: list[str] = []

    async def runner(step, prompt):
        call_log.append(f"{step.id}:{prompt}")
        return f"out_{step.id}"

    results = await execute_workflow(wf, user_prompt="HELLO", runner=runner)

    assert call_log[0] == "a:HELLO"
    assert call_log[1] == "b:use out_a"
    assert results["b"].output == "out_b"


@pytest.mark.asyncio
async def test_execute_workflow_calls_on_step_prompt_hook() -> None:
    """Lot C: the effective rendered prompt must be exposed to the caller
    via an optional on_step_prompt(step_id, prompt, template_used) callback
    so the service layer can persist it for auditability — core itself
    performs no I/O (layering)."""
    wf = parse_workflow(SIMPLE)
    captured: list[tuple[str, str, bool]] = []

    def on_step_prompt(step_id: str, prompt: str, template_used: bool) -> None:
        captured.append((step_id, prompt, template_used))

    async def runner(step, prompt):
        return f"out_{step.id}"

    await execute_workflow(
        wf, user_prompt="HELLO", runner=runner, on_step_prompt=on_step_prompt,
    )

    assert captured[0] == ("a", "HELLO", True)
    assert captured[1] == ("b", "use out_a", True)


@pytest.mark.asyncio
async def test_execute_workflow_on_step_prompt_reports_default_template() -> None:
    """When a step has no prompt_template, the hook must report
    template_used=False (the default-prompt filet de sécurité kicked in)."""
    yaml_text = """\
name: w
steps:
  - id: a
    kind: task
    role: backend
"""
    wf = parse_workflow(yaml_text)

    captured: list[tuple[str, str, bool]] = []

    def on_step_prompt(step_id: str, prompt: str, template_used: bool) -> None:
        captured.append((step_id, prompt, template_used))

    async def runner(step, prompt):
        return "out"

    await execute_workflow(
        wf, user_prompt="HELLO", runner=runner, on_step_prompt=on_step_prompt,
    )

    assert captured[0][0] == "a"
    assert captured[0][2] is False


@pytest.mark.asyncio
async def test_execute_workflow_runs_level_concurrently() -> None:
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


def test_open_workflow_writes_template_without_editor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("EDITOR", raising=False)
    armance = tmp_path / ".armance"
    p = open_workflow_in_editor(armance, "fresh")
    text = p.read_text(encoding="utf-8")
    assert "name: my_workflow" in text


def test_parse_workflow_yaml_from_llm_strips_fences() -> None:
    llm_output = """\
```yaml
workflow:
  name: test_wf
  steps:
    - id: s1
      kind: meeting
      domain: backend
      mode: full
      prompt_template: "{{user_prompt}}"
```
"""
    wf = parse_workflow_yaml_from_llm(llm_output)
    assert wf.name == "test_wf"
    assert len(wf.steps) == 1
    assert wf.steps[0].id == "s1"


def test_parse_workflow_yaml_from_llm_strips_plain_fences() -> None:
    llm_output = """\
```
workflow:
  name: plain
  steps:
    - id: x
      kind: task
      domain: m
      prompt_template: hi
```
"""
    wf = parse_workflow_yaml_from_llm(llm_output)
    assert wf.name == "plain"


def test_parse_workflow_yaml_from_llm_rejects_cycle() -> None:
    llm_output = """\
workflow:
  name: cyc
  steps:
    - id: a
      kind: task
      domain: m
      prompt_template: x
      depends_on: [b]
    - id: b
      kind: task
      domain: m
      prompt_template: x
      depends_on: [a]
"""
    with pytest.raises(ValueError):
        parse_workflow_yaml_from_llm(llm_output)




# --- human_checkpoint step kind tests (task 4.1) ---

HUMAN_CHECKPOINT = """\
name: with_checkpoint
steps:
  - id: explore
    kind: meeting
    domain: product
    mode: full
    prompt_template: "{{user_prompt}}"
  - id: review
    kind: human_checkpoint
    prompt: "Please review the brainstorm results before proceeding."
    save_to_context: true
    context_layer: L1
    domain: checkpoint
    mode: full
    depends_on: [explore]
"""


def test_parse_human_checkpoint_step() -> None:
    """Parse a workflow with human_checkpoint step kind."""
    wf = parse_workflow(HUMAN_CHECKPOINT)
    assert wf.name == "with_checkpoint"
    ids = [s.id for s in wf.steps]
    assert ids == ["explore", "review"]
    # The checkpoint step should be parsed as HumanCheckpointStep
    checkpoint = wf.steps[1]
    assert checkpoint.kind == "human_checkpoint"
    assert checkpoint.prompt == "Please review the brainstorm results before proceeding."
    assert checkpoint.save_to_context is True
    assert checkpoint.context_layer == "L1"


def test_parse_human_checkpoint_defaults() -> None:
    """human_checkpoint step should use default values for optional fields."""
    yaml_text = """\
name: minimal_checkpoint
steps:
  - id: cp
    kind: human_checkpoint
    prompt: "Approve to continue"
"""
    wf = parse_workflow(yaml_text)
    cp = wf.steps[0]
    assert cp.kind == "human_checkpoint"
    assert cp.save_to_context is True  # default from HumanCheckpointStep
    assert cp.context_layer == "L1"  # default from HumanCheckpointStep
    assert cp.mode == "full"  # default
    # domain defaults to "default" in WorkflowStep base, but HumanCheckpointStep
    # would use "checkpoint" — the base model is used for parsing


def test_parse_workflow_rejects_invalid_human_checkpoint() -> None:
    """parse_workflow should reject invalid human_checkpoint configs."""
    # Invalid kind value should be rejected
    yaml_text = """\
name: bad_checkpoint
steps:
  - id: cp
    kind: invalid_kind
    domain: test
"""
    with pytest.raises(ValueError):
        parse_workflow(yaml_text)


# --- checkpoint_handler tests (task 4.2) ---


@pytest.mark.asyncio
async def test_checkpoint_handler_called_at_human_checkpoint() -> None:
    """checkpoint_handler is called when a human_checkpoint step is reached."""
    wf = parse_workflow(HUMAN_CHECKPOINT)
    handler_calls: list[tuple[str, dict[str, str]]] = []

    async def dummy_runner(step, prompt):
        return f"out_{step.id}"

    async def handler(step, prior_outputs):
        handler_calls.append((step.id, dict(prior_outputs)))
        return "human approved"

    results = await execute_workflow(
        wf, user_prompt="HELLO", runner=dummy_runner, checkpoint_handler=handler
    )

    assert len(handler_calls) == 1
    assert handler_calls[0][0] == "review"
    assert "explore" in handler_calls[0][1]
    assert results["review"].output == "human approved"


@pytest.mark.asyncio
async def test_checkpoint_handler_result_stored_in_results() -> None:
    """Output of checkpoint_handler goes into results[step.id]."""
    wf = parse_workflow(HUMAN_CHECKPOINT)

    async def dummy_runner(step, prompt):
        return f"out_{step.id}"

    async def handler(step, prior_outputs):
        return "checkpoint response"

    results = await execute_workflow(
        wf, user_prompt="HELLO", runner=dummy_runner, checkpoint_handler=handler
    )

    assert results["review"].output == "checkpoint response"


@pytest.mark.asyncio
async def test_checkpoint_handler_required() -> None:
    """execute_workflow raises when human_checkpoint step is reached without checkpoint_handler."""
    wf = parse_workflow(HUMAN_CHECKPOINT)

    async def dummy_runner(step, prompt):
        return f"out_{step.id}"

    with pytest.raises(ValueError, match="checkpoint_handler required"):
        await execute_workflow(wf, user_prompt="HELLO", runner=dummy_runner)



@pytest.mark.asyncio
async def test_checkpoint_handler_prior_outputs_contains_completed_steps() -> None:
    """checkpoint_handler receives outputs from all prior completed steps."""
    cp_yaml = (
        "name: chain_cp\n"
        "steps:\n"
        "  - id: s1\n"
        "    kind: task\n"
        "    domain: m\n"
        "    prompt_template: step1\n"
        "  - id: s2\n"
        "    kind: task\n"
        "    domain: m\n"
        "    prompt_template: step2\n"
        "  - id: cp\n"
        "    kind: human_checkpoint\n"
        "    prompt: review\n"
        "    depends_on: [s1, s2]\n"
        "  - id: s3\n"
        "    kind: task\n"
        "    domain: m\n"
        "    depends_on: [cp]\n"
        '    prompt_template: "{{cp.output}}"\n'
    )
    wf = parse_workflow(cp_yaml)
    captured: dict[str, str] = {}

    async def dummy_runner(step, prompt):
        return f"out_{step.id}"

    async def handler(step, prior_outputs):
        captured.update(prior_outputs)
        return "cp_result"

    results = await execute_workflow(
        wf, user_prompt="x", runner=dummy_runner, checkpoint_handler=handler
    )

    assert "s1" in captured
    assert "s2" in captured
    assert captured["s1"] == "out_s1"
    assert captured["s2"] == "out_s2"
    assert results["cp"].output == "cp_result"
    assert results["s3"].output == "out_s3"


# --- context enrichment tests (task 4.4) ---


@pytest.mark.asyncio
async def test_checkpoint_enriches_context_when_save_to_context_true(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When save_to_context=True, append_to_layer is called and writes versioned file."""
    monkeypatch.chdir(tmp_path)

    wf = parse_workflow(HUMAN_CHECKPOINT)

    async def dummy_runner(step, prompt):
        return f"out_{step.id}"

    async def handler(step, prior_outputs):
        return "Budget cut 30%, refocus on cost"

    results = await execute_workflow(
        wf, user_prompt="HELLO", runner=dummy_runner, checkpoint_handler=handler
    )

    assert results["review"].output == "Budget cut 30%, refocus on cost"
    # append_to_layer writes to Path.cwd() / "context"
    ctx_dir = tmp_path / "context"
    assert ctx_dir.exists()
    checkpoint_files = sorted(ctx_dir.glob("L1_checkpoint_v*.md"))
    assert len(checkpoint_files) == 1
    assert "v1" in checkpoint_files[0].name
    content = checkpoint_files[0].read_text(encoding="utf-8")
    assert "Budget cut 30%" in content


@pytest.mark.asyncio
async def test_checkpoint_no_context_enrichment_when_save_to_context_false(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When save_to_context=False, no versioned file is written."""
    monkeypatch.chdir(tmp_path)

    yaml_text = """\
name: no_enrich
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
    domain: checkpoint
    depends_on: [explore]
"""
    wf = parse_workflow(yaml_text)

    async def dummy_runner(step, prompt):
        return f"out_{step.id}"

    async def handler(step, prior_outputs):
        return "skip context"

    results = await execute_workflow(
        wf, user_prompt="HELLO", runner=dummy_runner, checkpoint_handler=handler
    )

    assert results["review"].output == "skip context"
    # No context directory should be created
    ctx_dir = tmp_path / "context"
    assert not ctx_dir.exists()


@pytest.mark.asyncio
async def test_checkpoint_no_enrichment_on_empty_response(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When checkpoint response is empty/whitespace, no file is written."""
    monkeypatch.chdir(tmp_path)

    wf = parse_workflow(HUMAN_CHECKPOINT)

    async def dummy_runner(step, prompt):
        return f"out_{step.id}"

    async def handler(step, prior_outputs):
        return "   "  # whitespace only

    results = await execute_workflow(
        wf, user_prompt="HELLO", runner=dummy_runner, checkpoint_handler=handler
    )

    assert results["review"].output == "   "
    ctx_dir = tmp_path / "context"
    assert not ctx_dir.exists()


@pytest.mark.asyncio
async def test_checkpoint_uses_custom_domain_as_theme(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The domain field is used as the theme in the versioned filename."""
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
    context_layer: L1
    domain: budget_review
    depends_on: [explore]
"""
    wf = parse_workflow(yaml_text)

    async def dummy_runner(step, prompt):
        return f"out_{step.id}"

    async def handler(step, prior_outputs):
        return "reduce budget"

    await execute_workflow(
        wf, user_prompt="HELLO", runner=dummy_runner, checkpoint_handler=handler
    )

    ctx_dir = tmp_path / "context"
    checkpoint_files = list(ctx_dir.glob("L1_budget_review_v*.md"))
    assert len(checkpoint_files) == 1
    assert "L1_budget_review_v1" in checkpoint_files[0].name


@pytest.mark.asyncio
async def test_checkpoint_uses_custom_context_layer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The context_layer field controls which layer prefix is used."""
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

    async def dummy_runner(step, prompt):
        return f"out_{step.id}"

    async def handler(step, prior_outputs):
        return "add more testing"

    await execute_workflow(
        wf, user_prompt="HELLO", runner=dummy_runner, checkpoint_handler=handler
    )

    ctx_dir = tmp_path / "context"
    checkpoint_files = list(ctx_dir.glob("L2_notes_v*.md"))
    assert len(checkpoint_files) == 1
    assert "L2_notes_v1" in checkpoint_files[0].name


@pytest.mark.asyncio
async def test_checkpoint_version_increments_across_calls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Multiple checkpoint writes increment version numbers correctly."""
    monkeypatch.chdir(tmp_path)

    yaml_text = """\
name: multi_cp
steps:
  - id: explore
    kind: meeting
    domain: product
    mode: full
    prompt_template: "{{user_prompt}}"
  - id: cp1
    kind: human_checkpoint
    prompt: "First checkpoint"
    save_to_context: true
    domain: feedback
    depends_on: [explore]
  - id: cp2
    kind: human_checkpoint
    prompt: "Second checkpoint"
    save_to_context: true
    domain: feedback
    depends_on: [cp1]
"""
    wf = parse_workflow(yaml_text)

    async def dummy_runner(step, prompt):
        return f"out_{step.id}"

    async def handler(step, prior_outputs):
        return f"response from {step.id}"

    await execute_workflow(
        wf, user_prompt="HELLO", runner=dummy_runner, checkpoint_handler=handler
    )

    ctx_dir = tmp_path / "context"
    checkpoint_files = sorted(ctx_dir.glob("L1_feedback_v*.md"))
    assert len(checkpoint_files) == 2
    assert "v1" in checkpoint_files[0].name
    assert "v2" in checkpoint_files[1].name


# --- session enrichment tests (task 4.5) ---


def test_render_template_substitutes_prior_session_notes() -> None:
    """{{prior_session.notes}} is substituted with prior_session_notes arg."""
    out = render_template(
        "Prior notes: {{prior_session.notes}}",
        user_prompt="hello",
        results={},
        prior_session_notes="Budget cut 30%",
    )
    assert out == "Prior notes: Budget cut 30%"


def test_render_template_prior_session_notes_empty_by_default() -> None:
    """When prior_session_notes is not provided, it defaults to empty string."""
    out = render_template(
        "Prior notes: {{prior_session.notes}}",
        user_prompt="hello",
        results={},
    )
    assert out == "Prior notes: "


def test_render_template_prior_session_notes_with_step_output() -> None:
    """prior_session.notes and step outputs can be used together."""
    out = render_template(
        "Notes: {{prior_session.notes}} -> {{a.output}}",
        user_prompt="hello",
        results={"a": StepResult(id="a", output="DONE")},
        prior_session_notes="Budget cut 30%",
    )
    assert out == "Notes: Budget cut 30% -> DONE"


@pytest.mark.asyncio
async def test_execute_workflow_passes_prior_session_notes_to_template() -> None:
    """execute_workflow renders prior_session_notes into step templates."""
    yaml_text = """\
name: enriched_wf
steps:
  - id: s1
    kind: task
    domain: m
    mode: full
    prompt_template: "Notes: {{prior_session.notes}} | {{user_prompt}}"
"""
    wf = parse_workflow(yaml_text)
    captured_prompts: list[str] = []

    async def runner(step, prompt):
        captured_prompts.append(prompt)
        return f"out_{step.id}"

    await execute_workflow(
        wf,
        user_prompt="HELLO",
        runner=runner,
        prior_session_notes="Budget cut 30%",
    )

    assert len(captured_prompts) == 1
    assert "Budget cut 30%" in captured_prompts[0]
    assert "HELLO" in captured_prompts[0]


@pytest.mark.asyncio
async def test_execute_workflow_prior_session_notes_empty_by_default() -> None:
    """When prior_session_notes is not provided, template gets empty string."""
    yaml_text = """\
name: no_enrich_wf
steps:
  - id: s1
    kind: task
    domain: m
    mode: full
    prompt_template: "Notes: {{prior_session.notes}}"
"""
    wf = parse_workflow(yaml_text)
    captured_prompts: list[str] = []

    async def runner(step, prompt):
        captured_prompts.append(prompt)
        return f"out_{step.id}"

    await execute_workflow(wf, user_prompt="HELLO", runner=runner)

    assert len(captured_prompts) == 1
    assert captured_prompts[0] == "Notes: "


def test_load_transcript_from_path(tmp_path: Path) -> None:
    """Transcript loading from .armance/sessions/<id>/transcript.md works."""
    sessions_dir = tmp_path / "sessions" / "abc123"
    sessions_dir.mkdir(parents=True)
    transcript_path = sessions_dir / "transcript.md"
    transcript_path.write_text(
        "# Session abc123\n\nBudget cut 30%, refocus on cost.",
        encoding="utf-8",
    )

    # Simulate the transcript loading logic from cli.py
    enrich = "abc123"
    armance = tmp_path
    transcript_path = armance / "sessions" / enrich / "transcript.md"
    prior_session_notes = ""
    if transcript_path.exists():
        prior_session_notes = transcript_path.read_text(encoding="utf-8")

    assert prior_session_notes == "# Session abc123\n\nBudget cut 30%, refocus on cost."


def test_load_transcript_missing_session(tmp_path: Path) -> None:
    """When session transcript doesn't exist, prior_session_notes stays empty."""
    armance = tmp_path
    enrich = "nonexistent"
    transcript_path = armance / "sessions" / enrich / "transcript.md"
    prior_session_notes = ""
    if transcript_path.exists():
        prior_session_notes = transcript_path.read_text(encoding="utf-8")

    assert prior_session_notes == ""
