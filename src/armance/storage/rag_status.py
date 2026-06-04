"""RAG library status: diff manifest vs docs dir vs SQLite chunks."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import sqlite_vec
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from armance.config import Config

_SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".md", ".txt", ".text"}


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def _load_manifest(vector_dir: Path) -> dict[str, str]:
    p = vector_dir / "manifest.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def has_indexed_chunks(armance_root: Path) -> bool:
    """True if the vector DB exists and holds at least one chunk.

    Cheap (a single COUNT, no embedding) — used to skip RAG retrieval (and the
    query-embedding call it entails) entirely when no document is indexed.
    """
    from armance.storage.paths import rag_index_db_path
    db_path = rag_index_db_path(armance_root)
    if not db_path.exists():
        return False
    try:
        conn = sqlite3.connect(db_path, check_same_thread=False)
        try:
            row = conn.execute("SELECT 1 FROM chunks LIMIT 1").fetchone()
        finally:
            conn.close()
        return row is not None
    except Exception:
        return False


def _query_sqlite_chunks(armance_root: Path) -> dict[str, int]:
    """Return {doc_id: chunk_count} from the SQLite vector DB."""
    from armance.storage.paths import rag_index_db_path
    db_path = rag_index_db_path(armance_root)
    if not db_path.exists():
        return {}
    try:
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        rows = conn.execute(
            "SELECT doc_id, COUNT(*) FROM chunks GROUP BY doc_id"
        ).fetchall()
        conn.close()
        return {row[0]: row[1] for row in rows}
    except Exception:
        return {}


def get_rag_status(armance_root: Path, config: "Config | None" = None) -> dict:
    """Compute full RAG library status.

    Returns a dict with:
      - embedding_model: str (from config or "none")
      - embedding_provider: str
      - docs_in_db: list[dict]  — files in SQLite (source, chunks, tokens_est, size_kb)
      - docs_on_disk: list[dict] — files in .armance/docs/ (name, size_kb, in_manifest, stale, in_db)
      - orphans: list[str]  — in manifest but not on disk (to remove)
      - total_chunks: int
      - total_tokens_est: int
      - total_size_kb: float
      - db_path: str
    """
    embedding_model = ""
    embedding_provider = ""
    if config:
        embedding_model = getattr(config, "embedding_model", "") or ""
        embedding_provider = getattr(config, "embedding_provider", "") or ""

    vector_dir = armance_root / "vector"
    docs_dir = armance_root / "docs"

    manifest = _load_manifest(vector_dir)
    chunks_by_doc = _query_sqlite_chunks(armance_root)

    from armance.storage.paths import rag_index_db_path
    db_path = rag_index_db_path(armance_root)

    # --- Docs on disk ---
    docs_on_disk: list[dict] = []
    disk_names: set[str] = set()

    if docs_dir.exists():
        for f in sorted(docs_dir.rglob("*")):
            if not f.is_file():
                continue
            if f.suffix.lower() not in _SUPPORTED_EXTENSIONS:
                continue
            size_bytes = f.stat().st_size
            size_kb = round(size_bytes / 1024, 1)
            name = f.name
            disk_names.add(name)
            sha = _file_sha256(f)
            in_manifest = name in manifest
            manifest_sha = manifest.get(name, "")
            stale = in_manifest and manifest_sha != sha and not manifest_sha.startswith("failed:")
            in_db = name in chunks_by_doc
            chunk_count = chunks_by_doc.get(name, 0)
            # Token estimate: chars / 4 (rough cl100k approximation)
            tokens_est = size_bytes // 4
            docs_on_disk.append({
                "name": name,
                "size_kb": size_kb,
                "in_manifest": in_manifest,
                "stale": stale,
                "in_db": in_db,
                "chunk_count": chunk_count,
                "tokens_est": tokens_est,
            })

    # --- Orphans: in manifest but not on disk ---
    orphans = [name for name in manifest if name not in disk_names]

    # --- Docs in DB summary ---
    docs_in_db: list[dict] = []
    for doc_id, chunk_count in sorted(chunks_by_doc.items()):
        docs_in_db.append({"name": doc_id, "chunks": chunk_count})

    total_chunks = sum(chunks_by_doc.values())
    total_tokens_est = sum(d["tokens_est"] for d in docs_on_disk)
    total_size_kb = round(sum(d["size_kb"] for d in docs_on_disk), 1)

    return {
        "embedding_model": embedding_model,
        "embedding_provider": embedding_provider,
        "docs_on_disk": docs_on_disk,
        "docs_in_db": docs_in_db,
        "orphans": orphans,
        "total_chunks": total_chunks,
        "total_tokens_est": total_tokens_est,
        "total_size_kb": total_size_kb,
        "db_path": str(db_path),
    }


def forget_doc(armance_root: Path, filename: str) -> str:
    """Remove a doc from the RAG library: manifest entry + sqlite-vec chunks.

    Returns a human-readable status string.
    """
    vector_dir = armance_root / "vector"
    manifest_path = vector_dir / "manifest.json"
    manifest: dict = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text()) or {}
        except Exception:
            manifest = {}
    was_present = filename in manifest
    if was_present:
        del manifest[filename]
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True))

    from armance.storage.paths import rag_index_db_path
    db_path = rag_index_db_path(armance_root)
    deleted_chunks = 0
    if db_path.exists():
        try:
            conn = sqlite3.connect(db_path, check_same_thread=False)
            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
            conn.enable_load_extension(False)
            cur = conn.cursor()
            rows = cur.execute(
                "SELECT id FROM chunks WHERE doc_id = ?", (filename,)
            ).fetchall()
            deleted_chunks = len(rows)
            if rows:
                ids = [r[0] for r in rows]
                placeholders = ",".join("?" for _ in ids)
                cur.execute(
                    f"DELETE FROM vec_chunks WHERE rowid IN ({placeholders})", ids
                )
                cur.execute(
                    "DELETE FROM chunks WHERE doc_id = ?", (filename,)
                )
                conn.commit()
            conn.close()
        except Exception:
            pass

    from armance.nls import t
    if not was_present and deleted_chunks == 0:
        return t("system.info", body=t("forget.not_in_library", filename=filename))
    return t(
        "system.ok",
        body=t("forget.success", filename=filename, chunks=deleted_chunks),
    )


def format_rag_status_markdown(status: dict) -> str:
    """Render RAG status as a markdown block for TUI or agent reply."""
    from armance.nls import t
    lines: list[str] = [t("rag_report.title")]

    emb = status["embedding_model"] or t("rag_report.embedding_none")
    prov = status["embedding_provider"]
    if prov:
        lines.append(t("rag_report.embedding_with_provider", provider=prov, model=emb))
    else:
        lines.append(t("rag_report.embedding_no_provider", model=emb))

    lines.append("")
    lines.append(t(
        "rag_report.stats",
        chunks=status["total_chunks"],
        size_kb=status["total_size_kb"],
        tokens=f"{status['total_tokens_est']:,}",
    ))
    lines.append("")

    docs = status["docs_on_disk"]
    orphans = status["orphans"]

    if not docs and not orphans:
        lines.append(t("rag_report.no_docs_line"))
        lines.append("")
        lines.append(t("rag_report.no_docs_hint"))
        return "\n".join(lines)

    lines.append(t("rag_report.files_header"))
    for d in docs:
        name = d["name"]
        size = d["size_kb"]
        chunks = d["chunk_count"]
        tokens = d["tokens_est"]
        if d["stale"]:
            status_icon = t("rag_report.status_stale")
        elif d["in_db"]:
            status_icon = t("rag_report.status_retained", chunks=chunks, tokens=f"{tokens:,}")
        elif d["in_manifest"]:
            status_icon = t("rag_report.status_manifest_only")
        else:
            status_icon = t("rag_report.status_not_retained")
        lines.append(t("rag_report.doc_line", name=name, size_kb=size, status=status_icon))

    if orphans:
        lines.append("")
        lines.append(t("rag_report.orphans_header"))
        db_index = {d["name"]: d["chunks"] for d in status["docs_in_db"]}
        for name in orphans:
            lines.append(t("rag_report.orphan_line", name=name, chunks=db_index.get(name, 0)))
        lines.append("")
        lines.append(t("rag_report.orphans_hint"))

    return "\n".join(lines)
