"""Regression: confrontation detector triggers Mona auto-invocation.

When two consecutive deliverables contain opposite stance markers,
detect_confrontation() must return True, and the workflow engine must
emit a confrontation_detected event.
"""
from __future__ import annotations

import pytest

from armance.service.agents.confrontation import (
    detect_confrontation,
    STANCE_PATTERNS,
)


AFFIRM_DELIVERABLE = (
    "La garance était la principale teinture rouge. "
    "Je soutiens cette hypothèse. Evidence solide."
)

CONTRADICT_DELIVERABLE = (
    "Non, la garance n'était pas dominante dans la région du nord. "
    "Je conteste cette affirmation. Les sources sont insuffisantes."
)

NEUTRAL_DELIVERABLE_1 = "La teinture était utilisée dans les ateliers."
NEUTRAL_DELIVERABLE_2 = "Les marchands importaient aussi d'autres matières."


def test_opposite_stances_detected() -> None:
    """Affirm + contradict = confrontation."""
    assert detect_confrontation(AFFIRM_DELIVERABLE, CONTRADICT_DELIVERABLE) is True


def test_same_stance_no_confrontation() -> None:
    """Affirm + affirm = no confrontation."""
    assert detect_confrontation(AFFIRM_DELIVERABLE, AFFIRM_DELIVERABLE) is False


def test_neutral_deliverables_no_confrontation() -> None:
    """Neutral + neutral = no confrontation."""
    assert detect_confrontation(NEUTRAL_DELIVERABLE_1, NEUTRAL_DELIVERABLE_2) is False


def test_reversed_order_still_detected() -> None:
    """contradict + affirm = confrontation (order independent)."""
    assert detect_confrontation(CONTRADICT_DELIVERABLE, AFFIRM_DELIVERABLE) is True


def test_stance_patterns_have_affirm_and_contradict() -> None:
    """STANCE_PATTERNS must define both 'affirm' and 'contradict' groups."""
    assert "affirm" in STANCE_PATTERNS
    assert "contradict" in STANCE_PATTERNS
    assert len(STANCE_PATTERNS["affirm"]) >= 3
    assert len(STANCE_PATTERNS["contradict"]) >= 3


# Engine-integration test for confrontation_detected event was dropped
# alongside the rich WorkflowEngine deletion. The detect_confrontation()
# helper is still exercised above. The event-stream wiring can be
# re-added against execute_workflow's notify hook if/when a consumer
# needs it.
