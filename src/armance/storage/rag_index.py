"""RAG vector index: SQLite + sqlite-vec persistence layer.

Provides RagService for chunk ingestion, vector query, and deletion.
Moved from armance.service.rag_service to respect layer boundaries:
  - storage → service imports are forbidden
  - rag_index belongs in storage (SQLite DB persistence)
"""
from __future__ import annotations

import asyncio
import logging
import sqlite3
import sqlite_vec
import struct
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from armance.storage.paths import rag_index_db_path

logger = logging.getLogger(__name__)


# ── Local EventBus Protocol (avoids service → service dependency) ────────────

@runtime_checkable
class EventBus(Protocol):
    """Minimal event-bus protocol compatible with armance.service.events.EventBus."""

    async def emit(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
        severity: str = "info",
        **kwargs: Any,
    ) -> None: ...


# ── Data types ────────────────────────────────────────────────────────────────

class Chunk:
    """A single RAG chunk returned from a query."""

    def __init__(
        self,
        id: int,
        text: str,
        source: str,
        similarity: float = 0.0,
        doc_anchor: str = "",
    ):
        self.id = id
        self.text = text
        self.source = source
        self.similarity = similarity
        self.doc_anchor = doc_anchor

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Chunk):
            return False
        return self.text == other.text and self.source == other.source


# ── RagService ────────────────────────────────────────────────────────────────

