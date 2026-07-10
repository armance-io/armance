"""YAML workflow schema, parser, and DAG executor.

Workflow YAML shape:

    name: brainstorm
    steps:
      - id: explore
        kind: meeting              # task | meeting
        role: backend
        mode: full                 # full | light
        prompt_template: "{{user_prompt}}"
      - id: focus
        kind: task
        role: backend
        mode: light
        agents: [backend_balanced]
        depends_on: [explore]
        prompt_template: "Refine: {{explore.output}}"

The executor topologically sorts steps, then within each independent
level it runs them concurrently via asyncio.gather. A step's
prompt_template is rendered through a tiny double-brace substitution
("{{step_id.output}}", "{{user_prompt}}") so downstream steps can
read upstream outputs without pulling in jinja.
"""
from __future__ import annotations

import logging
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Iterable, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

logger = logging.getLogger(__name__)

StepKind = Literal["task", "meeting", "deliverable", "human_checkpoint", "render", "judge", "critique", "checkpoint", "loop"]
KNOWN_STEP_KINDS = frozenset(("task", "meeting", "deliverable", "human_checkpoint", "render", "judge", "critique", "checkpoint", "loop"))
StepMode = Literal["full", "light"]
CrucibleStage = Literal["standard", "draft", "critique", "synthesis", "gate"]
_TEMPLATE_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}")
# Gate verdict tag, scanned as a literal substring in a gate step's output.
# `core` must NOT import the service parser (agent_sandbox); the pass-through
# skip detects ACCEPT/REVISE here by regex. Last occurrence wins; absent ⇒
# REVISE (see `_run_if_satisfied`).
_GATE_TAG_RE = re.compile(r"\[GATE:(ACCEPT|REVISE)\]")
# `run_if` grammar: "gate:<gate_step_id>:<VERDICT>", VERDICT ∈ {ACCEPT, REVISE}.
_RUN_IF_RE = re.compile(r"^gate:([a-zA-Z0-9_.-]+):(ACCEPT|REVISE)$")


class RubricCriterion(BaseModel):
    """One scored criterion of a `gate` step's rubric (Creuset, Lot F3)."""
    name: str
    description: str = ""
    weight: float = 1.0


class WorkflowStep(BaseModel):
    """Polymorphic step model.

    `role` is the agent-matching field — the role this step assigns (Kim's
    user-facing YAML contract). Legacy YAMLs that wrote `domain:` still parse
    via a before-validator.
    """
    model_config = ConfigDict(populate_by_name=True)

    id: str
    kind: StepKind
    role: str = "default"
    mode: StepMode = "full"
    agents: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    prompt_template: str = ""
    # Library document names (basename, under `.armance/docs/`) to inject as
    # seed material for this step — e.g. an existing tender to challenge. The
    # actual file read happens in the `service` layer (layering: `core` does
    # no disk I/O); the loaded text is passed to `execute_workflow` via the
    # `inputs` dict under `seed.<basename>` and surfaced in the default prompt.
    seed_docs: list[str] = Field(default_factory=list)

    # Step-specific fields (populated based on kind)
    prompt: str = ""
    context_layer: str = "L1"
    save_to_context: bool = True
    format: str = ""
    source: str = ""
    output_name: str = ""

    # Creuset (Lot F) — cross-family draft→critique→synthesis→gate sub-graph.
    # `stage` names a step's function in a crucible (distinct from `kind`/`role`).
    # Default "standard" ⇒ 100% backward-compatible (legacy = standard-only).
    stage: CrucibleStage = "standard"
    # F5 static-unrolled bounded revision: a step with a non-empty `run_if` runs
    # only when the referenced gate emitted the matching verdict; else it is
    # skipped with PASS-THROUGH semantics. Grammar: "gate:<gate_id>:REVISE|ACCEPT".
    # The step MUST depend (transitively) on that gate so it is evaluated only
    # after the gate's verdict exists; otherwise the verdict is unseen ⇒ REVISE.
    run_if: str = ""
    # Pass-through source id for a skipped step; falls back to depends_on[0].
    passthrough_from: str = ""
    # gate-only: rubric (4-6 criteria) + acceptance threshold (weighted mean).
    rubric: list[RubricCriterion] = Field(default_factory=list)
    gate_threshold: float = 7.5

    @model_validator(mode="before")
    @classmethod
    def _accept_legacy_domain(cls, data):
        """Legacy YAMLs used `domain:` for the role — accept it on read."""
        if not isinstance(data, dict):
            return data
        if "role" not in data and "domain" in data:
            data["role"] = data["domain"]
        data.pop("domain", None)
        return data


