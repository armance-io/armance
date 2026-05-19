"""Tests for ClaimParser and claim emission into the ledger.

Covers:
* parse_claims — successful parsing of correctly formatted claim blocks.
* parse_claims — ignoring malformed or unrelated text.
* parse_claims_from_file — reading from file.
* Emission flow: mock ClaimLedgerService and verify append_claim calls.
* Edge cases: empty evidence, auto-generated IDs, invalid confidence.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from armance.core.models.claim import (
    Claim,
    ClaimStatus,
    Confidence,
    Evidence,
    EvidenceKind,
)
from armance.service.claim_ledger_service import ClaimLedgerService
from armance.service.claim_parser import (
    _parse_claim_block,
    _parse_evidence,
    _parse_kv_pairs,
    parse_claims,
    parse_claims_from_file,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


SAMPLE_TEXT = """Here is the analysis of the medieval textile trade.

[[claim id=c_a4f9k2pq evidence="docs/fab.pdf#p.42" confidence=asserted]]
L'indigotier dominait les teintures bleues européennes au XIVe siècle.
[[/claim]]

Other prose that is not a claim.

[[claim evidence="docs/textile.md#ch3" confidence=tentative by=historian-aisha view=wf:r_x9f]]
The wool trade was concentrated in Flanders.
[[/claim]]

More unrelated text.
"""

MALFORMED_TEXT = """Some text before.

[[claim evidence="docs/x.md" confidence=asserted]]
Valid claim before the bad one.
[[/claim]]

[[claim evidence="docs/bad.md" confidence=invalid_conf]]
This has invalid confidence.
[[/claim]]

[[claim evidence="docs/orphan.md" confidence=asserted]]
This tag is never closed.

