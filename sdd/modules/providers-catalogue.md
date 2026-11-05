---
governs: [src/armance/providers/]
depends: [core-models, config-and-paths]
---
# providers-catalogue

The four provider types (`openrouter`, `claude-code`, `gemini`, `custom-openai`) behind one model catalogue
(`ModelSpec`) that Malik, Kim, the cost estimate and the footprint read. A provider is a type plus an optional named
instance (`custom-openai:lab`) with its own config, key variable and model allowlist. Two instances of one type are
one model family for the Creuset.

Constraints and non-goals:

- Discovery is live and cached for the process only; nothing is persisted.
- A discovery failure never reaches the caller: static fallback or empty list.
- No invented price or tier: `custom-openai` models default to tier `low`, billing is the endpoint's business.
- The claude-code SDK runs hermetic (no host settings, plugins or hooks leak into Armance agents).

Criteria:

- The budget filter keeps free models under `free-first`, whatever their nominal tier:
  [test_filter_for_budget_free_first_keeps_only_free](../../tests/unit/providers/test_base_provider.py),
  [test_effectively_free_low_kept_under_free_first](../../tests/unit/providers/test_effectively_free_filter.py).
- `optimised` orders models by footprint, stable on ties:
  [test_optimised_orders_by_gco2e_ascending](../../tests/unit/providers/test_model_discovery_optimised.py),
  [test_optimised_is_stable_for_equal_gco2e](../../tests/unit/providers/test_model_discovery_optimised.py).
- A missing discovery route or base URL gives an empty list, not an error:
  [test_custom_openai_discovery_absent_route_returns_empty](../../tests/unit/providers/test_llm_openrouter.py),
  [test_custom_openai_discovery_without_base_url_returns_empty](../../tests/unit/providers/test_llm_openrouter.py).
- An instance resolves its client by type and keeps its own config:
  [test_get_client_resolves_by_type_with_instance_config](../../tests/test_provider_instances.py).
- Two instances of one type are one family:
  [test_model_family_two_instances_same_type_same_family](../../tests/test_provider_instances.py),
  [test_available_families_two_custom_instances_is_one_family](../../tests/test_provider_instances.py).
- The allowlist adds to discovery and never hides a discovered model:
  [test_known_ids_union_discovered_and_allowlist](../../tests/test_provider_allowlist.py),
  [test_allowlist_never_masks_discovered](../../tests/test_provider_allowlist.py).
