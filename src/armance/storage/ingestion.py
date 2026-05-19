"""Document loaders: PDF, DOCX, TXT, MD → list[Chunk] + manifest-driven sync."""
from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TYPE_CHECKING

import tiktoken

if TYPE_CHECKING:
    from armance.config import Config

logger = logging.getLogger(__name__)

MAX_FILE_BYTES = 50 * 1024 * 1024  # 50 MB
SCANNED_PDF_MIN_CHARS = 50  # below this total for multi-page PDF → assume scanned


class IngestionError(ValueError):
    """Raised when a document cannot be ingested (e.g. scanned PDF, unsupported format)."""

_TOKENIZER: tiktoken.Encoding | None = None


def _tokenizer() -> tiktoken.Encoding:
    global _TOKENIZER
    if _TOKENIZER is None:
        _TOKENIZER = tiktoken.get_encoding("cl100k_base")
    return _TOKENIZER


@dataclass
class Chunk:
    text: str
    source: str
    page: int = 0
    char_start: int = 0
    char_end: int = 0
    sha256: str = field(default="", repr=False)

    def __post_init__(self) -> None:
        if not self.sha256:
            self.sha256 = hashlib.sha256(self.text.encode()).hexdigest()


def chunk_text(
    text: str,
    source: str,
    page: int = 0,
    max_tokens: int = 512,
    overlap: int = 64,
) -> list[Chunk]:
    """Split text into token-bounded chunks, respecting paragraph breaks."""
    enc = _tokenizer()
    paragraphs = re.split(r"\n{2,}", text.strip())

    chunks: list[Chunk] = []
    current_paras: list[str] = []
    current_tokens = 0
    char_pos = 0

    def flush(paras: list[str], start: int) -> None:
        if not paras:
            return
        joined = "\n\n".join(paras)
        chunks.append(
            Chunk(
                text=joined,
                source=source,
                page=page,
                char_start=start,
                char_end=start + len(joined),
            )
        )

    para_start = 0
    for para in paragraphs:
        para_tokens = len(enc.encode(para))
        if current_tokens + para_tokens > max_tokens and current_paras:
            flush(current_paras, para_start - sum(len(p) + 2 for p in current_paras) + 2)
            # keep last `overlap` tokens worth of paras for continuity
            overlap_paras: list[str] = []
            overlap_tok = 0
            for p in reversed(current_paras):
                t = len(enc.encode(p))
                if overlap_tok + t > overlap:
                    break
                overlap_paras.insert(0, p)
                overlap_tok += t
            current_paras = overlap_paras
            current_tokens = overlap_tok
        current_paras.append(para)
        current_tokens += para_tokens
        char_pos += len(para) + 2

    flush(current_paras, 0)
    return chunks


def _check_size(path: Path) -> bool:
    size = path.stat().st_size
    if size > MAX_FILE_BYTES:
        logger.warning("skipping %s: %.1f MB exceeds 50 MB limit", path, size / 1e6)
        return False
    return True


def load_txt(path: Path, max_tokens: int = 512, overlap: int = 64) -> list[Chunk]:
    if not _check_size(path):
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    return chunk_text(text, source=path.name, max_tokens=max_tokens, overlap=overlap)


def load_md(path: Path, max_tokens: int = 512, overlap: int = 64) -> list[Chunk]:
    if not _check_size(path):
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    return chunk_text(text, source=path.name, max_tokens=max_tokens, overlap=overlap)


def load_pdf(path: Path, max_tokens: int = 512, overlap: int = 64) -> list[Chunk]:
    if not _check_size(path):
        return []
    from pypdf import PdfReader  # local import — optional dep

    reader = PdfReader(str(path))
    all_texts: list[tuple[int, str]] = []
    for page_num, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        all_texts.append((page_num, text))

    # Detect scanned PDF: multi-page with < SCANNED_PDF_MIN_CHARS total extracted
    total_chars = sum(len(t) for _, t in all_texts)
    if len(all_texts) > 1 and total_chars < SCANNED_PDF_MIN_CHARS:
        raise IngestionError(
            "PDF appears to be scanned; OCR not configured. "
            "Convert manually or skip."
        )

    chunks: list[Chunk] = []
    for page_num, text in all_texts:
        if not text.strip():
            continue
        chunks.extend(
            chunk_text(text, source=path.name, page=page_num, max_tokens=max_tokens, overlap=overlap)
        )
    return chunks


