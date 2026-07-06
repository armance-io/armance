"""Structural + prompt-template validation for Kim's workflow YAML.

Split out of `service/skills/design_workflow.py` (A2 in the workflow-quality
refonte, `roadmap/03_workflow_quality_refonte.md` §3) to keep that module
under the 300-LOC limit. Lives outside `service/skills/` on purpose — it is
not a `Skill` subclass, and `scripts/check_invariants.sh` spot-checks the
first files it finds under that directory for the Skill MCP shape
(description/input_schema/output_schema).

Two independent concerns live here:

1. **Structural checks** that catch real bugs seen in production runs
   (`tmp/runtime3/workflows/reponse-technique-short.yaml`):
   - a `depends_on` entry pointing at a step id that doesn't exist at all
     (not just "not defined *before*", which `design_workflow._validate`
     already catches) ;
   - a step whose `role` is literally another step's `id` (Kim confused
     the two — this silently breaks role→agent resolution at run time).
2. **Prompt-template reference validation** (A2): every `{{x.output}}` /
   `{{x.outputs...}}` ref in a step's `prompt_template` must resolve to a
   declared `depends_on` of that step, or to `user_prompt` / a declared
   workflow input — otherwise the template silently renders empty text at
   run time. Errors are blocking (returned to Kim, who fixes them in
   dialogue); an empty `prompt_template` on task/judge/critique is only a
   **warning** (non-blocking — legacy YAML compat, A2).
"""
from __future__ import annotations

import logging
import re
from typing import Any

from armance.core.models.workflow import _TEMPLATE_RE

logger = logging.getLogger(__name__)

# Kinds for which Kim's system prompt (A1) mandates a differentiated
# `prompt`/`prompt_template` — an empty one is a smell, not a hard error.
_PROMPT_REQUIRED_KINDS = {"task", "judge", "critique"}

# Step kinds the executor knows about.
VALID_KINDS = {"task", "judge", "critique", "human_checkpoint", "deliverable"}

# Aliases that map to a canonical kind (silently normalised before validation).
KIND_ALIASES: dict[str, str] = {
    "revise": "task",
    "revision": "task",
    "meeting": "task",
    "checkpoint": "human_checkpoint",
    "render": "deliverable",
}

# Staff domains the runner resolves to meta-agents (no roster entry needed).
STAFF_DOMAINS = {"mona", "serge"}


def validate_step_structure(steps: list[dict[str, Any]]) -> str:
    """Catch `depends_on` → unknown step id, and `role` == some step id.

    Returns an error message (blocking) or "" if the steps are structurally
    sound. Assumes each step is already known to be a dict with an `id`.
    """
    all_ids = {s.get("id") for s in steps if isinstance(s.get("id"), str)}

    for step in steps:
        sid = step["id"]
        depends = step.get("depends_on") or []
        for dep in depends:
            if dep not in all_ids:
                return (
                    f"step `{sid}` dépend de `{dep}` qui n'existe dans "
                    f"aucun step du workflow"
                )
        role = (step.get("role") or "").strip()
        if role and role in all_ids:
            return (
                f"step `{sid}` a `role: {role}` mais `{role}` est un id de "
                f"step, pas un rôle — vérifie que role/id ne sont pas inversés"
            )
    return ""


def _refs_in_template(template: str) -> list[str]:
    return [m.group(1).strip() for m in _TEMPLATE_RE.finditer(template)]


def validate_prompt_templates(
    steps: list[dict[str, Any]],
    *,
    declared_inputs: set[str] | None = None,
) -> tuple[str, list[str]]:
    """Validate `prompt_template` refs across every step.

    Returns (blocking_error, warnings). blocking_error is "" when every
    `{{ref}}` resolves to a `depends_on` of its own step, `user_prompt`,
    `prior_session.notes`, or a declared workflow input. warnings lists
    one line per task/judge/critique step with an empty prompt_template
    (non-blocking — filet de sécurité `_compose_default_prompt` still
    applies, A3).
    """
    declared_inputs = declared_inputs or set()
    warnings: list[str] = []

    for step in steps:
        sid = step.get("id", "?")
        kind = step.get("kind")
        template = step.get("prompt_template") or ""
        depends = set(step.get("depends_on") or [])

        if not template.strip():
            if kind in _PROMPT_REQUIRED_KINDS:
                warnings.append(
                    f"step `{sid}` (kind={kind}) n'a pas de `prompt` — "
                    f"le prompt par défaut sera utilisé (moins différencié)"
                )
            continue

        for ref in _refs_in_template(template):
            if ref in ("user_prompt", "prior_session.notes"):
                continue
            if ref in declared_inputs:
                continue
            step_id = re.split(r"\.", ref, maxsplit=1)[0]
            if step_id in depends:
                continue
            error = (
                f"step `{sid}` : `prompt` référence `{{{{{ref}}}}}` qui "
                f"n'est ni dans `depends_on` ({sorted(depends) or 'vide'}), "
                f"ni `user_prompt`, ni un input déclaré"
            )
            return error, warnings

    return "", warnings