class Workflow(BaseModel):
    name: str
    steps: list[WorkflowStep]
    scope: str = ""           # One-line narrow goal — narrower than the project.
    description: str = ""     # Free-text rationale (rendered by `/workflow list`).


@dataclass(slots=True)
class StepResult:
    id: str
    output: str
    # True when skipped via `run_if`: output is a pass-through copy of its
    # input (Creuset F5), no runner ran, 0 tokens. Read by wave-2 report code.
    skipped: bool = False


StepRunner = Callable[[WorkflowStep, str], Awaitable[str]]


def parse_workflow(text: str) -> Workflow:
    raw = yaml.safe_load(text) or {}
    try:
        wf = Workflow.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"invalid workflow yaml: {exc}") from exc
    _validate_dag(wf.steps)
    _validate_crucible(wf.steps)
    return wf


def load_workflow(path: Path) -> Workflow:
    return parse_workflow(path.read_text(encoding="utf-8"))


def _validate_dag(steps: Iterable[WorkflowStep]) -> None:
    step_list = list(steps)
    by_id: dict[str, WorkflowStep] = {}
    for s in step_list:
        if s.id in by_id:
            raise ValueError(f"duplicate step id: {s.id}")
        by_id[s.id] = s

    visited: dict[str, int] = {}  # 0=unseen,1=in-stack,2=done

    def visit(node: str, stack: list[str]) -> None:
        state = visited.get(node, 0)
        if state == 1:
            cycle = " -> ".join(stack[stack.index(node):] + [node])
            raise ValueError(f"workflow has a cycle: {cycle}")
        if state == 2:
            return
        if node not in by_id:
            raise ValueError(f"step '{stack[-1] if stack else '?'}' depends on unknown step '{node}'")
        visited[node] = 1
        stack.append(node)
        for dep in by_id[node].depends_on:
            visit(dep, stack)
        stack.pop()
        visited[node] = 2

    for s in by_id:
        visit(s, [])


def _validate_crucible(steps: Iterable[WorkflowStep]) -> None:
    """Structural (raise-on-error) validation of Creuset `run_if` wiring (F5).

    Soft family-diversity / shape warnings live in the service layer
    (`service/workflow_validation.py`); only hard errors raise here: a
    non-empty `run_if` must match `gate:<id>:ACCEPT|REVISE` where `<id>` is an
    existing `stage == "gate"` step, and the conditional step must have a
    resolvable pass-through source (`passthrough_from` or a non-empty depends_on).
    """
    by_id = {s.id: s for s in steps}
    for s in by_id.values():
        if not s.run_if:
            continue
        m = _RUN_IF_RE.match(s.run_if)
        if m is None:
            raise ValueError(
                f"step '{s.id}' has malformed run_if '{s.run_if}' "
                f"(expected 'gate:<step_id>:ACCEPT|REVISE')"
            )
        target = by_id.get(m.group(1))
        if target is None:
            raise ValueError(f"step '{s.id}' run_if references unknown gate step '{m.group(1)}'")
        if target.stage != "gate":
            raise ValueError(
                f"step '{s.id}' run_if references step '{m.group(1)}' "
                f"which is not a gate (stage={target.stage!r})"
            )
        if s.passthrough_from and s.passthrough_from not in by_id:
            raise ValueError(
                f"step '{s.id}' passthrough_from references unknown step '{s.passthrough_from}'"
            )
        if not s.passthrough_from and not s.depends_on:
            raise ValueError(
                f"step '{s.id}' has run_if but no resolvable pass-through source "
                f"(set passthrough_from or a non-empty depends_on)"
            )