def load_docx(path: Path, max_tokens: int = 512, overlap: int = 64) -> list[Chunk]:
    if not _check_size(path):
        return []
    from docx import Document  # local import — optional dep

    doc = Document(str(path))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    text = "\n\n".join(paragraphs)
    return chunk_text(text, source=path.name, max_tokens=max_tokens, overlap=overlap)


def load_file(path: Path, max_tokens: int = 512, overlap: int = 64) -> list[Chunk]:
    """Dispatch loader by extension."""
    ext = path.suffix.lower()
    if ext == ".pdf":
        return load_pdf(path, max_tokens=max_tokens, overlap=overlap)
    if ext in (".docx", ".doc"):
        return load_docx(path, max_tokens=max_tokens, overlap=overlap)
    if ext == ".md":
        return load_md(path, max_tokens=max_tokens, overlap=overlap)
    if ext in (".txt", ".text", ""):
        return load_txt(path, max_tokens=max_tokens, overlap=overlap)
    logger.warning("unsupported file type: %s", path)
    return []


# ---------------------------------------------------------------------------
# Manifest-driven sync (task 1.5)
# ---------------------------------------------------------------------------

MANIFEST_FILE = "manifest.json"
EMBED_META_FILE = "embedding_meta.json"
_SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".md", ".txt", ".text"}


def _load_embed_meta(vector_dir: Path) -> dict:
    p = vector_dir / EMBED_META_FILE
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _save_embed_meta(vector_dir: Path, model: str, dim: int) -> None:
    p = vector_dir / EMBED_META_FILE
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        p.write_text(
            json.dumps({"model": model, "dim": dim}, indent=2), encoding="utf-8"
        )
    except Exception:
        logger.debug("embed meta write failed", exc_info=True)


def _probe_embedding_dim(client: Any, model: str, vector_dir: Path) -> int:
    """Return the embedding dimension for (model). Cached so the provider is
    only hit once per (model, dim) pair.

    Source of truth = a one-token live call. Avoids hard-coded id heuristics
    that silently break when providers ship new model variants.
    """
    cached = _load_embed_meta(vector_dir)
    if cached.get("model") == model and isinstance(cached.get("dim"), int):
        return int(cached["dim"])

    try:
        embed_sync = getattr(client, "embed_sync", None)
        if embed_sync is not None:
            vec = embed_sync("ping", model)
        else:
            import asyncio
            vec = asyncio.new_event_loop().run_until_complete(client.embed("ping", model))
        return len(vec)
    except Exception:
        logger.exception("embedding dim probe failed; defaulting to 1536")
        return 1536


def _reset_db_if_embedding_changed(
    vector_dir: Path, current_model: str, current_dim: int,
) -> None:
    """If the persisted (model, dim) differs from the runtime one, drop the
    sqlite-vec DB + manifest so the next sync rebuilds from scratch with the
    correct dim. Silent + transparent — the user just sees re-indexing run.
    Always rewrites embedding_meta.json to the current (model, dim).
    """
    cached = _load_embed_meta(vector_dir)
    if (
        cached.get("model") == current_model
        and cached.get("dim") == current_dim
    ):
        # No change. Make sure the meta file exists (first run).
        if not cached:
            _save_embed_meta(vector_dir, current_model, current_dim)
        return

    from armance.storage.paths import rag_index_db_path
    db_path = rag_index_db_path(vector_dir.parent)
    manifest_path = vector_dir / MANIFEST_FILE
    for p in (db_path, manifest_path):
        try:
            if p.exists():
                p.unlink()
        except Exception:
            logger.debug("failed to remove %s", p, exc_info=True)
    _save_embed_meta(vector_dir, current_model, current_dim)
    logger.info(
        "embedding switched (model=%s dim=%d); vector DB rebuilt from scratch",
        current_model, current_dim,
    )


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def _load_manifest(vector_dir: Path) -> dict[str, str]:
    p = vector_dir / MANIFEST_FILE
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _save_manifest(vector_dir: Path, manifest: dict[str, str]) -> None:
    p = vector_dir / MANIFEST_FILE
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")


