---
governs: [src/armance/service/claim_ledger_service.py, src/armance/service/claim_parser.py,
  src/armance/service/argument_ledger.py, src/armance/service/render_provenance.py]
depends: [core-models]
---
# claims-ledger

A dated, checkable record of what the agents assert, one of the three anti-lie mechanisms. A factual claim is
extracted, stored with its provenance, verified (verdict, rationale, verifier) and confronted with what contradicts
it. Render provenance and the argument and source registers of the synthesis complete the chain from claim to
evidence to deliverable.

Constraints and non-goals:

- The ledger flags a contradiction; settling it belongs to the human or a verifying agent.
- No hard delete: a removed claim stays, marked unsourced. Audit comes before tidiness.
- Atomic temp-and-rename writes instead of file locks, for Windows.
- The parser never completes missing evidence: a claim without evidence keeps an empty list.

Criteria:

- Writes are atomic and an id collision is refused, never overwritten:
  [test_atomic_write_preserves_data](../../tests/unit/service/test_claim_ledger.py),
  [test_append_claim_id_collision](../../tests/unit/service/test_claim_ledger.py).
- Verifying an unknown claim fails, a verdict born of a conflict names the contradicting claim:
  [test_verify_claim_not_found](../../tests/unit/service/test_claim_ledger.py),
  [test_verify_claim_with_contradicting](../../tests/unit/service/test_claim_ledger.py).
- A malformed claim block raises instead of being dropped:
  [test_unclosed_tag_raises](../../tests/unit/service/test_claim_parser.py),
  [test_invalid_confidence_raises](../../tests/unit/service/test_claim_parser.py),
  [test_empty_body_raises](../../tests/unit/service/test_claim_parser.py).
- The synthesis sidecars (arguments, sources) are extracted and persisted when present:
  [test_extract_both_sidecars](../../tests/unit/service/test_argument_ledger.py).
