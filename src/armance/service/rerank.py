"""Two-stage RAG retrieval — the precision stage (service layer).

Stage 1 (recall) is the plain vector query owned by
``armance.storage.rag_index.RagService``. Stage 2 (precision) reorders
those candidates through a cross-encoder rerank endpoint and keeps the
top ``rerank_keep_n``.

Orchestration lives HERE, never in storage: the storage layer must stay
free of service imports. Sync callers (``context_with_rag``) receive the
stage-2 step as an injected async callback built by
``ContextService.enrich_for_agent``.
"""
from __future__ import annotations

import logging

from armance.service.llm_service import get_client

logger = logging.getLogger(__name__)


async def rerank_chunks(query: str, candidates: list, config) -> list:
    """Rerank *candidates* for *query*, keep top ``config.rerank_keep_n``.

    Degrades to vector order on ANY failure (unsupported provider, HTTP,
    timeout, bad payload). Never raises.
    """
    keep_n = getattr(config, "rerank_keep_n", 5)
    try:
        client = get_client(config.rerank_provider, config)
        hits = await client.rerank(
            query, [c.text for c in candidates], config.rerank_model, top_n=keep_n,
        )
        ranked = [candidates[h.index] for h in hits if 0 <= h.index < len(candidates)]
        # any candidate the reranker omitted gets appended in vector order
        seen = {id(c) for c in ranked}
        ranked += [c for c in candidates if id(c) not in seen]
        return ranked[:keep_n]
    except Exception:
        logger.warning("rerank failed; falling back to vector order", exc_info=True)
        return candidates[:keep_n]