def sync_docs(
    armance_root: Path,
    config: Config | None = None,
    max_tokens: int = 512,
    overlap: int = 64,
) -> dict[str, int]:
    """Walk .armance/docs/, re-index changed/new files, remove deleted ones.

    Returns counts: {"indexed": N, "skipped": N, "deleted": N}.
    """
    from armance.storage.rag_index import RagService  # same-layer import

    docs_dir = armance_root / "docs"
    vector_dir = armance_root / "vector"

    if not docs_dir.exists():
        logger.info("docs dir not found: %s", docs_dir)
        return {"indexed": 0, "skipped": 0, "deleted": 0}

    embedding_client = None
    embedding_model = ""
    embedding_dim = 1536

    if config and getattr(config, "embedding_provider", "") and getattr(config, "embedding_model", ""):
        from armance.core.protocols.llm import get_client
        try:
            embedding_client = get_client(config.embedding_provider, config)
            embedding_model = config.embedding_model
            # Probe the actual embedding dimension by sending one tiny call.
            # Model id heuristics (3-large -> 3072, etc.) are fragile and break
            # silently on new model ids — the runtime call is the source of
            # truth. Fall back to 1536 if probing fails.
            embedding_dim = _probe_embedding_dim(
                embedding_client, embedding_model, vector_dir,
            )
            logger.info(
                "ingest embed client ready: provider=%s model=%s dim=%d",
                config.embedding_provider, embedding_model, embedding_dim,
            )
        except Exception:
            logger.exception(
                "ingest embed client init failed: provider=%s model=%s",
                config.embedding_provider, config.embedding_model,
            )

    # If the embedding (model + dim) has changed since last ingest, drop the
    # vector DB so we recreate it with the new dimension. Manifest is also
    # cleared so all docs re-index from scratch — transparent to the user.
    if embedding_model and embedding_model != "none":
        _reset_db_if_embedding_changed(vector_dir, embedding_model, embedding_dim)

    if not embedding_model:
        if config is not None:
            # Config provided but embedding unusable (disabled or init failed).
            # Distinguish: was it configured at all?
            configured = bool(
                getattr(config, "embedding_provider", "")
                and getattr(config, "embedding_model", "")
            )
            if configured:
                logger.warning(
                    "sync_docs: embedding configured but client init failed — "
                    "skipping ingestion. Check API key and provider connectivity."
                )
                return {"indexed": 0, "skipped": 0, "deleted": 0, "error": "embed_init_failed"}
            logger.info("sync_docs: embedding disabled in config — skipping ingestion")
            return {"indexed": 0, "skipped": 0, "deleted": 0}
        # No config passed at all (CLI/test path): fall back to keyword-only mode
        # using zero-vectors so chunks are still queryable lexically.
        embedding_model = "none"

    store = RagService(
        armance_root,
        embedding_client=embedding_client,
        embedding_model=embedding_model,
        embedding_dim=embedding_dim,
    )
    manifest = _load_manifest(vector_dir)

    current_files: dict[str, str] = {}
    per_doc_chunks: dict[str, int] = {}
    indexed = skipped = 0

    for path in sorted(docs_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in _SUPPORTED_EXTENSIONS:
            continue
        if path.stat().st_size > MAX_FILE_BYTES:
            logger.warning("skipping %s: exceeds 50 MB limit", path.name)
            skipped += 1
            continue

        sha = _file_sha256(path)
        current_files[path.name] = sha

        if manifest.get(path.name) == sha:
            skipped += 1
            logger.debug("unchanged: %s", path.name)
            continue

        logger.info("indexing: %s", path.name)
        store.delete_by_source(path.name)
        try:
            chunks = load_file(path, max_tokens=max_tokens, overlap=overlap)
        except IngestionError as exc:
            logger.warning("ingestion error for %s: %s", path.name, exc)
            manifest[path.name] = f"failed:{exc}"
            skipped += 1
            continue
        store.upsert(chunks)
        manifest[path.name] = sha
        indexed += 1
        per_doc_chunks[path.name] = len(chunks)

    # remove deleted files
    deleted = 0
    for name in list(manifest.keys()):
        if name not in current_files:
            logger.info("removing deleted: %s", name)
            store.delete_by_source(name)
            del manifest[name]
            deleted += 1

    _save_manifest(vector_dir, manifest)
    total_chunks = sum(per_doc_chunks.values())
    logger.info(
        "sync_docs: indexed=%d skipped=%d deleted=%d chunks=%d",
        indexed, skipped, deleted, total_chunks,
    )
    return {
        "indexed": indexed,
        "skipped": skipped,
        "deleted": deleted,
        "chunks": total_chunks,
        "per_doc_chunks": per_doc_chunks,
    }
