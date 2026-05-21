"""Assumptions register — post-workflow Mona compilation.

After a workflow run finishes, Mona reviews every step output, extracts
explicit `HYPOTHESIS:` / `QUESTION:` markers (emitted by specialists
under the strict non-hallucination policy), and writes a structured
`assumptions.md` next to `synthesis.md`.

The executive summary is also surfaced to the user via the final run
message. The detailed register is persisted to disk only.

Spec: see specialist non-hallucination addon in
`service/agents/specialist_runner.py`.
"""
from __future__ import annotations

import logging

from armance.service.agents.judge_agent import JudgeAgent
from armance.service.loop_context import LoopContext
from armance.service.workflow_runs import RunArtefact, write_assumptions

logger = logging.getLogger(__name__)


def _format_steps_text(results: dict) -> str:
    """Concatenate step outputs into a single LLM-readable block."""
    return "\n\n".join(
        f"### Step: {sid}\n{getattr(r, 'output', '') or ''}"
        for sid, r in results.items()
    )


def split_exec_summary(assumptions_content: str) -> str:
    """Return the executive-summary portion (before `---` separator).

    Empty string if no separator or no summary.
    """
    if not assumptions_content:
        return ""
    parts = assumptions_content.split("---", 1)
    return parts[0].strip() if parts else ""


async def compile_and_persist(
    artefact: RunArtefact,
    results: dict,
    ctx: LoopContext,
) -> str:
    """Compile assumptions via Mona and write to `assumptions.md`.

    Returns the full assumptions content (executive summary + register),
    or empty string on failure / no output. Failure is logged, never
    raised — assumptions compilation is best-effort, not blocking.
    """
    all_steps_text = _format_steps_text(results)
    judge = JudgeAgent(ctx.armance_root, ctx.cfg)
    try:
        content = await judge.compile_assumptions(all_steps_text)
    except Exception:
        logger.exception("Mona failed to compile assumptions")
        return ""

    if content:
        write_assumptions(artefact, content)
    return content