def _run_if_satisfied(step: WorkflowStep, results: dict[str, StepResult]) -> bool:
    """True if `step.run_if` is satisfied by results in hand (pure, no I/O).

    Empty run_if ⇒ True. Else the gate's output is scanned for the literal
    `[GATE:ACCEPT|REVISE]` tag (last wins; absent ⇒ REVISE — a gate that did
    not decide is broken), and True is returned when it matches the required verdict.
    """
    if not step.run_if:
        return True
    m = _RUN_IF_RE.match(step.run_if)
    if m is None:  # defensive — parse_workflow already rejects malformed run_if
        return True
    gate_res = results.get(m.group(1))
    tags = _GATE_TAG_RE.findall(gate_res.output if gate_res is not None else "")
    verdict = tags[-1] if tags else "REVISE"
    return verdict == m.group(2)


def _passthrough_output(step: WorkflowStep, results: dict[str, StepResult]) -> str:
    """Skipped-step pass-through output: `passthrough_from` else depends_on[0]
    (missing from results ⇒ "" — validation already ensures a source exists)."""
    src_id = step.passthrough_from or (step.depends_on[0] if step.depends_on else "")
    src = results.get(src_id)
    return src.output if src is not None else ""


def topo_levels(workflow: Workflow) -> list[list[WorkflowStep]]:
    by_id = {s.id: s for s in workflow.steps}
    pending = {s.id: set(s.depends_on) for s in workflow.steps}
    levels: list[list[WorkflowStep]] = []
    while pending:
        ready = sorted(sid for sid, deps in pending.items() if not deps)
        if not ready:
            raise ValueError("workflow has a cycle (unreachable in topo)")
        levels.append([by_id[sid] for sid in ready])
        for sid in ready:
            pending.pop(sid)
        for deps in pending.values():
            deps.difference_update(ready)
    return levels


def render_template(
    template: str,
    *,
    user_prompt: str,
    results: dict[str, StepResult],
    prior_session_notes: str = "",
    inputs: dict[str, Any] | None = None,
) -> str:
    """Render a step prompt template.

    Supported refs:
      {{user_prompt}}            — top-level user prompt
      {{prior_session.notes}}    — enriched prior session transcript
      {{<input_key>}}            — workflow input by key
      {{<step_id>.output}}       — text deliverable of a prior step
      {{<step_id>.outputs}}      — bulleted list of all outputs (mode:full)
      {{<step_id>.outputs[i]}}   — individual output at index i
    """
    inputs = inputs or {}

    def replace(match: re.Match[str]) -> str:
        ref = match.group(1).strip()
        if ref == "user_prompt":
            return user_prompt
        if ref == "prior_session.notes":
            return prior_session_notes
        if ref in inputs:
            return str(inputs[ref])

        idx_match = re.match(r"^(.+)\.outputs\[(\d+)\]$", ref)
        if idx_match:
            step_id, idx_str = idx_match.groups()
            if step_id not in results:
                raise ValueError(f"template references unfinished step: {step_id}")
            all_outputs = getattr(results[step_id], "outputs", None) or [results[step_id].output]
            i = int(idx_str)
            if i >= len(all_outputs):
                raise ValueError(
                    f"template references out-of-range index {i} for step '{step_id}'"
                )
            return all_outputs[i]

        outputs_match = re.match(r"^(.+)\.outputs$", ref)
        if outputs_match:
            step_id = outputs_match.group(1)
            if step_id not in results:
                raise ValueError(f"template references unfinished step: {step_id}")
            all_outputs = getattr(results[step_id], "outputs", None) or [results[step_id].output]
            return "\n".join(f"- {o}" for o in all_outputs)

        if "." in ref:
            step_id, field = ref.split(".", 1)
            if field != "output":
                raise ValueError(f"only .output, .outputs, .outputs[i] are supported in templates: {ref}")
            if step_id not in results:
                raise ValueError(f"template references unfinished step: {step_id}")
            return results[step_id].output
        raise ValueError(f"unknown template ref: {ref}")

    return _TEMPLATE_RE.sub(replace, template)


