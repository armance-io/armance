---
governs: [src/armance/service/library_ops.py, src/armance/service/library_web_ops.py,
  src/armance/service/context_service.py, src/armance/service/rerank.py, src/armance/service/agents/_rag_inject.py,
  src/armance/storage/rag_index.py, src/armance/storage/rag_status.py, src/armance/storage/ingestion.py]
depends: [config-and-paths, providers-catalogue]
---
# library-rag

The user's documents (`.armance/docs/`), indexed in a local vector store (sqlite-vec), retrieved by similarity and
injected into prompts as evidence. Two states stay distinct: the searchable library (indexed slips) and the read set
(full documents loaded into every agent's context). Alongside, the project context (L0/L1/L2), versioned and written
by the agents. Knowledge used by an agent is sourced and dated, never invented.

Constraints and non-goals:

- Local store only, no cloud RAG. Indexing is triggered (`/library index`, web button), never silent or in background.
- Every injected excerpt is framed by a provenance header naming `.armance/docs/` and labelled `[rag:<id>]` with its
  source (checked by hand).
- Rerank is opt-in and optional: without `rerank_provider` and `rerank_model`, the search path is the plain vector
  query; any rerank failure falls back to the vector order.
- `created_at` is provenance, not a ranking factor. No semantic dedup across documents.

Criteria:

- No embedding config or no docs means no injection and no provider call:
  [test_inject_rag_section_no_embedding_config](../../tests/unit/service/agents/test_rag_inject_async.py),
  [test_inject_rag_section_skips_embed_when_no_docs](../../tests/unit/service/agents/test_rag_inject_async.py).
- A document whose content changed is reported stale and indexed again:
  [test_doc_in_manifest_marks_stale](../../tests/unit/storage/test_rag_status.py),
  [test_sync_docs_reindexes_changed_file](../../tests/unit/storage/test_ingestion.py).
- Rerank degrades to the vector order on error, and is absent when not configured:
  [test_rerank_chunks_degrades_on_error](../../tests/test_rerank_service.py),
  [test_inject_rag_section_without_rerank_is_single_stage](../../tests/test_rag_inject_rerank.py),
  [test_context_with_rag_no_hook_is_legacy](../../tests/test_context_with_rag_rerank.py).
- A new L0 version updates the manifest: [test_write_l0_updates_manifest](../../tests/unit/service/test_context_service.py).
