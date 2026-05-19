"""Confrontation detector — heuristic to detect opposite stance in deliverables.

When two consecutive deliverables carry opposite stance markers,
``detect_confrontation`` returns True, signalling Kim to auto-invoke Mona.

Spec: docs/spec/03_agents.md § Mona auto-invocation, T-21.
"""
from __future__ import annotations

import re
from typing import Literal

StanceGroup = Literal["affirm", "contradict", "neutral"]

STANCE_PATTERNS: dict[StanceGroup, list[str]] = {
    "affirm": [
        r"\bje soutiens\b",
        r"\bje confirme\b",
        r"\bje valide\b",
        r"\bcela est avéré\b",
        r"\bpreuve solide\b",
        r"\bevidence solide\b",
        r"\bI support\b",
        r"\bI confirm\b",
        r"\bconsensus\b",
        r"\bsupported by\b",
    ],
    "contradict": [
        r"\bje conteste\b",
        r"\bje réfute\b",
        r"\bje m'oppose\b",
        r"\bje nie\b",
        r"\bnon,\b",
        r"\bn'était pas\b",
        r"\binsuffisant[es]?\b",
        r"\bI contest\b",
        r"\bI dispute\b",
        r"\bI refute\b",
    ],
}


def _classify_stance(text: str) -> StanceGroup:
    """Return the dominant stance in a deliverable text."""
    text_lower = text.lower()
    affirm_hits = sum(
        1 for pat in STANCE_PATTERNS["affirm"] if re.search(pat, text_lower)
    )
    contradict_hits = sum(
        1 for pat in STANCE_PATTERNS["contradict"] if re.search(pat, text_lower)
    )
    if affirm_hits > 0 and contradict_hits == 0:
        return "affirm"
    if contradict_hits > 0 and affirm_hits == 0:
        return "contradict"
    return "neutral"


def detect_confrontation(deliverable_a: str, deliverable_b: str) -> bool:
    """Return True when the two deliverables carry opposite stances.

    "affirm" vs "contradict" (in any order) = confrontation.
    """
    stance_a = _classify_stance(deliverable_a)
    stance_b = _classify_stance(deliverable_b)
    return {stance_a, stance_b} == {"affirm", "contradict"}
