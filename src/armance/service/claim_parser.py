"""Claim parser — extract ``Claim`` objects from specialist deliverable text.

This module implements **Path A** of the claim ledger spec
(:doc:`../spec/19_claim_ledger`): inline annotation via ``[[claim ...]]``
blocks embedded in LLM-generated deliverables.

Expected input format
---------------------
A specialist's deliverable may contain zero or more claim blocks using the
following micro-syntax::

    [[claim id=c_a4f9k2pq evidence="docs/fab.pdf#p.42" confidence=asserted]]
    L'indigotier dominait les teintures bleues.
    [[/claim]]

Fields on the opening tag:

+---------------+------------------------+------------------------------------------+
| Field         | Required               | Notes                                    |
+---------------+------------------------+------------------------------------------+
| ``id``        | No (auto-generated)    | ``c_<8 base36>``; omitted → generated.  |
| ``evidence``  | No (empty list default)| Single ref or comma-separated refs.      |
|               |                        | Format: ``kind:ref`` or just ``ref``.   |
| ``confidence``| No (``asserted``)      | ``asserted``, ``tentative``, ``speculative``. |
| ``by``        | No (``unknown``)       | Canonical agent name.                    |
| ``view``      | No (``open-space``)    | ViewRef string.                          |
| ``step``      | No                     | Workflow step ID.                        |
+---------------+------------------------+------------------------------------------+

The block body (between opening and closing tags) is the claim ``text``.

Usage
-----
::

    from armance.service.claim_parser import parse_claims
    from armance.service.claim_ledger_service import ClaimLedgerService

    claims = parse_claims(llm_output)
    for claim in claims:
        ledger.append_claim(claim)

Error handling
--------------
Malformed blocks (unclosed tags, missing required fields, invalid JSON) raise
``ClaimSchemaError`` with a descriptive message.  This ensures callers can
detect and report parsing failures rather than silently losing claims.

.. versionadded:: 0.2.0
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from armance.core.models.claim import (
    Claim,
    ClaimStatus,
    Confidence,
    Evidence,
    EvidenceKind,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class ClaimSchemaError(Exception):
    """Raised when a claim block fails schema validation.

    This replaces the previous silent-skip behavior for malformed claims.
    Callers should catch this exception to handle parsing errors explicitly.
    """


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Matches [[claim ...]] with key=value pairs (values may be quoted).
_OPENING_TAG_RE = re.compile(
    r"\[\[claim\s+"  # opening bracket + keyword + whitespace
    r"(.+?)"  # capture key=value pairs (non-greedy)
    r"\]\]",  # closing bracket
    re.DOTALL,
)

# Matches [[/claim]]
_CLOSING_TAG_RE = re.compile(r"\[\[/claim\]\]", re.IGNORECASE)

# Matches a single key=value pair.
# Values can be quoted ("..." or '...') or unquoted (no spaces).
_KV_RE = re.compile(
    r'(\w+?)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|(\S+))'
)

# Evidence ref: kind:ref or bare ref
_EVIDENCE_RE = re.compile(
    r"^(?:(\w+):)?(.+)$"
)


def _parse_kv_pairs(kv_string: str) -> dict[str, str]:
    """Parse a string of key=value pairs into a dict.

    Handles quoted and unquoted values.  Unknown keys are included
    verbatim so callers can ignore them.

    Args:
        kv_string: Raw key=value string from the opening tag.

    Returns:
        Dict mapping field names to their string values.
    """
    result: dict[str, str] = {}
    for match in _KV_RE.finditer(kv_string):
        key = match.group(1).lower()
        # Group 2 = double-quoted, 3 = single-quoted, 4 = unquoted
        value = match.group(2) or match.group(3) or match.group(4) or ""
        result[key] = value
    return result


def _parse_evidence(evidence_raw: str) -> list[Evidence]:
    """Parse an evidence string into a list of Evidence objects.

    Accepts comma-separated refs.  Each ref may be ``kind:ref`` or bare ``ref``.

    Args:
        evidence_raw: Comma-separated evidence string.

    Returns:
        List of Evidence instances.
    """
    results: list[Evidence] = []
    for part in evidence_raw.split(","):
        part = part.strip()
        if not part:
            continue
        m = _EVIDENCE_RE.match(part)
        if m:
            kind_str = m.group(1)
            ref = m.group(2).strip()
            if kind_str:
                try:
                    kind = EvidenceKind(kind_str.lower())
                except ValueError:
                    # Unknown kind — treat as doc
                    kind = EvidenceKind.DOC
                    logger.warning("Unknown evidence kind '%s', defaulting to doc", kind_str)
            else:
                kind = EvidenceKind.DOC
            results.append(Evidence(kind=kind, ref=ref))
    return results


def _parse_claim_block(
    opening_tag: str,
    body: str,
    defaults: dict[str, str] | None = None,
) -> Claim:
    """Parse a single claim block into a Claim instance.

    Args:
        opening_tag: Raw key=value string from the opening tag.
        body: The claim text between tags.
        defaults: Default values for ``by``, ``view``, ``step`` injected
            by the emission hook.

    Returns:
        A Claim instance.

    Raises:
        ClaimSchemaError: If required fields are missing or invalid.
    """
    kv = _parse_kv_pairs(opening_tag)

    # Merge defaults (caller-provided)
    if defaults:
        for k, v in defaults.items():
            kv.setdefault(k, v)

    # Extract fields
    text = body.strip()
    if not text:
        raise ClaimSchemaError("Claim block has empty body")

    # Confidence
    conf_str = kv.get("confidence", "asserted")
    try:
        confidence = Confidence(conf_str.lower())
    except ValueError:
        raise ClaimSchemaError(f"Invalid confidence '{conf_str}' (must be asserted, tentative, or speculative)")

    # Evidence
    evidence_raw = kv.get("evidence", "")
    evidence = _parse_evidence(evidence_raw)

    # By / view / step
    by = kv.get("by", "unknown")
    view = kv.get("view", "open-space")
    step = kv.get("step", None)

    # ID — auto-generate if missing
    claim_id = kv.get("id", Claim.generate_id())

    try:
        return Claim(
            id=claim_id,
            by=by,
            ts=datetime.now(timezone.utc),
            view=view,
            step=step,
            text=text[:500],  # enforce max_length
            evidence=evidence,
            confidence=confidence,
            status=ClaimStatus.UNVERIFIED,
        )
    except Exception as exc:
        raise ClaimSchemaError(f"Failed to construct Claim from block: {exc}") from exc


def parse_claims(
    text: str,
    defaults: dict[str, str] | None = None,
) -> list[Claim]:
    """Parse claim blocks from the given text and return Claim instances.

    Scans the text for ``[[claim ...]]...[[/claim]]`` blocks.  Malformed
    blocks and unrelated text are silently ignored (with warnings logged).

    Args:
        text: The deliverable text to scan (e.g., LLM output).
        defaults: Default key/value pairs merged into each block's attributes.
            Commonly ``{"by": "agent-name", "view": "wf:r_xxx"}``.

    Returns:
        List of parsed Claim instances (may be empty).
    """
    if not text:
        return []

    claims: list[Claim] = []
    defaults = defaults or {}

    # Find all opening tags — store (kv_string, start_pos, end_pos)
    openings: list[tuple[str, int, int]] = []
    for m in _OPENING_TAG_RE.finditer(text):
        openings.append((m.group(1), m.start(), m.end()))

    for i, (kv_str, open_start, open_end) in enumerate(openings):
        # Find the next closing tag after this opening
        close_m = _CLOSING_TAG_RE.search(text, open_start)
        if close_m is None:
            raise ClaimSchemaError(f"Unclosed claim tag at position {open_start}")

        # Body is between the end of the opening tag and the start of the closing tag
        body = text[open_end: close_m.start()].strip()

        claim = _parse_claim_block(kv_str, body, defaults)
        claims.append(claim)

    return claims


# ---------------------------------------------------------------------------
# Convenience: parse from file
# ---------------------------------------------------------------------------


def parse_claims_from_file(
    path: Path | str,
    defaults: dict[str, str] | None = None,
) -> list[Claim]:
    """Read a file and parse claim blocks from its contents.

    Args:
        path: Path to the file (e.g., a specialist deliverable).
        defaults: Default key/value pairs for each claim.

    Returns:
        List of parsed Claim instances.
    """
    p = Path(path)
    if not p.exists():
        logger.warning("File not found: %s", p)
        return []
    text = p.read_text(encoding="utf-8")
    return parse_claims(text, defaults=defaults)