# Prompt-composition helpers live in a sibling module to keep this file small.
# Re-exported under their private names for backward compat (tests import
# `_compose_default_prompt` from here).
from armance.core.models._workflow_prompts import (  # noqa: E402
    compose_default_prompt as _compose_default_prompt,
    resolve_deliverable_prompt as _resolve_deliverable_prompt,
)


class WorkflowAbortError(RuntimeError):
    """Raised by a pre_run_hook to abort the workflow before any step runs."""


async def execute_workflow(
    workflow: Workflow,
    *,
    user_prompt: str,
    runner: StepRunner,
    prior_session_notes: str = "",
    checkpoint_handler: Callable[[WorkflowStep, dict[str, str]], Awaitable[str]] | None = None,
    pre_run_hook: Callable[[Workflow], Awaitable[None]] | None = None,
    post_run_hook: Callable[[Workflow, "dict[str, StepResult]", StepRunner], Awaitable[None]] | None = None,
    armance_root: Path | None = None,
    on_step_prompt: Callable[[str, str, bool], None] | None = None,
    inputs: dict[str, Any] | None = None,
) -> dict[str, StepResult]:
    """Run every step of the workflow.

    runner(step, rendered_prompt) -> output text. Handles topological ordering,
    per-level concurrency (asyncio.gather), and template substitution.

    checkpoint_handler(step, prior_outputs) -> user response, called for
    kind=="human_checkpoint" steps (prior_outputs maps completed ids → output).

    pre_run_hook (optional): async(workflow). Raise to abort (cross-family
    validation lives here, service layer). post_run_hook (optional):
    async(workflow, results, runner) after the last level; may mutate `results`
    to inject step outputs (Serge consensus auto-invoke). on_step_prompt
    (optional): sync(step_id, effective_prompt, template_used) before each
    runner dispatch — the seam the service layer uses to persist the effective
    prompt (Lot C) without `core` doing I/O.

    inputs (optional): free-form workflow inputs for templates (`{{<key>}}`) and
    the default prompt; Lot B loads seed docs here (keys `seed.<basename>`) from
    the service layer — `core` never touches the filesystem.
    """
    import asyncio

    inputs = inputs or {}

    if pre_run_hook is not None:
        await pre_run_hook(workflow)

    levels = topo_levels(workflow)
    results: dict[str, StepResult] = {}
    for level in levels:
        # Separate checkpoint steps from regular steps in this level.
        # Regular steps run FIRST: steps in the same level never depend on
        # each other, so a checkpoint must not block its parallel siblings —
        # and the human then answers with those fresh outputs in hand.
        checkpoint_steps = [s for s in level if s.kind == "human_checkpoint"]
        regular_steps = [s for s in level if s.kind != "human_checkpoint"]

        # Process regular steps with template rendering and asyncio.gather.
        # Creuset F5: partition on `run_if`. Skipped steps get a pass-through
        # StepResult (0 tokens, no runner call) and are filled into `results`
        # FIRST so any same-level/downstream depends_on still resolve; only
        # `to_run` steps reach the runner dispatch batch.
        to_skip = [s for s in regular_steps if not _run_if_satisfied(s, results)]
        to_run = [s for s in regular_steps if _run_if_satisfied(s, results)]
        for s in to_skip:
            results[s.id] = StepResult(
                id=s.id, output=_passthrough_output(s, results), skipped=True,
            )
        if to_run:
            prompts = []
            template_used_flags: list[bool] = []
            for s in to_run:
                template_used = bool(s.prompt_template)
                if s.kind == "deliverable":
                    prompt_text = _resolve_deliverable_prompt(
                        s, workflow, user_prompt, results,
                        prior_session_notes, inputs,
                    )
                else:
                    # Regular task/meeting/judge/critique step.
                    if s.prompt_template:
                        prompt_text = render_template(
                            s.prompt_template,
                            user_prompt=user_prompt,
                            results=results,
                            prior_session_notes=prior_session_notes,
                            inputs=inputs,
                        )
                    else:
                        # No explicit template — compose a structured prompt
                        # (scope + kind + upstream). Without it agents get an
                        # empty prompt and reply with their persona seed only.
                        prompt_text = _compose_default_prompt(
                            workflow, s, user_prompt, results, inputs=inputs,
                        )
                prompts.append(prompt_text)
                template_used_flags.append(template_used)

            if on_step_prompt is not None:
                for s, prompt_text, template_used in zip(to_run, prompts, template_used_flags):
                    try:
                        on_step_prompt(s.id, prompt_text, template_used)
                    except Exception:  # noqa: BLE001 — a persistence hook must never break the run
                        logger.exception("on_step_prompt hook failed for step %s", s.id)

            # Real tasks (not bare coroutines) so an abort can cancel the
            # in-flight siblings — plain gather leaves them running orphaned,
            # burning tokens on a run that is already over.
            tasks = [
                asyncio.create_task(runner(step, prompt))
                for step, prompt in zip(to_run, prompts)
            ]
            try:
                outputs = await asyncio.gather(*tasks)
            except BaseException:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                raise
            for step, output in zip(to_run, outputs):
                results[step.id] = StepResult(id=step.id, output=output)

        # Checkpoints AFTER the level's regular steps (see above).
        for cs in checkpoint_steps:
            if checkpoint_handler is None:
                raise ValueError(
                    f"checkpoint_handler required but not provided; "
                    f"step '{cs.id}' is a human_checkpoint"
                )
            prior_outputs = {rid: r.output for rid, r in results.items()}
            response = await checkpoint_handler(cs, prior_outputs)
            results[cs.id] = StepResult(id=cs.id, output=response)

            # Context enrichment: write checkpoint response to versioned layer file
            if cs.save_to_context and response.strip():
                from armance.core.models.context import append_to_layer

                target_root = armance_root or Path.cwd()
                theme = cs.role or "checkpoint"
                layer = cs.context_layer or "L1"
                append_to_layer(
                    target_root,
                    layer=layer,
                    theme=theme,
                    text=response,
                )

    if post_run_hook is not None:
        await post_run_hook(workflow, results, runner)
    return results