class RagService:
    """Vector-index service backed by SQLite + sqlite-vec."""

    def __init__(
        self,
        root: Path,
        event_bus: EventBus | None = None,
        embedding_client: Any = None,
        embedding_model: str = "",
        embedding_dim: int = 1536,
    ):
        self.db_path = rag_index_db_path(root)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.embedding_dim = embedding_dim
        self.embedding_client = embedding_client
        self.embedding_model = embedding_model
        self.event_bus = event_bus

        legacy_chroma = root / "rag" / "chroma.sqlite3"
        legacy_vector = root / "vector"

        if self.event_bus and (legacy_chroma.exists() or legacy_vector.exists()):
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(
                    self.event_bus.emit("rag.legacy.detected", severity="warn")
                )
            except RuntimeError:
                pass

        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.enable_load_extension(True)
        sqlite_vec.load(self.conn)
        self.conn.enable_load_extension(False)
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.executescript(f"""
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY,
                doc_id TEXT NOT NULL,
                doc_anchor TEXT,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks
                USING vec0(embedding float[{self.embedding_dim}]);
        """)
        self.conn.commit()

    async def ingest(self, doc_path: Path) -> int:
        """Ingest a doc into the RAG index.

        Splits into ~500 token chunks. Uses zero-vector if no embedding
        provider is configured.
        """
        text = doc_path.read_text(encoding="utf-8")
        chunk_size = 2000
        overlap = 400

        chunks: list[str] = []
        i = 0
        while i < len(text):
            chunks.append(text[i : i + chunk_size])
            i += chunk_size - overlap
            if i >= len(text):
                break

        if not chunks and text:
            chunks.append(text)

        doc_id = doc_path.name
        created_at = datetime.now(timezone.utc).isoformat()

        c = self.conn.cursor()

        for chunk in chunks:
            if self.embedding_client:
                embedding = await self.embedding_client.embed(chunk, self.embedding_model)
            else:
                embedding = [0.0] * self.embedding_dim
                embedding[0] = 1.0

            embed_bytes = struct.pack(f"{len(embedding)}f", *embedding)

            c.execute(
                "INSERT INTO chunks (doc_id, doc_anchor, text, created_at) "
                "VALUES (?, ?, ?, ?)",
                (doc_id, "", chunk, created_at),
            )
            rowid = c.lastrowid
            c.execute(
                "INSERT INTO vec_chunks (rowid, embedding) VALUES (?, ?)",
                (rowid, embed_bytes),
            )

        self.conn.commit()

        if self.event_bus:
            await self.event_bus.emit(
                "rag.doc.ingested",
                {"doc_id": doc_id, "chunks": len(chunks)},
            )

        return len(chunks)

    def delete_by_source(self, source: str) -> None:
        c = self.conn.cursor()
        c.execute(
            "DELETE FROM vec_chunks WHERE rowid IN "
            "(SELECT id FROM chunks WHERE doc_id = ?)",
            (source,),
        )
        c.execute("DELETE FROM chunks WHERE doc_id = ?", (source,))
        self.conn.commit()

    def upsert(self, chunks: list) -> None:
        if not chunks:
            return
        c = self.conn.cursor()
        created_at = datetime.now(timezone.utc).isoformat()
        for chunk in chunks:
            text = getattr(chunk, "text", str(chunk))
            if self.embedding_client:
                # sync_docs runs on a worker thread (see host_agent /
                # library_ops); both asyncio.run() and run_coroutine_threadsafe
                # deadlock from there. Prefer a sync embed call.
                embed_sync = getattr(self.embedding_client, "embed_sync", None)
                if embed_sync is not None:
                    embedding = embed_sync(text, self.embedding_model)
                else:
                    # Fallback for providers that only expose async embed
                    # (claude-code, gemini). Spin a fresh event loop in this
                    # thread to drive the coroutine.
                    embedding = asyncio.new_event_loop().run_until_complete(
                        self.embedding_client.embed(text, self.embedding_model)
                    )
            else:
                embedding = [0.0] * self.embedding_dim
                embedding[0] = 1.0

            embed_bytes = struct.pack(f"{len(embedding)}f", *embedding)
            source = getattr(chunk, "source", "")
            page = str(getattr(chunk, "page", 0))

            c.execute(
                "INSERT INTO chunks (doc_id, doc_anchor, text, created_at) "
                "VALUES (?, ?, ?, ?)",
                (source, page, text, created_at),
            )
            rowid = c.lastrowid
            c.execute(
                "INSERT INTO vec_chunks (rowid, embedding) VALUES (?, ?)",
                (rowid, embed_bytes),
            )
        self.conn.commit()

    async def query(self, text: str, top_k: int = 5) -> list[Chunk]:
        return await self.query_excluding(text, top_k, [])

    async def query_excluding(
        self,
        text: str,
        top_k: int,
        exclude_ids: list[str],
    ) -> list[Chunk]:
        if self.embedding_client:
            embedding = await self.embedding_client.embed(text, self.embedding_model)
        else:
            embedding = [0.0] * self.embedding_dim
            embedding[0] = 1.0

        embed_bytes = struct.pack(f"{len(embedding)}f", *embedding)

        c = self.conn.cursor()

        if exclude_ids:
            placeholders = ",".join("?" for _ in exclude_ids)
            q = f"""
                SELECT c.id, c.text, c.doc_id, c.doc_anchor,
                       vec_distance_cosine(v.embedding, ?) as dist
                FROM vec_chunks v
                JOIN chunks c ON v.rowid = c.id
                WHERE c.doc_id NOT IN ({placeholders})
                ORDER BY dist
                LIMIT ?
            """
            c.execute(q, [embed_bytes] + exclude_ids + [top_k])
        else:
            q = """
                SELECT c.id, c.text, c.doc_id, c.doc_anchor,
                       vec_distance_cosine(v.embedding, ?) as dist
                FROM vec_chunks v
                JOIN chunks c ON v.rowid = c.id
                ORDER BY dist
                LIMIT ?
            """
            c.execute(q, [embed_bytes, top_k])

        results: list[Chunk] = []
        for row in c.fetchall():
            results.append(
                Chunk(
                    id=row[0],
                    text=row[1],
                    source=row[2],
                    doc_anchor=row[3],
                    similarity=1.0 - (row[4] if row[4] is not None else 0.0),
                )
            )

        if self.event_bus:
            await self.event_bus.emit(
                "rag.query.completed",
                {"query": text, "results": len(results)},
            )

        return results


# ── Convenience helper ────────────────────────────────────────────────────────

def context_with_rag(armance_root: Path, query: str, k: int = 8) -> str:
    """Return top-k RAG chunks formatted for prompt injection.

    Format per chunk: ``[source: filename p.N] text``
    Returns empty string if vector store is empty or unavailable.
    """
    # Skip when nothing is indexed — avoids embedding the query for nothing.
    try:
        from armance.storage.rag_status import has_indexed_chunks
        if not has_indexed_chunks(armance_root):
            return ""
    except Exception:
        logger.debug("RAG index probe failed; proceeding", exc_info=True)
    try:
        store = RagService(armance_root)

        chunks: list[Chunk] = []

        def _run() -> None:
            chunks.extend(asyncio.run(store.query(query, top_k=k)))

        t = threading.Thread(target=_run)
        t.start()
        t.join()
    except Exception:
        logger.warning("RAG retrieval failed", exc_info=True)
        return ""

    if not chunks:
        return ""

    lines = [
        f"### [rag:{c.id}] Source: {c.source} p.{getattr(c, 'doc_anchor', None) or '0'}\n{c.text}"
        for c in chunks
    ]
    return "\n".join(lines)
