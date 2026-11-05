---
governs: [src/armance/core/, ":!src/armance/core/models/workflow.py", ":!src/armance/core/models/_workflow_prompts.py",
  ":!src/armance/core/models/preset.py"]
---
# core-models

The leaf layer: the data models every other layer shares (agents, roles, tasks, turns, conversations, claims, events,
tokens, footprint, deliverables), the L0/L1/L2 context layers, and the `LLMClient` protocol with its client registry.
Concrete clients live in `providers/` and register themselves at import; callers always go through `get_client`.

Constraints and non-goals:

- `core/` never imports `service`, `client` or `providers`, and never reads the disk on its own: callers inject what
  it needs.
- No LLM call here. The default context writer only concatenates text; the real writer is injected by the service
  layer.
- Canonical paths belong to `config-and-paths`, the workflow schema and executor to `workflow-engine`.

Criteria:

- No module of `core/` imports an upper layer: [check_invariants.sh](../../scripts/check_invariants.sh).
- A changed source hash counts as added, so the document is ingested again:
  [test_diff_sources_added_removed_unchanged](../../tests/unit/core/models/test_context.py).
- `chunk_text` never returns a chunk above the cap, splitting on paragraphs first:
  [test_chunk_text_splits_on_paragraph_when_over_cap](../../tests/unit/core/models/test_context.py),
  [test_chunk_text_hard_splits_oversized_paragraph](../../tests/unit/core/models/test_context.py).
- Writing context produces the three layers, each new version numbered after the last:
  [test_write_context_layers_produces_l0_l1_l2](../../tests/unit/core/models/test_context.py),
  [test_next_layer_version_increments](../../tests/unit/core/models/test_context.py).
- There is one event type, the one of `core.models.event`:
  [test_canonical_event_is_core_models_event](../../tests/architecture/test_single_event_type.py).