WORKFLOW_TEMPLATE = """\
name: my_workflow
steps:
  - id: step1
    kind: meeting       # task | meeting
    role: backend
    mode: full          # full | light
    prompt_template: |
      Replace this with your prompt. Use {{user_prompt}} for the user
      input and {{step_id.output}} to chain step outputs.
"""


def parse_workflow_yaml_from_llm(text: str) -> Workflow:
    """Strip markdown fences and parse LLM output as Workflow."""
    # Strip ```yaml ... ``` or ``` ... ```
    cleaned = re.sub(r"^```(?:yaml)?\s*", "", text.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip())
    raw = yaml.safe_load(cleaned) or {}
    # LLM may wrap in {workflow: {name, steps}} — unwrap
    if isinstance(raw, dict) and "workflow" in raw and "name" not in raw:
        raw = raw["workflow"]
    return parse_workflow(yaml.safe_dump(raw))


def open_workflow_in_editor(armance_root: Path, name: str, *, editor: str | None = None) -> Path:
    """Create (or open) a workflow file under $EDITOR for editing."""
    workflows_dir = armance_root / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    path = workflows_dir / f"{name}.yaml"
    if not path.exists():
        path.write_text(WORKFLOW_TEMPLATE, encoding="utf-8")
    chosen_editor = editor or os.environ.get("EDITOR")
    if chosen_editor:
        subprocess.run([chosen_editor, str(path)], check=False)
    else:
        logger.warning("no $EDITOR set; created %s without launching editor", path)
    return path
