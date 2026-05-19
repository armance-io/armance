"""Claim model for the cross-agent claim ledger.

Defines the ``Claim`` data class and supporting enums used by
:mod:`armance.service.claim_ledger_service` to record, verify, and query
factual assertions across agents.

Schema reference: :doc:`../spec/19_claim_ledger`
"""

from __future__ import annotations

import secrets
import string
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Confidence(str, Enum):
    """Writer self-assessed certainty."""

    ASSERTED = "asserted"
    TENTATIVE = "tentative"
    SPECULATIVE = "speculative"


class ClaimStatus(str, Enum):
    """Verifier verdict on a claim."""

    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    DISPUTED = "disputed"
    REFUTED = "refuted"
    UNSOURCED = "unsourced"


class EvidenceKind(str, Enum):
    """Type of evidence reference."""

    DOC = "doc"
    CONTEXT = "context"
    CLAIM = "claim"
    DECISION = "decision"
    DELIVERABLE = "deliverable"
    EXTERNAL = "external"


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------

class Evidence(BaseModel):
    """Single evidence reference attached to a claim.

    Attributes:
        kind: Category of the evidence source.
        ref:  Pointer to the source (path, URL, claim id, …).
    """

    kind: EvidenceKind
    ref: str


# ---------------------------------------------------------------------------
# Status metadata
# ---------------------------------------------------------------------------

class StatusMeta(BaseModel):
    """Verifier metadata recorded when a claim status changes.

    Attributes:
        by:              Canonical name of the verifier agent.
        ts:              ISO-8601 timestamp of the verification action.
        rationale:       One-line explanation for the verdict.
        contradicting_claim: ID of a claim that contradicts this one (optional).
    """

    by: str
    ts: datetime
    rationale: str
    contradicting_claim: str | None = None


# ---------------------------------------------------------------------------
# Claim
# ---------------------------------------------------------------------------

class Claim(BaseModel):
    """A factual assertion made by an agent.

    This is the core record written to the claim ledger
    (``.armance/shared_memory/claims.jsonl``).

    Attributes:
        id:          Globally unique identifier ``c_<8-char-base36>``.
        by:          Canonical agent name that authored the claim.
        ts:          Write timestamp (UTC).
        view:        View reference where the claim was made (e.g. ``wf:r_x9f4k2pq``).
        step:        Workflow step ID that produced the claim, or ``None``.
        text:        The assertion verbatim (≤ 500 chars).
        evidence:    List of evidence references; may be empty ``[]``.
        confidence:  Writer self-label of certainty.
        status:      Current verifier verdict.
        status_meta: Verifier metadata (``None`` until first verification).
    """

    id: str
    by: str
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    view: str
    step: str | None = None
    text: str = Field(..., max_length=500)
    evidence: list[Evidence] = Field(default_factory=list)
    confidence: Confidence
    status: ClaimStatus = ClaimStatus.UNVERIFIED
    status_meta: StatusMeta | None = None

    # -- helpers ----------------------------------------------------------

    @staticmethod
    def generate_id() -> str:
        """Generate a new claim id ``c_<8 base36 chars>``."""
        chars = string.ascii_lowercase + string.digits
        suffix = "".join(secrets.choice(chars) for _ in range(8))
        return f"c_{suffix}"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict suitable for JSONL writing."""
        data: dict[str, Any] = {
            "id": self.id,
            "by": self.by,
            "ts": self.ts.isoformat().replace("+00:00", "Z"),
            "view": self.view,
            "text": self.text,
            "evidence": [e.model_dump() for e in self.evidence],
            "confidence": self.confidence.value,
            "status": self.status.value,
        }
        if self.step is not None:
            data["step"] = self.step
        if self.status_meta is not None:
            data["status_meta"] = {
                "by": self.status_meta.by,
                "ts": self.status_meta.ts.isoformat().replace("+00:00", "Z"),
                "rationale": self.status_meta.rationale,
                "contradicting_claim": self.status_meta.contradicting_claim,
            }
        else:
            data["status_meta"] = None
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Claim:
        """Deserialize from a plain dict read from JSONL."""
        # Parse timestamp — accept both ISO with Z and +00:00
        ts_raw = data.get("ts", "")
        if ts_raw.endswith("Z"):
            ts_raw = ts_raw[:-1] + "+00:00"
        ts = datetime.fromisoformat(ts_raw)

        evidence_raw = data.get("evidence", [])
        evidence = [Evidence(kind=EvidenceKind(e["kind"]), ref=e["ref"]) for e in evidence_raw]

        confidence = Confidence(data["confidence"])
        status = ClaimStatus(data["status"])

        status_meta_raw = data.get("status_meta")
        status_meta: StatusMeta | None = None
        if status_meta_raw is not None:
            meta_ts = status_meta_raw.get("ts", "")
            if meta_ts.endswith("Z"):
                meta_ts = meta_ts[:-1] + "+00:00"
            status_meta = StatusMeta(
                by=status_meta_raw["by"],
                ts=datetime.fromisoformat(meta_ts),
                rationale=status_meta_raw["rationale"],
                contradicting_claim=status_meta_raw.get("contradicting_claim"),
            )

        return cls(
            id=data["id"],
            by=data["by"],
            ts=ts,
            view=data["view"],
            step=data.get("step"),
            text=data["text"],
            evidence=evidence,
            confidence=confidence,
            status=status,
            status_meta=status_meta,
        )
