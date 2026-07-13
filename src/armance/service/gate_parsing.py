"""Creuset gate-tag / score parsing (Lot F4), split out of `agent_sandbox.py`
to keep that module under the 300-LOC limit. Re-exported from agent_sandbox
(the tag-scrubber home) for callers that expect it there.

The `[GATE:...]` tag is in the same structured-tag family as `[EXECUTE:/...]`.
The score-table format is the STABLE contract read by the Lot H report code.
"""
from __future__ import annotations

import re
from typing import Literal

_GATE_VERDICT_RE = re.compile(r"\[GATE:(ACCEPT|REVISE)\]")
# One rubric row of the gate's markdown score table (see parse_gate_scores).
_GATE_SCORE_ROW_RE = re.compile(
    r"^\s*\|(?P<name>[^|]+)\|\s*(?P<score>[0-9]+(?:\.[0-9]+)?)\s*(?:/\s*10)?\s*\|",
)


def parse_gate_verdict(text: str) -> Literal["ACCEPT", "REVISE"] | None:
    """Gate's terminal verdict; last `[GATE:ACCEPT|REVISE]` tag wins, None if
    no tag (callers treat absence as a broken gate → REVISE + warning)."""
    tags = _GATE_VERDICT_RE.findall(text)
    return tags[-1] if tags else None  # type: ignore[return-value]


def parse_gate_scores(text: str) -> dict[str, float]:
    """Extract per-criterion scores from a gate's STABLE markdown-table format.

    Contract (Lot H reads this — keep it stable): a table with header row
    ``| Criterion | Score |`` and rows ``| <name> | <n>/10 |`` (the ``/10`` is
    optional — a bare ``<n>`` parses too). Tolerant: whitespace stripped,
    separator rows (``|---|---|``) and the header row ignored. Returns {} when
    no scored rows are found. E.g. ``| Coverage | 8/10 |`` → ``{"Coverage": 8.0}``.
    """
    scores: dict[str, float] = {}
    for line in text.splitlines():
        m = _GATE_SCORE_ROW_RE.match(line)
        if m is None:
            continue
        name = m.group("name").strip()
        # Skip the header row and markdown separator rows.
        if not name or set(name) <= {"-", ":", " "} or name.lower() == "criterion":
            continue
        try:
            scores[name] = float(m.group("score"))
        except ValueError:  # pragma: no cover — regex already guarantees a number
            continue
    return scores
