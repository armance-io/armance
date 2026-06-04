"""Tests for Claim model and ClaimLedgerService.

Covers:
* Claim serialization / deserialization (to_dict / from_dict).
* ClaimLedgerService.append_claim — atomic writes, ID collision.
* ClaimLedgerService.verify_claim — status patch, StatusMeta recording.
* ClaimLedgerService.get_claims — filtering by status, by, view, confidence.
* ClaimLedgerService.get_claims_by_view / get_claims_by_agent / get_unverified.
* ClaimLedgerService.delete_claim — soft-delete via unsourced.
* ClaimLedgerService.rebuild_index — index rebuild from JSONL.
* Edge cases: empty evidence, corrupt lines, missing ledger file.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from armance.core.models.claim import (
    Claim,
    ClaimStatus,
    Confidence,
    Evidence,
    EvidenceKind,
    StatusMeta,
)
from armance.service.claim_ledger_service import (
    ClaimLedgerError,
    ClaimLedgerService,
    ClaimNotFoundError,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


_DEFAULT_EVIDENCE = [Evidence(kind=EvidenceKind.DOC, ref="docs/fab.pdf#p.42")]


def _make_claim(
    id: str = "c_a4f9k2pq",
    by: str = "historian-aisha",
    view: str = "wf:r_x9f4k2pq",
    step: str | None = "outline",
    text: str = "L'indigotier dominait les teintures bleues.",
    evidence: list[Evidence] | None | object = None,
    confidence: Confidence = Confidence.ASSERTED,
    status: ClaimStatus = ClaimStatus.UNVERIFIED,
    ts: datetime | None = None,
) -> Claim:
    """Helper to build a Claim with sensible defaults."""
    if evidence is None:
        ev = list(_DEFAULT_EVIDENCE)
    elif evidence is ...:  # sentinel for "force default even if explicitly passed"
        ev = list(_DEFAULT_EVIDENCE)
    else:
        ev = evidence
    return Claim(
        id=id,
        by=by,
        ts=ts or datetime(2026, 5, 4, 14, 30, 0, tzinfo=timezone.utc),
        view=view,
        step=step,
        text=text,
        evidence=ev,
        confidence=confidence,
        status=status,
    )


@pytest.fixture()
def service(tmp_path: Path) -> ClaimLedgerService:
    """Create a ClaimLedgerService backed by a temporary directory."""
    return ClaimLedgerService(tmp_path)


# ---------------------------------------------------------------------------
# Claim model tests
# ---------------------------------------------------------------------------


class TestClaimModel:
    """Tests for the Claim data model."""

    def test_generate_id_format(self) -> None:
        """Generated IDs must match c_<8 base36 chars>."""
        cid = Claim.generate_id()
        assert cid.startswith("c_")
        assert len(cid) == 10  # 2 prefix + 8 chars

    def test_generate_id_uniqueness(self) -> None:
        """Multiple generated IDs must be unique."""
        ids = {Claim.generate_id() for _ in range(100)}
        assert len(ids) == 100

    def test_to_dict_roundtrip(self) -> None:
        """to_dict -> from_dict must preserve all fields."""
        claim = _make_claim()
        d = claim.to_dict()
        restored = Claim.from_dict(d)
        assert restored.id == claim.id
        assert restored.by == claim.by
        assert restored.view == claim.view
        assert restored.step == claim.step
        assert restored.text == claim.text
        assert len(restored.evidence) == len(claim.evidence)
        assert restored.evidence[0].kind == claim.evidence[0].kind
        assert restored.evidence[0].ref == claim.evidence[0].ref
        assert restored.confidence == claim.confidence
        assert restored.status == claim.status
        assert restored.status_meta is None

    def test_to_dict_with_status_meta(self) -> None:
        """Claims with status_meta must serialize and deserialize correctly."""
        claim = _make_claim()
        claim.status = ClaimStatus.VERIFIED
        claim.status_meta = StatusMeta(
            by="system-judge",
            ts=datetime(2026, 5, 4, 15, 0, 0, tzinfo=timezone.utc),
            rationale="Supported by primary source.",
            contradicting_claim="c_b8e1m3xx",
        )
        d = claim.to_dict()
        assert d["status_meta"] is not None
        assert d["status_meta"]["by"] == "system-judge"
        assert d["status_meta"]["contradicting_claim"] == "c_b8e1m3xx"
        restored = Claim.from_dict(d)
        assert restored.status_meta is not None
        assert restored.status_meta.by == "system-judge"
        assert restored.status_meta.contradicting_claim == "c_b8e1m3xx"

    def test_to_dict_empty_evidence(self) -> None:
        """Claims with empty evidence list must serialize correctly."""
        claim = _make_claim(evidence=[])
        d = claim.to_dict()
        assert d["evidence"] == []
        restored = Claim.from_dict(d)
        assert restored.evidence == []

    def test_to_dict_null_step(self) -> None:
        """Claims with step=None must not include step in dict."""
        claim = _make_claim(step=None)
        d = claim.to_dict()
        assert "step" not in d
        restored = Claim.from_dict(d)
        assert restored.step is None

    def test_text_max_length(self) -> None:
        """Text must be limited to 500 characters."""
        with pytest.raises(Exception):  # Pydantic validation error
            Claim(
                id="c_test0001",
                by="test-agent",
                view="open-space",
                text="x" * 501,
                confidence=Confidence.ASSERTED,
            )

    def test_from_dict_with_z_timestamp(self) -> None:
        """Timestamps ending with Z must parse correctly."""
        data: dict = {
            "id": "c_test0002",
            "by": "test-agent",
            "ts": "2026-05-04T14:30:00Z",
            "view": "open-space",
            "text": "Test claim",
            "evidence": [],
            "confidence": "asserted",
            "status": "unverified",
            "status_meta": None,
        }
        claim = Claim.from_dict(data)
        assert claim.ts.tzinfo is not None


# ---------------------------------------------------------------------------
# ClaimLedgerService tests
# ---------------------------------------------------------------------------


class TestClaimLedgerService:
    """Tests for ClaimLedgerService."""

    def test_append_claim_creates_file(self, service: ClaimLedgerService, tmp_path: Path) -> None:
        """append_claim must create the JSONL file and index."""
        claim = _make_claim()
        service.append_claim(claim)
        assert service._ledger_path.exists()
        assert service._index_path.exists()
        assert claim.id in service._index

    def test_append_claim_jsonl_format(self, service: ClaimLedgerService) -> None:
        """Each line in the JSONL file must be valid JSON."""
        claim = _make_claim(id="c_line0001")
        service.append_claim(claim)
        with open(service._ledger_path, "r", encoding="utf-8") as fh:
            lines = [l.strip() for l in fh.readlines() if l.strip()]
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["id"] == "c_line0001"

    def test_append_multiple_claims(self, service: ClaimLedgerService) -> None:
        """Multiple claims must be appended correctly."""
        c1 = _make_claim(id="c_multi001")
        c2 = _make_claim(id="c_multi002", view="dm:historian")
        service.append_claim(c1)
        service.append_claim(c2)
        assert len(service._index) == 2
        with open(service._ledger_path, "r", encoding="utf-8") as fh:
            lines = [l.strip() for l in fh.readlines() if l.strip()]
        assert len(lines) == 2

    def test_append_claim_id_collision(self, service: ClaimLedgerService) -> None:
        """Appending a claim with a duplicate ID must raise ClaimLedgerError."""
        claim = _make_claim()
        service.append_claim(claim)
        duplicate = _make_claim(id=claim.id)
        with pytest.raises(ClaimLedgerError, match="already exists"):
            service.append_claim(duplicate)

    def test_verify_claim_success(self, service: ClaimLedgerService) -> None:
        """verify_claim must update status and status_meta."""
        claim = _make_claim()
        service.append_claim(claim)
        service.verify_claim(
            claim_id=claim.id,
            verdict=ClaimStatus.VERIFIED,
            rationale="Supported by primary source.",
            by="system-judge",
        )
        assert service._index[claim.id].status == ClaimStatus.VERIFIED
        meta = service._index[claim.id].status_meta
        assert meta is not None
        assert meta.by == "system-judge"
        assert meta.rationale == "Supported by primary source."

    def test_verify_claim_not_found(self, service: ClaimLedgerService) -> None:
        """verify_claim on a non-existent ID must raise ClaimNotFoundError."""
        with pytest.raises(ClaimNotFoundError, match="not found"):
            service.verify_claim(
                claim_id="c_nonexistent",
                verdict=ClaimStatus.VERIFIED,
                rationale="test",
                by="system-judge",
            )

    def test_verify_claim_terminal_statuses(self, service: ClaimLedgerService) -> None:
        """verify_claim must accept terminal statuses (verified, refuted)."""
        claim = _make_claim()
        service.append_claim(claim)
        for verdict in (ClaimStatus.VERIFIED, ClaimStatus.REFUTED):
            service.verify_claim(
                claim_id=claim.id,
                verdict=verdict,
                rationale="test rationale",
                by="system-judge",
            )
            assert service._index[claim.id].status == verdict

    def test_verify_claim_with_contradicting(self, service: ClaimLedgerService) -> None:
        """verify_claim must record contradicting_claim in status_meta."""
        c1 = _make_claim(id="c_contra001")
        c2 = _make_claim(id="c_contra002")
        service.append_claim(c1)
        service.append_claim(c2)
        service.verify_claim(
            claim_id=c1.id,
            verdict=ClaimStatus.DISPUTED,
            rationale="Contradicts c_contra002",
            by="system-challenger",
            contradicting_claim="c_contra002",
        )
        meta = service._index[c1.id].status_meta
        assert meta is not None
        assert meta.contradicting_claim == "c_contra002"

    def test_get_claims_no_filter(self, service: ClaimLedgerService) -> None:
        """get_claims without filter must return all claims."""
        c1 = _make_claim(id="c_all001")
        c2 = _make_claim(id="c_all002")
        service.append_claim(c1)
        service.append_claim(c2)
        all_claims = service.get_claims()
        assert len(all_claims) == 2

    def test_get_claims_filter_by_status(self, service: ClaimLedgerService) -> None:
        """get_claims must filter by status when specified."""
        c1 = _make_claim(id="c_st001", status=ClaimStatus.UNVERIFIED)
        c2 = _make_claim(id="c_st002", status=ClaimStatus.VERIFIED)
        service.append_claim(c1)
        service.append_claim(c2)
        unverified = service.get_claims(filter={"status": ClaimStatus.UNVERIFIED})
        assert len(unverified) == 1
        assert unverified[0].id == "c_st001"

    def test_get_claims_filter_by_agent(self, service: ClaimLedgerService) -> None:
        """get_claims must filter by agent name."""
        c1 = _make_claim(id="c_ag001", by="historian-aisha")
        c2 = _make_claim(id="c_ag002", by="historian-lars")
        service.append_claim(c1)
        service.append_claim(c2)
        aisha_claims = service.get_claims(filter={"by": "historian-aisha"})
        assert len(aisha_claims) == 1
        assert aisha_claims[0].id == "c_ag001"

    def test_get_claims_filter_by_view(self, service: ClaimLedgerService) -> None:
        """get_claims must filter by view reference."""
        c1 = _make_claim(id="c_vw001", view="wf:r_x9f4k2pq")
        c2 = _make_claim(id="c_vw002", view="open-space")
        service.append_claim(c1)
        service.append_claim(c2)
        wf_claims = service.get_claims(filter={"view": "wf:r_x9f4k2pq"})
        assert len(wf_claims) == 1
        assert wf_claims[0].id == "c_vw001"

    def test_get_claims_sorted_descending(self, service: ClaimLedgerService) -> None:
        """get_claims must return claims sorted by timestamp descending."""
        ts1 = datetime(2026, 5, 4, 14, 0, 0, tzinfo=timezone.utc)
        ts2 = datetime(2026, 5, 4, 15, 0, 0, tzinfo=timezone.utc)
        c1 = _make_claim(id="c_ts001", ts=ts1)
        c2 = _make_claim(id="c_ts002", ts=ts2)
        service.append_claim(c1)
        service.append_claim(c2)
        claims = service.get_claims()
        assert claims[0].id == "c_ts002"
        assert claims[1].id == "c_ts001"

    def test_get_claims_by_view(self, service: ClaimLedgerService) -> None:
        """get_claims_by_view must return claims for a specific view."""
        c1 = _make_claim(id="c_bv001", view="wf:r_x9f4k2pq")
        c2 = _make_claim(id="c_bv002", view="open-space")
        service.append_claim(c1)
        service.append_claim(c2)
        wf_claims = service.get_claims_by_view("wf:r_x9f4k2pq")
        assert len(wf_claims) == 1
        assert wf_claims[0].id == "c_bv001"

    def test_get_claims_by_agent(self, service: ClaimLedgerService) -> None:
        """get_claims_by_agent must return claims by a specific agent."""
        c1 = _make_claim(id="c_ba001", by="historian-aisha")
        c2 = _make_claim(id="c_ba002", by="historian-lars")
        service.append_claim(c1)
        service.append_claim(c2)
        aisha_claims = service.get_claims_by_agent("historian-aisha")
        assert len(aisha_claims) == 1
        assert aisha_claims[0].id == "c_ba001"

    def test_get_unverified(self, service: ClaimLedgerService) -> None:
        """get_unverified must return only unverified claims."""
        c1 = _make_claim(id="c_uv001", status=ClaimStatus.UNVERIFIED)
        c2 = _make_claim(id="c_uv002", status=ClaimStatus.VERIFIED)
        service.append_claim(c1)
        service.append_claim(c2)
        unverified = service.get_unverified()
        assert len(unverified) == 1
        assert unverified[0].id == "c_uv001"

    def test_get_unverified_scoped_to_view(self, service: ClaimLedgerService) -> None:
        """get_unverified with view must scope the query."""
        c1 = _make_claim(id="c_uv003", status=ClaimStatus.UNVERIFIED, view="wf:r_x9f4k2pq")
        c2 = _make_claim(id="c_uv004", status=ClaimStatus.UNVERIFIED, view="open-space")
        service.append_claim(c1)
        service.append_claim(c2)
        wf_unverified = service.get_unverified(view="wf:r_x9f4k2pq")
        assert len(wf_unverified) == 1
        assert wf_unverified[0].id == "c_uv003"

    def test_delete_claim_soft_deletes(self, service: ClaimLedgerService) -> None:
        """delete_claim must mark the claim as unsourced."""
        claim = _make_claim(id="c_del001")
        service.append_claim(claim)
        service.delete_claim(claim.id)
        assert service._index[claim.id].status == ClaimStatus.UNSOURCED
        # Must not raise on re-delete
        service.delete_claim(claim.id)

    def test_delete_claim_not_found(self, service: ClaimLedgerService) -> None:
        """delete_claim on non-existent ID must raise ClaimNotFoundError."""
        with pytest.raises(ClaimNotFoundError):
            service.delete_claim("c_nonexistent")

    def test_rebuild_index(self, service: ClaimLedgerService) -> None:
        """rebuild_index must reconstruct the index from JSONL."""
        c1 = _make_claim(id="c_rbuild01")
        c2 = _make_claim(id="c_rbuild02")
        service.append_claim(c1)
        service.append_claim(c2)
        # Clear in-memory index
        service._index = {}
        service.rebuild_index()
        assert len(service._index) == 2
        assert "c_rbuild01" in service._index
        assert "c_rbuild02" in service._index

    def test_rebuild_index_preserves_status(self, service: ClaimLedgerService) -> None:
        """rebuild_index must preserve verified status after verification."""
        claim = _make_claim(id="c_rbuild03")
        service.append_claim(claim)
        service.verify_claim(
            claim_id=claim.id,
            verdict=ClaimStatus.VERIFIED,
            rationale="test",
            by="system-judge",
        )
        service._index = {}
        service.rebuild_index()
        assert service._index[claim.id].status == ClaimStatus.VERIFIED
        assert service._index[claim.id].status_meta is not None

    def test_empty_evidence_claim(self, service: ClaimLedgerService) -> None:
        """Claims with empty evidence must be appendable."""
        claim = _make_claim(id="c_empty001", evidence=[])
        service.append_claim(claim)
        assert len(service._index) == 1
        assert service._index["c_empty001"].evidence == []

    def test_atomic_write_preserves_data(self, service: ClaimLedgerService) -> None:
        """Atomic writes must preserve all existing claims."""
        claims = [_make_claim(id=f"c_atom{i:04d}") for i in range(10)]
        for c in claims:
            service.append_claim(c)
        # Verify all claims are in the file
        with open(service._ledger_path, "r", encoding="utf-8") as fh:
            lines = [l.strip() for l in fh.readlines() if l.strip()]
        assert len(lines) == 10
        for c in claims:
            assert c.id in service._index

    def test_index_file_created_on_init(self, service: ClaimLedgerService) -> None:
        """Index file must be created even when ledger is empty."""
        assert service._index_path.exists()
        assert len(service._index) == 0

    def test_append_claim_no_ledger_file(self, service: ClaimLedgerService) -> None:
        """append_claim must work when no ledger file exists yet."""
        # Ensure no ledger file exists
        if service._ledger_path.exists():
            service._ledger_path.unlink()
        claim = _make_claim(id="c_nofile01")
        service.append_claim(claim)
        assert service._ledger_path.exists()
        assert claim.id in service._index
