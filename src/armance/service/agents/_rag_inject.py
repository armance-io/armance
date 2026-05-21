"""RAG injection helper for meta-agents (Armance, Malik, Kim).

Specialist agents already enrich via ContextService.enrich_for_agent.
Meta-agents call inject_rag_section() to get a formatted prompt section
they can append to their system prompt.

Async by design: callers all live inside the TUI / FastAPI event loop,
so RagService.query is awaited directly. Previous versions used
asyncio.run() inside a worker thread, which would crash under FastAPI
(`asyncio.run() cannot be called from a running event loop`).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


async def inject_rag_section(
    armance_root: Path,
    query: str,
    *,
    k: int = 3,
    config: "Any | None" = None,
) -> str:
    """Return a ready-to-append system-prompt section with top-k RAG chunks.

    Empty string if no docs indexed, query empty, or retrieval fails.
    Passes embedding_client from config when available so vectors are real.
    """
    if not query or not query.strip():
        return ""

    # If embedding not configured, RAG is disabled — skip retrieval
    if config is not None:
        if not getattr(config, "embedding_provider", "") or not getattr(config, "embedding_model", ""):
            return ""

    try:
        from armance.storage.rag_index import RagService, Chunk
    except Exception:
        logger.warning("RAG module unavailable", exc_info=True)
        return ""

    embedding_client = None
    embedding_model = ""
    embedding_dim = 1536
    if config is not None:
        prov = getattr(config, "embedding_provider", "")
        model = getattr(config, "embedding_model", "")
        if prov and model:
            try:
                from armance.service.llm_service import get_client as _get
                embedding_client = _get(prov, config)
                embedding_model = model
                if "3-large" in model or "exp" in model:
                    embedding_dim = 3072
                elif "text-embedding-004" in model or "768" in model:
                    embedding_dim = 768
                logger.info(
                    "RAG embed client ready: provider=%s model=%s dim=%d",
                    prov, model, embedding_dim,
                )
            except Exception:
                logger.exception("RAG embed client init failed: provider=%s model=%s", prov, model)

    if not embedding_model:
        logger.info("RAG retrieval skipped: no embedding model configured")
        return ""

    try:
        store = RagService(
            armance_root,
            embedding_client=embedding_client,
            embedding_model=embedding_model,
            embedding_dim=embedding_dim,
        )
        chunks: list[Chunk] = await store.query(query, top_k=k)
        logger.info("RAG retrieved %d chunk(s) for query=%r", len(chunks), query[:60])
    except Exception:
        logger.exception("RAG retrieval failed")
        return ""

    if not chunks:
        return ""

    lines = [
        f"### [rag:{c.id}] Source: {c.source}\n{c.text}"
        for c in chunks
    ]
    excerpt = "\n".join(lines)
    return (
        "## Retrieved from .armance/docs/ (user-supplied documents)\n"
        f"{excerpt}\n"
        "Use this evidence naturally when relevant. Do not cite mechanically."
    )