def validate_workflow_data(
    data: Any, agents: list[Any],
) -> tuple[bool, str, list[str]]:
    """Full validation pipeline for Kim's parsed workflow YAML dict.

    Moved out of `DesignWorkflowSkill._validate` (which stayed thin — id/
    kind/role/depends_on checks against the roster) so the module housing
    the skill itself stays under the 300-LOC project limit. Returns
    (ok, blocking_error, prompt_warnings).
    """
    if not isinstance(data, dict):
        return False, "racine non-objet", []
    if "name" not in data or not isinstance(data["name"], str):
        return False, "champ `name` manquant", []
    name_clean = re.sub(r"[^\w-]", "-", data["name"].lower())[:60].strip("-")
    if not name_clean:
        return False, "`name` vide après nettoyage", []
    data["name"] = name_clean

    steps = data.get("steps")
    if not isinstance(steps, list) or not steps:
        return False, "champ `steps` doit être une liste non vide", []

    # Build two indices over the roster: by role (canonical match) and by
    # lowercased name (fallback when Kim confuses name and role).
    def _agent_role(a: Any) -> str:
        return (a.role or "").lower().strip()

    roster_roles = {
        _agent_role(a)
        for a in agents
        if not getattr(a, "name", "").startswith("system-")
        and _agent_role(a)
    }
    name_to_role: dict[str, str] = {
        getattr(a, "name", "").lower().strip(): _agent_role(a)
        for a in agents
        if not getattr(a, "name", "").startswith("system-")
    }
    allowed_roles = roster_roles | STAFF_DOMAINS

    ids: set[str] = set()
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            return False, f"step #{i+1} non-objet", []
        # `prompt:` is Kim's natural-language-facing alias for the
        # existing `prompt_template` field (A1 bis) — map it before any
        # further processing so the rest of the pipeline (executor,
        # template validation) only ever sees `prompt_template`.
        if "prompt" in step and "prompt_template" not in step:
            step["prompt_template"] = step.pop("prompt")
        sid = step.get("id")
        if not isinstance(sid, str) or not sid:
            return False, f"step #{i+1} sans `id`", []
        if sid in ids:
            return False, f"id `{sid}` dupliqué", []
        ids.add(sid)
        kind = step.get("kind")
        kind = KIND_ALIASES.get(kind, kind)  # normalise aliases silently
        step["kind"] = kind
        if kind not in VALID_KINDS:
            return False, f"step `{sid}` kind=`{kind}` inconnu (attendu: {sorted(VALID_KINDS)})", []
        # `role` required for every kind except human_checkpoint.
        if kind != "human_checkpoint":
            value = (step.get("role") or "").lower().strip()
            if not value:
                return False, f"step `{sid}` sans `role`", []
            # If Kim wrote an agent name as `role`, map it back to that
            # agent's role automatically.
            if value in name_to_role and value not in allowed_roles:
                mapped = name_to_role[value]
                logger.info(
                    "skill: step `%s` role=`%s` is an agent name; "
                    "remapped to its role `%s`", sid, value, mapped,
                )
                value = mapped
            if value not in allowed_roles:
                return False, (
                    f"step `{sid}` role `{value}` ne correspond à aucun "
                    f"rôle du roster ni à `mona`/`serge`. "
                    f"Disponibles : {sorted(allowed_roles)}"
                ), []
            step["role"] = value
        depends = step.get("depends_on", [])
        if not isinstance(depends, list):
            return False, f"step `{sid}` depends_on non-liste", []
        for d in depends:
            if d not in ids:
                return False, f"step `{sid}` dépend de `{d}` non défini avant", []

    # A2 — extra structural checks (real bugs seen in production: a dep
    # pointing at a step id that never exists anywhere in the workflow,
    # and role==step-id confusion) + prompt-template ref validation.
    structural_err = validate_step_structure(steps)
    if structural_err:
        return False, structural_err, []

    declared_inputs = {
        inp.get("key") for inp in (data.get("inputs") or [])
        if isinstance(inp, dict) and inp.get("key")
    }
    template_err, prompt_warnings = validate_prompt_templates(
        steps, declared_inputs=declared_inputs,
    )
    if template_err:
        return False, template_err, []

    return True, "", prompt_warnings
