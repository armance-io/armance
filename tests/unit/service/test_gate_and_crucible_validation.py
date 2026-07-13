"""Wave-1 service-layer Creuset helpers: gate tag/score parsing (Lot F4) and
soft crucible shape + family-diversity validation (Lot G1/G4)."""
from __future__ import annotations

from dataclasses import dataclass

from armance.service.agent_sandbox import parse_gate_scores, parse_gate_verdict
from armance.service.workflow_crucible import (
    available_model_families,
    model_family,
    validate_crucible_shape,
)


# --- parse_gate_verdict ---------------------------------------------------

def test_verdict_accept() -> None:
    assert parse_gate_verdict("all good [GATE:ACCEPT]") == "ACCEPT"


def test_verdict_revise() -> None:
    assert parse_gate_verdict("needs work [GATE:REVISE]") == "REVISE"


def test_verdict_absent_is_none() -> None:
    assert parse_gate_verdict("no tag at all") is None


def test_verdict_last_tag_wins() -> None:
    assert parse_gate_verdict("[GATE:REVISE] ... final [GATE:ACCEPT]") == "ACCEPT"
    assert parse_gate_verdict("[GATE:ACCEPT] ... final [GATE:REVISE]") == "REVISE"


# --- parse_gate_scores ----------------------------------------------------

def test_scores_table_with_slash_ten() -> None:
    text = (
        "| Criterion | Score |\n"
        "|-----------|-------|\n"
        "| Coverage  | 8/10  |\n"
        "| Clarity   | 6.5/10|\n"
    )
    assert parse_gate_scores(text) == {"Coverage": 8.0, "Clarity": 6.5}


def test_scores_bare_number() -> None:
    text = "| Criterion | Score |\n|---|---|\n| Feasibility | 7 |\n"
    assert parse_gate_scores(text) == {"Feasibility": 7.0}


def test_scores_none_returns_empty() -> None:
    assert parse_gate_scores("no table here") == {}


# --- model_family / available_model_families ------------------------------

def test_model_family_provider_is_family() -> None:
    assert model_family("claude-code", "claude-opus-4") == "anthropic"
    assert model_family("gemini", "gemini-2.0-pro") == "google"


def test_model_family_from_openrouter_prefix() -> None:
    assert model_family("openrouter", "anthropic/claude-3.5") == "anthropic"
    assert model_family("openrouter", "google/gemini-2.0") == "google"
    assert model_family("openrouter", "openai/gpt-5") == "openai"


@dataclass
class _Agent:
    provider: str
    model: str
    role: str = ""
    provider_family: str | None = None


def test_available_families() -> None:
    catalog = [
        _Agent("claude-code", "claude-opus"),
        _Agent("gemini", "gemini-2.0"),
        _Agent("openrouter", "openai/gpt-5"),
    ]
    assert available_model_families(catalog) == {"anthropic", "google", "openai"}


def test_available_families_empty_catalog() -> None:
    assert available_model_families(None) == set()
    assert available_model_families([]) == set()


# --- validate_crucible_shape ----------------------------------------------

def _shape(steps: list[dict]) -> list[str]:
    return validate_crucible_shape(steps)


def test_no_crucible_no_warnings() -> None:
    steps = [{"id": "a", "kind": "task", "stage": "standard"}]
    assert _shape(steps) == []


def test_missing_critique_warns() -> None:
    steps = [
        {"id": "da", "kind": "task", "stage": "draft"},
        {"id": "db", "kind": "task", "stage": "draft"},
        {"id": "syn", "kind": "task", "stage": "synthesis", "depends_on": ["da", "db"]},
        {"id": "g", "kind": "judge", "stage": "gate", "depends_on": ["syn"]},
    ]
    warns = _shape(steps)
    assert any("critique" in w for w in warns)


def test_less_than_two_drafts_warns() -> None:
    steps = [
        {"id": "da", "kind": "task", "stage": "draft"},
        {"id": "crit", "kind": "critique", "stage": "critique", "depends_on": ["da"]},
        {"id": "syn", "kind": "task", "stage": "synthesis", "depends_on": ["da", "crit"]},
        {"id": "g", "kind": "judge", "stage": "gate", "depends_on": ["syn"]},
    ]
    warns = _shape(steps)
    assert any("draft" in w for w in warns)


def test_critique_not_depending_on_all_drafts_warns() -> None:
    steps = [
        {"id": "da", "kind": "task", "stage": "draft"},
        {"id": "db", "kind": "task", "stage": "draft"},
        # critique depends only on da, not db → warning
        {"id": "crit", "kind": "critique", "stage": "critique", "depends_on": ["da"]},
        {"id": "syn", "kind": "task", "stage": "synthesis", "depends_on": ["da", "db", "crit"]},
        {"id": "g", "kind": "judge", "stage": "gate", "depends_on": ["syn"]},
    ]
    warns = _shape(steps)
    assert any("ne dépend pas de" in w and "db" in w for w in warns)