End of text with no closing tag.
"""

EMPTY_TEXT = ""

NO_CLAIMS_TEXT = "Just plain prose with no claim markers at all."


# ---------------------------------------------------------------------------
# KV parsing tests
# ---------------------------------------------------------------------------


class TestParseKvPairs:
    """Tests for _parse_kv_pairs helper."""

    def test_simple_pairs(self) -> None:
        kv = _parse_kv_pairs('evidence="docs/x.md" confidence=asserted')
        assert kv["evidence"] == "docs/x.md"
        assert kv["confidence"] == "asserted"

    def test_single_quoted(self) -> None:
        kv = _parse_kv_pairs("by='test-agent'")
        assert kv["by"] == "test-agent"

    def test_mixed_quotes(self) -> None:
        kv = _parse_kv_pairs('name="foo" other=\'bar\' bare=baz')
        assert kv["name"] == "foo"
        assert kv["other"] == "bar"
        assert kv["bare"] == "baz"

    def test_empty_string(self) -> None:
        kv = _parse_kv_pairs("")
        assert kv == {}

    def test_unknown_keys_preserved(self) -> None:
        kv = _parse_kv_pairs("unknown_field=value")
        assert kv["unknown_field"] == "value"


# ---------------------------------------------------------------------------
# Evidence parsing tests
# ---------------------------------------------------------------------------


class TestParseEvidence:
    """Tests for _parse_evidence helper."""

    def test_kind_ref(self) -> None:
        ev = _parse_evidence("doc:docs/fab.pdf#p.42")
        assert len(ev) == 1
        assert ev[0].kind == EvidenceKind.DOC
        assert ev[0].ref == "docs/fab.pdf#p.42"

    def test_bare_ref(self) -> None:
        ev = _parse_evidence("docs/fab.pdf")
        assert len(ev) == 1
        assert ev[0].kind == EvidenceKind.DOC
        assert ev[0].ref == "docs/fab.pdf"

    def test_comma_separated(self) -> None:
        ev = _parse_evidence("doc:a.md,context:b.md,external:https://example.com")
        assert len(ev) == 3
        assert ev[0].ref == "a.md"
        assert ev[1].ref == "b.md"
        assert ev[2].ref == "https://example.com"

    def test_empty_string(self) -> None:
        ev = _parse_evidence("")
        assert ev == []

    def test_unknown_kind_defaults_to_doc(self) -> None:
        ev = _parse_evidence("unknown:ref.md")
        assert len(ev) == 1
        assert ev[0].kind == EvidenceKind.DOC


# ---------------------------------------------------------------------------
# Claim block parsing tests
# ---------------------------------------------------------------------------


class TestParseClaimBlock:
    """Tests for _parse_claim_block helper."""

    def test_full_block(self) -> None:
        claim = _parse_claim_block(
            'id=c_a4f9k2pq evidence="docs/x.md" confidence=asserted',
            "The sky is blue.",
        )
        assert claim is not None
        assert claim.id == "c_a4f9k2pq"
        assert claim.text == "The sky is blue."
        assert claim.confidence == Confidence.ASSERTED
        assert len(claim.evidence) == 1

    def test_auto_generated_id(self) -> None:
        claim = _parse_claim_block('confidence=tentative', "Some fact.")
        assert claim is not None
        assert claim.id.startswith("c_")
        assert len(claim.id) == 10

    def test_empty_body_raises(self) -> None:
        from armance.service.claim_parser import ClaimSchemaError

        with pytest.raises(ClaimSchemaError, match="empty body"):
            _parse_claim_block('evidence="x.md"', "  ")

    def test_defaults_merged(self) -> None:
        claim = _parse_claim_block(
            'evidence="x.md"',
            "Fact.",
            defaults={"by": "test-agent", "view": "wf:r_abc"},
        )
        assert claim is not None
        assert claim.by == "test-agent"
        assert claim.view == "wf:r_abc"

    def test_invalid_confidence_raises(self) -> None:
        from armance.service.claim_parser import ClaimSchemaError

        with pytest.raises(ClaimSchemaError, match="Invalid confidence"):
            _parse_claim_block(
                'confidence=maybe',
                "Fact.",
            )

    def test_text_truncated_to_500(self) -> None:
        long_text = "x" * 600
        claim = _parse_claim_block("", long_text)
        assert claim is not None
        assert len(claim.text) == 500


# ---------------------------------------------------------------------------
# parse_claims tests
# ---------------------------------------------------------------------------


class TestParseClaims:
    """Tests for the main parse_claims function."""

    def test_parse_valid_blocks(self) -> None:
        claims = parse_claims(SAMPLE_TEXT)
        assert len(claims) == 2
        assert claims[0].id == "c_a4f9k2pq"
        assert claims[1].by == "historian-aisha"
        assert claims[1].view == "wf:r_x9f"

    def test_empty_text(self) -> None:
        claims = parse_claims(EMPTY_TEXT)
        assert claims == []

    def test_no_claims(self) -> None:
        claims = parse_claims(NO_CLAIMS_TEXT)
        assert claims == []

    def test_malformed_blocks_raises(self) -> None:
        """Malformed blocks should raise ClaimSchemaError, not be silently skipped."""
        from armance.service.claim_parser import ClaimSchemaError

        with pytest.raises(ClaimSchemaError):
            parse_claims(MALFORMED_TEXT)

    def test_unclosed_tag_raises(self) -> None:
        from armance.service.claim_parser import ClaimSchemaError

        text = "[[claim evidence='x.md']]First[[/claim]]\n[[claim evidence='y.md']]No close"
        with pytest.raises(ClaimSchemaError, match="Unclosed claim tag"):
            parse_claims(text)

    def test_defaults_passed_through(self) -> None:
        text = "[[claim evidence='x.md']]Fact. [[/claim]]"
        claims = parse_claims(text, defaults={"by": "auto", "view": "dm:test"})
        assert len(claims) == 1
        assert claims[0].by == "auto"
        assert claims[0].view == "dm:test"

    def test_multiple_claims_preserve_order(self) -> None:
        text = (
            "[[claim id=c_first]]First.[[/claim]]\n"
            "[[claim id=c_second]]Second.[[/claim]]\n"
            "[[claim id=c_third]]Third.[[/claim]]"
        )
        claims = parse_claims(text)
        assert len(claims) == 3
        assert claims[0].id == "c_first"
        assert claims[1].id == "c_second"
        assert claims[2].id == "c_third"


# ---------------------------------------------------------------------------
# parse_claims_from_file tests
# ---------------------------------------------------------------------------


class TestParseClaimsFromFile:
    """Tests for parse_claims_from_file convenience function."""

    def test_parse_from_file(self, tmp_path: Path) -> None:
        f = tmp_path / "deliverable.md"
        f.write_text(SAMPLE_TEXT, encoding="utf-8")
        claims = parse_claims_from_file(f, defaults={"by": "test"})
        assert len(claims) == 2
        assert claims[0].by == "test"

    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        claims = parse_claims_from_file(tmp_path / "nonexistent.md")
        assert claims == []


# ---------------------------------------------------------------------------
# Emission integration tests
# ---------------------------------------------------------------------------


class TestClaimEmission:
    """Tests for claim emission into the ledger via SpecialistRunner."""

    def test_emit_claims_calls_append(self, tmp_path: Path) -> None:
        """Emission should call ClaimLedgerService.append_claim for each parsed claim."""
        from armance.service.agents.specialist_runner import SpecialistRunner

        runner = SpecialistRunner(tmp_path, MagicMock())

        # Mock the ledger
        mock_ledger = MagicMock(spec=ClaimLedgerService)
        runner._claim_ledger = mock_ledger

        runner._emit_claims(SAMPLE_TEXT, "historian-aisha", "open-space")

        # Should have called append_claim once per valid claim (2 in SAMPLE_TEXT)
        assert mock_ledger.append_claim.call_count == 2
        calls = mock_ledger.append_claim.call_args_list
        # First claim: defaults applied (by=historian-aisha, view=open-space)
        claim0 = calls[0].args[0]
        assert isinstance(claim0, Claim)
        assert claim0.by == "historian-aisha"
        assert claim0.view == "open-space"
        # Second claim: has its own by=view overrides from the tag
        claim1 = calls[1].args[0]
        assert isinstance(claim1, Claim)
        assert claim1.by == "historian-aisha"  # default merged
        assert claim1.view == "wf:r_x9f"  # from tag, overrides default

    def test_emit_claims_empty_content(self, tmp_path: Path) -> None:
        """Empty content should not call append_claim."""
        from armance.service.agents.specialist_runner import SpecialistRunner

        runner = SpecialistRunner(tmp_path, MagicMock())
        mock_ledger = MagicMock(spec=ClaimLedgerService)
        runner._claim_ledger = mock_ledger

        runner._emit_claims("", "agent", "open-space")

        mock_ledger.append_claim.assert_not_called()

    def test_emit_claims_no_markers(self, tmp_path: Path) -> None:
        """Content without claim markers should not call append_claim."""
        from armance.service.agents.specialist_runner import SpecialistRunner

        runner = SpecialistRunner(tmp_path, MagicMock())
        mock_ledger = MagicMock(spec=ClaimLedgerService)
        runner._claim_ledger = mock_ledger

        runner._emit_claims(NO_CLAIMS_TEXT, "agent", "open-space")

        mock_ledger.append_claim.assert_not_called()

    def test_emit_claims_ledger_error_logged(self, tmp_path: Path) -> None:
        """Duplicate claim ID should not crash emission; error is logged."""
        from armance.service.agents.specialist_runner import SpecialistRunner

        runner = SpecialistRunner(tmp_path, MagicMock())
        mock_ledger = MagicMock(spec=ClaimLedgerService)
        # Simulate append_claim raising ClaimLedgerError (duplicate ID)
        from armance.service.claim_ledger_service import ClaimLedgerError

        mock_ledger.append_claim.side_effect = ClaimLedgerError("duplicate")
        runner._claim_ledger = mock_ledger

        # Should not raise; error is caught and logged
        runner._emit_claims(SAMPLE_TEXT, "agent", "open-space")

        # append_claim was still called (the error is caught internally)
        assert mock_ledger.append_claim.call_count == 2

    def test_claim_ledger_lazy_init(self, tmp_path: Path) -> None:
        """claim_ledger property should lazily initialize."""
        from armance.service.agents.specialist_runner import SpecialistRunner

        runner = SpecialistRunner(tmp_path, MagicMock())
        assert runner._claim_ledger is None
        ledger = runner.claim_ledger
        assert isinstance(ledger, ClaimLedgerService)
        # Second access should return same instance
        assert runner.claim_ledger is ledger
