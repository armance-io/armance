"""Creuset (Lot F/G) shape + provider-family validation, split out of
`workflow_validation.py` to keep that module under the 300-LOC project limit.

Pure functions over already-parsed step dicts + an optional agent catalog; no
disk I/O. `model_family` is the CENTRAL family primitive (§G2/G4) — Serge and
the Creuset checks must share this one definition, never duplicate it.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


# Crucible stages that make a workflow a "creuset" (Lot F). `standard` steps
# are ordinary; any non-standard stage triggers the shape checks below.
CRUCIBLE_STAGES = {"draft", "critique", "synthesis", "gate"}

# Known provider-family prefixes for `model_family` — derived from the model id
# (anthropic/claude, google/gemini, openai/gpt). Order matters only for clarity.
_FAMILY_BY_KEYWORD: dict[str, str] = {
    "claude": "anthropic",
    "anthropic": "anthropic",
    "gemini": "google",
    "gemma": "google",
    "google": "google",
    "gpt": "openai",
    "o1": "openai",
    "o3": "openai",
    "openai": "openai",
    "mistral": "mistral",
    "mixtral": "mistral",
    "llama": "meta",
    "qwen": "qwen",
    "deepseek": "deepseek",
}


def model_family(provider: str, model: str) -> str:
    """Derive a coarse provider *family* from (provider, model) — §G2/G4 primitive.

    The family is what matters for adversarial diversity (a same-family critique
    validates by sycophancy). Centralised here so Serge (`executor_families`/
    `serge_family`) and the Creuset validation share ONE definition — do not
    duplicate. Rules:

    - `claude-code` → anthropic ; `gemini` → google (provider IS the family).
    - `openrouter` / `custom-openai` → derive from the underlying model prefix
      (``anthropic/claude-…`` → anthropic, ``google/gemini-…`` → google,
      ``openai/gpt-…`` → openai, …).
    - Fallback: the provider name itself (never crash; honest "unknown-ish").
    """
    prov = (provider or "").lower().strip()
    mdl = (model or "").lower().strip()
    if prov == "claude-code":
        return "anthropic"
    if prov == "gemini":
        return "google"
    # openrouter / custom-openai (and anything else): read the model id. The
    # part before the first "/" is often the family; otherwise keyword-match.
    head = mdl.split("/", 1)[0] if "/" in mdl else mdl
    for keyword, family in _FAMILY_BY_KEYWORD.items():
        if keyword in head or keyword in mdl:
            return family
    if "/" in mdl and head:
        return head  # e.g. "cohere/command-r" → "cohere"
    return prov or "unknown"


def available_model_families(catalog: list[Any] | None) -> set[str]:
    """Distinct provider families reachable via the configured roster (§G4).

    `catalog` is the list of recruited agents (each with `.provider`/`.model`).
    Used to tell "same family by mistake" (2+ families were available) from
    "same family because that is all that is configured" (1 family — a *subir*
    degradation, never the user's fault). Empty/None catalog ⇒ empty set (no
    live catalog wired yet — callers gate family warnings on this).
    """
    families: set[str] = set()
    for a in catalog or []:
        prov = getattr(a, "provider", "") or ""
        mdl = getattr(a, "model", "") or ""
        if prov or mdl:
            families.add(model_family(prov, mdl))
    return families


def _resolve_step_families(
    steps: list[dict[str, Any]], catalog: list[Any] | None,
) -> dict[str, str]:
    """Map draft step id → provider family, when resolvable from the catalog.

    Returns {} when no catalog is available (family resolution needs a step→
    agent→(provider,model) link). WAVE 2: the live step→agent binding is done
    at recruit time (recruiter_agent); until it lands here, this stays a hook
    that returns {} and the family-diversity warning is skipped (structural
    checks below still run). Only a per-step explicit `provider`/`model` (rare)
    resolves today.
    """
    if not catalog:
        return {}
    families: dict[str, str] = {}
    for s in steps:
        if s.get("stage") != "draft":
            continue
        prov = s.get("provider")
        mdl = s.get("model")
        if prov or mdl:
            families[s["id"]] = model_family(prov or "", mdl or "")
    return families


def validate_crucible_shape(
    steps: list[dict[str, Any]],
    *,
    catalog: list[Any] | None = None,
) -> list[str]:
    """Soft (warning-only) Creuset shape + family-diversity checks (§G1/G4).

    Runs only when at least one step carries a non-standard `stage`. Returns a
    list of human-readable warning strings (same convention as
    `validate_prompt_templates`' warnings — non-blocking, surfaced to Kim). An
    empty list means the crucible is well-formed (or there is no crucible).

    Structural rules (always checked):
      - exactly 1 `critique`, 1 `synthesis`, 1 `gate` among crucible steps ;
      - ≥ 2 `draft` steps ;
      - `critique` depends_on ALL `draft` steps.

    Family-diversity rule (§G4, gated on catalog): only fires when the catalog
    offers > 1 family AND the drafts share one → STRONG warning. When only ONE
    family is available it is a *subie* degradation → INFORMATIONAL note
    (config advice, never culpabilising).
    """
    stages = [(s["id"], s.get("stage", "standard")) for s in steps]
    if not any(st in CRUCIBLE_STAGES for _, st in stages):
        return []

    warnings: list[str] = []
    by_stage: dict[str, list[str]] = {}
    for sid, st in stages:
        by_stage.setdefault(st, []).append(sid)

    drafts = by_stage.get("draft", [])
    if len(drafts) < 2:
        warnings.append(
            f"creuset : {len(drafts)} step(s) `draft` — il en faut ≥ 2 "
            f"(brouillons concurrents comparables)"
        )
    for stage in ("critique", "synthesis", "gate"):
        n = len(by_stage.get(stage, []))
        if n != 1:
            warnings.append(
                f"creuset : {n} step(s) `{stage}` — il en faut exactement 1"
            )

    # critique must depend on ALL drafts.
    crit_ids = by_stage.get("critique", [])
    by_id = {s["id"]: s for s in steps}
    for crit_id in crit_ids:
        crit_deps = set(by_id[crit_id].get("depends_on") or [])
        missing = [d for d in drafts if d not in crit_deps]
        if missing:
            warnings.append(
                f"creuset : le step `critique` ({crit_id}) ne dépend pas de "
                f"tous les drafts (manquants : {sorted(missing)}) — la critique "
                f"comparative cross-family perd des brouillons"
            )

    # §G4 family diversity — compare families USED by drafts vs AVAILABLE.
    used = _resolve_step_families(steps, catalog)
    available = available_model_families(catalog)
    if len(drafts) >= 2 and used:
        used_families = {used[d] for d in drafts if d in used}
        if len(used_families) == 1:
            if len(available) > 1:
                warnings.append(
                    f"creuset dégénéré : les drafts partagent la famille "
                    f"`{next(iter(used_families))}` alors que "
                    f"{len(available)} familles étaient disponibles "
                    f"({sorted(available)}) — la critique cross-family n'a plus "
                    f"de prise. Répartis les drafts sur des familles distinctes."
                )
            elif len(available) == 1:
                # Subie degradation, NOT a fault — informational config advice.
                warnings.append(
                    f"creuset dégradé : 1 seule famille de modèles disponible "
                    f"({next(iter(available))}). La diversité cross-family est "
                    f"impossible avec ce setup — configure un 2ᵉ provider d'une "
                    f"autre famille pour la pleine puissance (ce n'est pas une "
                    f"faute de design)."
                )
    return warnings
