"""Workflow safety-net hooks: cross-family validation + Serge consensus
auto-invoke. Called by core.execute_workflow via pre_run_hook /
post_run_hook callbacks.

Hooks are pure async functions — no engine state, no globals. The caller
passes the workflow + accumulated step results + a small notify(event)
callback (defaults to a no-op).
"""
from __future__ import annotations

import logging
import re
from typing import Any, Awaitable, Callable, Protocol

logger = logging.getLogger(__name__)

NotifyFn = Callable[[str, dict[str, Any]], Awaitable[None]]


class _StepLike(Protocol):
    id: str
    kind: str


async def _noop_notify(kind: str, payload: dict[str, Any]) -> None:
    return None


async def validate_cross_family(
    workflow: Any,
    config: Any,
    notify: NotifyFn = _noop_notify,
) -> str | None:
    """Pre-run advisory check. NEVER aborts.

    Emits soft warnings via the notify callback when the configured providers
    cannot guarantee adversarial diversity (single-family critique, single-
    family judge). Returns None always — the workflow is the user's choice.
    Callers should NOT treat the return value as a fail signal.
    """
    if config is None:
        return None

    from armance.nls import t as _t
    from armance.service.workflow_crucible import model_family

    step_kinds = {s.kind for s in workflow.steps}
    # Family diversity is what matters, not the raw count of provider entries:
    # two providers can share a family (`custom-openai` + `openrouter` both
    # serving GPT), and a single provider name can BE its family (claude-code →
    # anthropic). Resolve each provider to its family via the central helper.
    # Providers carry no per-entry model (config.default_model is the only
    # model), so pass it through — `model_family` reads the provider name when
    # the model is empty (claude-code/gemini are their own family).
    default_model = getattr(config, "default_model", "") or ""
    families = {
        model_family(p.name, default_model)
        for p in getattr(config, "providers", []) or []
    }
    single_family = len(families) <= 1
    family_name = next(iter(families)) if families else "unknown"

    if "critique" in step_kinds and single_family:
        await notify("cross_family_warning", {
            "message": _t("workflow.warn_critique_single_family", family=family_name),
        })

    if "judge" in step_kinds and single_family:
        await notify("cross_family_warning", {
            "message": _t("workflow.warn_judge_single_family", family=family_name),
        })
    return None


async def check_consensus_and_maybe_invoke_serge(
    workflow: Any,
    step_results: dict[str, Any],
    *,
    critique_runner: Callable[[_StepLike, str], Awaitable[str]],
    notify: NotifyFn = _noop_notify,
) -> tuple[str, str] | None:
    """If 3+ judge steps all show empty Divergence, synthesise their outputs
    and call critique_runner once to get Serge's pushback.

    Workflows that already schedule a `critique` step get nothing: Serge
    already spoke there — auto-invoking him again duplicates the pushback.

    Returns (auto_step_id, critique_output) on invocation, else None.

    The caller is in charge of storing the auto-step result in its own
    StepResult container — keeps this hook engine-agnostic.
    """
    judge_steps = [s for s in workflow.steps if s.kind == "judge"]
    if not judge_steps:
        return None
    if any(s.kind == "critique" for s in workflow.steps):
        return None

    empty_count = sum(
        1 for s in judge_steps
        if s.id in step_results
        and detect_empty_divergence(_output_of(step_results[s.id]))
    )
    if empty_count < 1:
        return None

    await notify("serge_auto_invoked", {
        "reason": f"{empty_count} judge steps with empty Divergence",
        "mode": "consensus_heuristic",
    })
    logger.info(
        "Consensus heuristic: %d judge steps with empty Divergence — invoking Serge",
        empty_count,
    )

    payload = "\n\n---\n\n".join(
        _output_of(step_results[s.id])
        for s in judge_steps
        if s.id in step_results and _output_of(step_results[s.id])
    )

    class _AutoStep:
        id = "auto_serge_critique"
        kind = "critique"
        role = "meta"

    auto = _AutoStep()
    try:
        output = await critique_runner(auto, payload)
    except Exception:
        logger.exception("auto Serge critique failed")
        return None
    return (auto.id, output)


def _output_of(result_obj: Any) -> str:
    """StepResult shape differs between callers — pull the text robustly."""
    return getattr(result_obj, "output", "") or ""


# The docstring below has always promised 'Aucune' handling — the pattern
# only covered the English markers until now.
_TRIVIAL_DIVERGENCE = re.compile(
    r"^(none identified|none|no divergence|aucune(\s+divergence)?(\s+identifiée)?|—|-\s*$)\.?$",
    re.IGNORECASE,
)


def detect_empty_divergence(synthesis_text: str) -> bool:
    """True if the Divergence section in a judge synthesis is empty or trivial.

    A section is empty when it has no body, or only contains markers like
    'None identified', 'Aucune', '-', '—'.
    """
    sections = re.split(r"^(?=##)", synthesis_text, flags=re.MULTILINE)
    div_body: str | None = None
    for section in sections:
        if re.match(r"##\s*Divergence\b", section, re.IGNORECASE):
            div_body = section.split("\n", 1)[1] if "\n" in section else ""
            break
    if div_body is None:
        return True
    body = div_body.strip()
    if not body:
        return True
    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    if not lines:
        return True
    return all(_TRIVIAL_DIVERGENCE.match(ln) for ln in lines)
