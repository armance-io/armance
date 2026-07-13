"""Prompt-composition helpers for the workflow executor.

Split out of `workflow.py` to keep that module small. Pure functions (no disk
I/O, no service imports) — they only build strings from a step, its workflow,
upstream results, and the `inputs` dict. `render_template` is imported lazily
inside `_resolve_deliverable_prompt` to avoid a circular import with
`workflow.py` (which imports these two functions at module load).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # annotations only — no runtime import (avoids an import cycle)
    from armance.core.models.workflow import StepResult, Workflow, WorkflowStep


def compose_default_prompt(
    workflow: "Workflow",
    step: "WorkflowStep",
    user_prompt: str,
    results: "dict[str, StepResult]",
    inputs: "dict[str, Any] | None" = None,
) -> str:
    """Build a structured prompt when no `prompt_template` is provided.

    Without this, Kim's free-text workflows (no templates) pass an empty string
    to the runner and specialists answer with their persona seed only. A3
    filet-de-sécurité (roadmap/03_workflow_quality_refonte.md §3), never the
    nominal path (Kim should write a differentiated `prompt` per step): emits
    scope + request, kind/role-tailored instructions with an anti-redundancy
    guardrail + output contract, and upstream outputs framed as to *extend*.
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
    # Repeated anti-redundancy guardrail (identical across kinds).
    axis = (f"Stay strictly on your `{role}` axis; other steps cover the "
            "rest. Do not produce a standalone full document. ")
    if kind == "task":
        lines[-1] += (
            "Produce substantive content for this step. Write at length — "
            "specialists are expected to deliver detailed, sourced, structured "
            "output (target 500-2000 words depending on the workflow scope). "
            "Use Markdown: headings, bullets, citations where applicable. "
            "Do NOT just acknowledge the task — actually do the work. " + axis +
            "Produce exactly these sections: "
            "## Findings / ## Risks / ## Open questions."
        )
    elif kind == "judge":
        lines[-1] += (
            "Synthesise the upstream contributions into a single coherent "
            "document. Quote, contrast, structure. Stay strictly inside the "
            "workflow scope above — do NOT comment on the broader project "
            "(budget, logistics, timeline) unless the scope explicitly "
            "includes them. Target 800-2000 words. " + axis +
            "Produce exactly these sections: "
            "## Synthesis / ## Points of tension / ## Recommendation."
        )
    elif kind == "critique":
        lines[-1] += (
            "Stress-test the upstream synthesis. Find weak claims, missing "
            "evidence, logical gaps, blind spots. Be specific and adversarial. "
            "Stay strictly inside the workflow scope — do NOT critique angles "
            "outside it (e.g. business, finance, code) unless the scope says so. "
            "Target 300-800 words. " + axis + "Produce "
            "numbered deltas, not a rewrite of the synthesis. "
            "Produce exactly these sections: "
            "## Deltas (numbered) / ## Unresolved risks."
        )
    elif kind == "meeting":
        lines[-1] += (
            "Contribute your distinct angle to the group's exchange. Build on "
            "or push back against peers' contributions when relevant. "
            "Target 200-600 words. " + axis.rstrip()
        )
    else:
        lines[-1] += (
            "Produce the output expected for this kind of step. Be substantive. "
            + axis.rstrip()
        )

    # Seed documents (Lot B): text loaded by the service layer, passed via
    # `inputs` under `seed.<basename>` keys; injected as-is so a step can
    # critique/extend an existing doc. `core` never reads the disk.
    inputs = inputs or {}
    seed_keys = [k for k in step.seed_docs if f"seed.{k}" in inputs]
    if seed_keys:
        lines.append(
            "\n## Seed documents (existing material — critique/extend it, "
            "do NOT ignore it and do NOT re-derive it from scratch)"
        )
        for basename in seed_keys:
            lines.append(f"\n### `{basename}`\n{inputs[f'seed.{basename}']}")

    if step.depends_on:
        lines.append("\n## Upstream material (extend it, do NOT rewrite or restate it)")
        for dep_id in step.depends_on:
            if dep_id in results:
                lines.append(
                    f"\n### Deliverable from step `{dep_id}` "
                    "(extend it, do NOT rewrite or restate it)\n"
                    f"{results[dep_id].output}"
                )
    return "\n".join(lines)


def resolve_deliverable_prompt(
    s: "WorkflowStep",
    workflow: "Workflow",
    user_prompt: str,
    results: "dict[str, StepResult]",
    prior_session_notes: str,
    inputs: "dict[str, Any]",
) -> str:
    """Resolve the content a `kind: deliverable` step compiles.

    Priority: explicit `source` → "latest_judge" → an existing result id →
    else compile depends_on outputs (or render the template) into a synthesis
    prompt.
    """
    from armance.core.models.workflow import render_template  # lazy: import cycle

    source = s.model_dump().get("source", "")
    if source == "latest_judge":
        for res in results.values():
            if res.id == "judge":
                return res.output
        raise ValueError("latest_judge requested but no judge result found in workflow results")
    if source and source in results:
        return results[source].output
    if source and source not in results:
        raise ValueError(f"deliverable step source '{source}' not found in workflow results")
    # No explicit source — compile depends_on outputs into a synthesis prompt.
    # This handles Kim's common pattern of kind:deliverable without source
    # (the step IS the synthesis).
    if s.prompt_template:
        return render_template(
            s.prompt_template,
            user_prompt=user_prompt,
            results=results,
            prior_session_notes=prior_session_notes,
            inputs=inputs,
        )
    parts = [
        f"## {dep_id}\n\n{results[dep_id].output}"
        for dep_id in s.depends_on
        if dep_id in results
    ]
    if parts:
        return (
            f"Original request: {user_prompt}\n\n"
            + "\n\n---\n\n".join(parts)
            + "\n\nBased on the above contributions, produce the final deliverable."
        )
    return user_prompt
