---
governs: [src/armance/service/footprint.py, src/armance/service/footprint_ops.py,
  src/armance/service/footprint_resolve.py, src/armance/service/footprint_bounds.py,
  src/armance/service/footprint_zones.py, src/armance/service/cost.py, src/armance/service/equivalences.py,
  src/armance/service/ademe_equivalences.yaml, src/armance/service/env_model_aliases.yaml]
depends: [core-models, providers-catalogue]
---
# env-impact-ledger

For every LLM answer, the carbon (gCO2e) and water (mL) footprint, estimated offline with EcoLogits (MPL-2.0),
recorded in the ledger and shown in the UI. One of the three anti-lie mechanisms, with one rule: never fabricate a
number. When data is missing, bound physically rather than invent a point, and show the uncertainty: `~` for an
estimate, `?` for unknown.

Constraints and non-goals:

- EcoLogits is called through its pure `compute_llm_impacts`, never patched.
- No price or equivalence factor in code: they come from the YAML files or from live discovery.
- The hook that measures latency and writes the ledger (`call_with_ledger`) lives in `service/llm_service.py`, the
  `Footprint` model in `core-models`.

Criteria:

- A free model without parameters resolves to physical bounds, never a made-up point:
  [test_free_model_no_params_returns_bounded](../../tests/unit/service/test_footprint_ei2.py),
  [test_returns_non_none_range](../../tests/unit/service/test_footprint_bounds.py),
  [test_water_bounds_ordered](../../tests/unit/service/test_footprint_bounds.py).
- An unknown price is unknown, not zero: [test_lookup_price_unknown_returns_none](../../tests/unit/service/test_cost.py).
- Equivalence factors come from YAML: [test_constants_come_from_yaml](../../tests/unit/service/test_equivalences.py).
- The chip shows `~` on an estimate, `?` on unknown, and flags partial coverage:
  [test_tilde_prefix_on_estimate](../../tests/unit/service/test_footprint_ei6.py),
  [test_question_mark_on_unknown](../../tests/unit/service/test_footprint_ei6.py),
  [test_mixed_known_and_unknown_flags_partial](../../tests/unit/service/test_footprint_ei6.py).