def test_well_formed_crucible_has_no_shape_warnings() -> None:
    steps = [
        {"id": "da", "kind": "task", "stage": "draft"},
        {"id": "db", "kind": "task", "stage": "draft"},
        {"id": "crit", "kind": "critique", "stage": "critique", "depends_on": ["da", "db"]},
        {"id": "syn", "kind": "task", "stage": "synthesis", "depends_on": ["da", "db", "crit"]},
        {"id": "g", "kind": "judge", "stage": "gate", "depends_on": ["syn"]},
    ]
    # No catalog → family rule skipped; structural checks all pass.
    assert _shape(steps) == []


def test_mono_family_is_informational_not_fault() -> None:
    # Two drafts, one available family → informational degradation, not a fault.
    steps = [
        {"id": "da", "kind": "task", "stage": "draft",
         "provider": "claude-code", "model": "claude-opus"},
        {"id": "db", "kind": "task", "stage": "draft",
         "provider": "claude-code", "model": "claude-sonnet"},
        {"id": "crit", "kind": "critique", "stage": "critique", "depends_on": ["da", "db"]},
        {"id": "syn", "kind": "task", "stage": "synthesis", "depends_on": ["da", "db", "crit"]},
        {"id": "g", "kind": "judge", "stage": "gate", "depends_on": ["syn"]},
    ]
    catalog = [_Agent("claude-code", "claude-opus")]  # only one family available
    warns = validate_crucible_shape(steps, catalog=catalog)
    assert any("dégradé" in w and "pas une" in w for w in warns)


def test_same_family_with_alternatives_is_strong_fault() -> None:
    steps = [
        {"id": "da", "kind": "task", "stage": "draft",
         "provider": "claude-code", "model": "claude-opus"},
        {"id": "db", "kind": "task", "stage": "draft",
         "provider": "claude-code", "model": "claude-sonnet"},
        {"id": "crit", "kind": "critique", "stage": "critique", "depends_on": ["da", "db"]},
        {"id": "syn", "kind": "task", "stage": "synthesis", "depends_on": ["da", "db", "crit"]},
        {"id": "g", "kind": "judge", "stage": "gate", "depends_on": ["syn"]},
    ]
    # Catalog offers TWO families → sharing one is a real design fault.
    catalog = [_Agent("claude-code", "claude-opus"), _Agent("gemini", "gemini-2.0")]
    warns = validate_crucible_shape(steps, catalog=catalog)
    assert any("dégénéré" in w for w in warns)


# --- live step→agent family resolution (Wave 2a) --------------------------

def _crucible_by_role(draft_a_role: str, draft_b_role: str) -> list[dict]:
    return [
        {"id": "da", "kind": "task", "stage": "draft", "role": draft_a_role},
        {"id": "db", "kind": "task", "stage": "draft", "role": draft_b_role},
        {"id": "crit", "kind": "critique", "stage": "critique", "depends_on": ["da", "db"]},
        {"id": "syn", "kind": "task", "stage": "synthesis", "depends_on": ["da", "db", "crit"]},
        {"id": "g", "kind": "judge", "stage": "gate", "depends_on": ["syn"]},
    ]


def test_drafts_resolved_by_role_distinct_families_no_warning() -> None:
    # Steps bind to agents by ROLE (Kim's real YAML); families derived from
    # the recruited agents, not from explicit per-step provider/model.
    steps = _crucible_by_role("drafter_a", "drafter_b")
    catalog = [
        _Agent("claude-code", "claude-opus", role="drafter_a"),   # anthropic
        _Agent("gemini", "gemini-2.0", role="drafter_b"),          # google
    ]
    warns = validate_crucible_shape(steps, catalog=catalog)
    assert not any("dégénéré" in w or "dégradé" in w for w in warns)


def test_drafts_resolved_by_role_same_family_with_alternatives_faults() -> None:
    steps = _crucible_by_role("drafter_a", "drafter_b")
    # Both draft roles resolve to anthropic, but google was on the bench.
    catalog = [
        _Agent("claude-code", "claude-opus", role="drafter_a"),
        _Agent("claude-code", "claude-sonnet", role="drafter_b"),
        _Agent("gemini", "gemini-2.0", role="reviewer"),
    ]
    warns = validate_crucible_shape(steps, catalog=catalog)
    assert any("dégénéré" in w for w in warns)


def test_step_family_prefers_precomputed_provider_family() -> None:
    # provider_family, when set on the agent, wins over deriving from model.
    steps = _crucible_by_role("drafter_a", "drafter_b")
    catalog = [
        _Agent("openrouter", "some-obscure/model", role="drafter_a",
               provider_family="anthropic"),
        _Agent("openrouter", "another/model", role="drafter_b",
               provider_family="google"),
    ]
    warns = validate_crucible_shape(steps, catalog=catalog)
    assert not any("dégénéré" in w for w in warns)
