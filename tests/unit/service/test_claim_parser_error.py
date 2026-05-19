"""Tests for ClaimSchemaError in claim_parser.

Covers:
- Malformed claim blocks raise ClaimSchemaError
- Empty body raises ClaimSchemaError
- Invalid confidence raises ClaimSchemaError
- Unclosed tag raises ClaimSchemaError
- Valid claims still parse successfully
"""

from __future__ import annotations

import pytest

from armance.core.models.claim import Claim, Confidence
from armance.service.claim_parser import (
    ClaimSchemaError,
    _parse_claim_block,
    parse_claims,
)


class TestClaimSchemaError:
    """Tests for ClaimSchemaError exception."""

    def test_is_exception(self) -> None:
        """ClaimSchemaError is an Exception."""
        assert issubclass(ClaimSchemaError, Exception)

    def test_has_descriptive_message(self) -> None:
        """ClaimSchemaError carries a message."""
        err = ClaimSchemaError("test message")
        assert str(err) == "test message"


class TestParseClaimBlockErrors:
    """Tests for _parse_claim_block raising ClaimSchemaError."""

    def test_empty_body_raises(self) -> None:
        """Empty body raises ClaimSchemaError."""
        with pytest.raises(ClaimSchemaError, match="empty body"):
            _parse_claim_block('evidence="x.md"', "  ")

    def test_invalid_confidence_raises(self) -> None:
        """Invalid confidence value raises ClaimSchemaError."""
        with pytest.raises(ClaimSchemaError, match="Invalid confidence"):
            _parse_claim_block('confidence=maybe', "Some fact.")

    def test_valid_block_succeeds(self) -> None:
        """Valid claim block returns Claim."""
        claim = _parse_claim_block(
            'id=c_a4f9k2pq evidence="docs/x.md" confidence=asserted',
            "The sky is blue.",
        )
        assert claim is not None
        assert isinstance(claim, Claim)
        assert claim.confidence == Confidence.ASSERTED

    def test_tentative_confidence_succeeds(self) -> None:
        """Valid tentative confidence works."""
        claim = _parse_claim_block('confidence=tentative', "Maybe true.")
        assert claim is not None
        assert claim.confidence == Confidence.TENTATIVE


class TestParseClaimsErrors:
    """Tests for parse_claims raising ClaimSchemaError."""

    def test_unclosed_tag_raises(self) -> None:
        """Unclosed claim tag raises ClaimSchemaError."""
        text = "[[claim evidence='x.md']]Unclosed claim without close"
        with pytest.raises(ClaimSchemaError, match="Unclosed claim tag"):
            parse_claims(text)

    def test_valid_multiple_claims_succeed(self) -> None:
        """Multiple valid claims parse successfully."""
        text = (
            "[[claim id=c_first]]First claim.[[/claim]]\n"
            "[[claim id=c_second]]Second claim.[[/claim]]"
        )
        claims = parse_claims(text)
        assert len(claims) == 2
        assert claims[0].id == "c_first"
        assert claims[1].id == "c_second"

    def test_empty_text_returns_empty(self) -> None:
        """Empty text returns empty list (no exception)."""
        claims = parse_claims("")
        assert claims == []

    def test_no_claims_returns_empty(self) -> None:
        """Text with no claim markers returns empty list."""
        claims = parse_claims("Just plain prose.")
        assert claims == []

    def test_malformed_claim_raises(self) -> None:
        """Claim with empty body raises ClaimSchemaError."""
        text = "[[claim evidence='x.md']]   [[/claim]]"
        with pytest.raises(ClaimSchemaError, match="empty body"):
            parse_claims(text)

    def test_malformed_confidence_raises(self) -> None:
        """Claim with invalid confidence raises ClaimSchemaError."""
        text = "[[claim confidence=invalid]]Fact.[[/claim]]"
        with pytest.raises(ClaimSchemaError, match="Invalid confidence"):
            parse_claims(text)
