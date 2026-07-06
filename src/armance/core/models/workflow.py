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
_TEMPLATE_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}")



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

    # Step-specific fields (populated based on kind)
    prompt: str = ""
    context_layer: str = "L1"
    save_to_context: bool = True
    format: str = ""
    source: str = ""
    output_name: str = ""

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



StepRunner = Callable[[WorkflowStep, str], Awaitable[str]]



def parse_workflow(text: str) -> Workflow:
    raw = yaml.safe_load(text) or {}
    try:
        wf = Workflow.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"invalid workflow yaml: {exc}") from exc
    _validate_dag(wf.steps)
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



def _compose_default_prompt(
    workflow: "Workflow",
    step: "WorkflowStep",
    user_prompt: str,
    results: "dict[str, StepResult]",
) -> str:
    """Build a structured prompt when no `prompt_template` is provided.

    Without this, Kim's free-text workflows (which never define templates)
    pass an empty string to the runner and specialists answer with their
    persona seed only — outputs end up being 1 line of "Prêt à défendre les
    archives".

    The composed prompt has three parts:
      1. Workflow scope (the narrow goal) + user's original request.
      2. Step instructions tailored to its kind + role.
      3. Upstream outputs as cited material to build on / critique / judge.
    """
    scope = (workflow.scope or "").strip()
    role = step.role or "specialist"
    kind = step.kind

    lines: list[str] = []
    lines.append(f"# Workflow: {workflow.name}")
    if scope:
        lines.append(f"\n## Scope (narrow goal — stay strictly inside)\n{scope}")
    if user_prompt and user_prompt.strip():
        lines.append(f"\n## User's original request\n{user_prompt.strip()}")

    lines.append(f"\n## Your role in this step\nYou are a `{role}`. ")
    if kind == "task":
        lines[-1] += (
            "Produce substantive content for this step. Write at length — "
            "specialists are expected to deliver detailed, sourced, structured "
            "output (target 500-2000 words depending on the workflow scope). "
            "Use Markdown: headings, bullets, citations where applicable. "
            "Do NOT just acknowledge the task — actually do the work."
        )
    elif kind == "judge":
        lines[-1] += (
            "Synthesise the upstream contributions into a single coherent "
            "document. Quote, contrast, structure. Stay strictly inside the "
            "workflow scope above — do NOT comment on the broader project "
            "(budget, logistics, timeline) unless the scope explicitly "
            "includes them. Target 800-2000 words."
        )
    elif kind == "critique":
        lines[-1] += (
            "Stress-test the upstream synthesis. Find weak claims, missing "
            "evidence, logical gaps, blind spots. Be specific and adversarial. "
            "Stay strictly inside the workflow scope — do NOT critique angles "
            "outside it (e.g. business, finance, code) unless the scope says so. "
            "Target 300-800 words."
        )
    elif kind == "meeting":
        lines[-1] += (
            "Contribute your distinct angle to the group's exchange. Build on "
            "or push back against peers' contributions when relevant. "
            "Target 200-600 words."
        )
    else:
        lines[-1] += (
            "Produce the output expected for this kind of step. Be substantive."
        )

    if step.depends_on:
        lines.append("\n## Upstream contributions (material to work from)")
        for dep_id in step.depends_on:
            if dep_id in results:
                lines.append(f"\n### {dep_id}\n{results[dep_id].output}")
    return "\n".join(lines)


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
) -> dict[str, StepResult]:
    """Run every step of the workflow.

    runner(step, rendered_prompt) -> output text. The executor handles
    topological ordering, concurrency within a level via asyncio.gather,
    and template substitution.

    checkpoint_handler(step, prior_outputs) -> user response text.
    Called when a step has kind=="human_checkpoint" instead of the
    regular runner.  prior_outputs maps completed step ids to their
    output strings.

    pre_run_hook (optional): async callable(workflow). Raise to abort
    (cross-family validation lives here in the service layer).

    post_run_hook (optional): async callable(workflow, results, runner)
    invoked after the last level finishes. The hook may mutate `results`
    to inject extra step outputs (Serge consensus auto-invoke does this).

    on_step_prompt (optional): sync callable(step_id, effective_prompt,
    template_used) invoked right before each regular step's runner is
    dispatched. `core` performs no I/O — this is the seam the service
    layer uses to persist the effective prompt for auditability (Lot C)
    without core touching the filesystem itself.
    """
    import asyncio

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

        # Process regular steps with template rendering and asyncio.gather
        if regular_steps:
            prompts = []
            template_used_flags: list[bool] = []
            for s in regular_steps:
                template_used = bool(s.prompt_template)
                if s.kind == "deliverable":
                    # For deliverable steps, resolve the content to compile.
                    # Priority: explicit `source` field → "latest_judge" keyword →
                    # last depends_on result → fallback to template rendering.
                    source = s.model_dump().get("source", "")
                    if source == "latest_judge":
                        judge_result = None
                        for res in results.values():
                            if res.id == "judge":
                                judge_result = res.output
                                break
                        if judge_result:
                            prompt_text = judge_result
                        else:
                            raise ValueError("latest_judge requested but no judge result found in workflow results")
                    elif source and source in results:
                        prompt_text = results[source].output
                    elif source and source not in results:
                        raise ValueError(f"deliverable step source '{source}' not found in workflow results")
                    else:
                        # No explicit source — compile depends_on outputs into a
                        # synthesis prompt. This handles Kim's common pattern of
                        # kind:deliverable without source (the step IS the synthesis).
                        if s.prompt_template:
                            prompt_text = render_template(
                                s.prompt_template,
                                user_prompt=user_prompt,
                                results=results,
                                prior_session_notes=prior_session_notes,
                            )
                        else:
                            parts = []
                            for dep_id in s.depends_on:
                                if dep_id in results:
                                    parts.append(f"## {dep_id}\n\n{results[dep_id].output}")
                            if parts:
                                prompt_text = (
                                    f"Original request: {user_prompt}\n\n"
                                    + "\n\n---\n\n".join(parts)
                                    + "\n\nBased on the above contributions, produce the final deliverable."
                                )
                            else:
                                prompt_text = user_prompt
                    prompts.append(prompt_text)
                else:
                    # Regular task/meeting/judge/critique step.
                    if s.prompt_template:
                        prompt_text = render_template(
                            s.prompt_template,
                            user_prompt=user_prompt,
                            results=results,
                            prior_session_notes=prior_session_notes,
                        )
                    else:
                        # No explicit template — compose a structured prompt
                        # from the workflow scope, step kind, and upstream
                        # outputs. Kim rarely writes templates; without
                        # this fallback, agents receive an empty prompt and
                        # respond with their persona seed only.
                        prompt_text = _compose_default_prompt(
                            workflow, s, user_prompt, results,
                        )
                    prompts.append(prompt_text)
                template_used_flags.append(template_used)

            if on_step_prompt is not None:
                for s, prompt_text, template_used in zip(regular_steps, prompts, template_used_flags):
                    try:
                        on_step_prompt(s.id, prompt_text, template_used)
                    except Exception:  # noqa: BLE001 — a persistence hook must never break the run
                        logger.exception("on_step_prompt hook failed for step %s", s.id)

            # Real tasks (not bare coroutines) so an abort can cancel the
            # in-flight siblings — plain gather leaves them running orphaned,
            # burning tokens on a run that is already over.
            tasks = [
                asyncio.create_task(runner(step, prompt))
                for step, prompt in zip(regular_steps, prompts)
            ]
            try:
                outputs = await asyncio.gather(*tasks)
            except BaseException:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                raise
            for step, output in zip(regular_steps, outputs):
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
