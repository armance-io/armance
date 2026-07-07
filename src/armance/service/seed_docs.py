"""Load seed documents for a workflow run (Lot B).

A *seed document* is existing material — e.g. a drafted tender — that the
user wants a workflow to challenge/extend rather than write from scratch.
Steps reference library files by basename via `WorkflowStep.seed_docs`; a
run may also pass ad-hoc files via the `seed:<key>=<path>` CLI input.

Layering: file reads live here in the `service` layer. `core` never touches
the disk — the loaded text is handed to `execute_workflow(..., inputs=...)`
under `seed.<basename>` keys, where the executor and the default-prompt
composer surface it (`{{seed.<basename>}}` / the "## Seed documents" block).
"""
from __future__ import annotations

import logging
from pathlib import Path

from armance.service.agents.host_agent import _read_doc_text

logger = logging.getLogger(__name__)

# Per-file cap: seed docs feed straight into an LLM prompt; a full tender can
# be tens of thousands of chars, and every parallel step gets a copy. 6000
# chars (~1500 tokens) keeps the root step grounded without blowing the budget.
MAX_SEED_CHARS = 6000

_READABLE_SUFFIXES = (".md", ".txt", ".text", ".pdf", ".docx", ".doc", "")


def _read_capped(path: Path) -> str:
    text = _read_doc_text(path)
    if not text or not text.strip():
        return ""
    return text[:MAX_SEED_CHARS]


def load_library_seed_docs(armance_root: Path, basenames: list[str]) -> dict[str, str]:
    """Read library docs (under `.armance/docs/`) by basename.

    Returns a dict keyed `seed.<basename>` → capped text. Missing or empty
    files are skipped (logged, never raised — a run must not die because a
    seed doc vanished).
    """
    out: dict[str, str] = {}
    if not basenames:
        return out
    docs_dir = armance_root / "docs"
    if not docs_dir.exists():
        logger.warning("seed docs requested but %s does not exist", docs_dir)
        return out
    wanted = set(basenames)
    found: set[str] = set()
    for f in sorted(docs_dir.rglob("*")):
        if not f.is_file() or f.name not in wanted:
            continue
        if f.suffix.lower() not in _READABLE_SUFFIXES:
            continue
        text = _read_capped(f)
        if text:
            out[f"seed.{f.name}"] = text
            found.add(f.name)
    for missing in wanted - found:
        logger.warning("seed doc not found or empty in library: %s", missing)
    return out


def load_adhoc_seed_docs(specs: list[str]) -> dict[str, str]:
    """Read ad-hoc seed docs from `--input` specs of the form `key=path`.

    A bare `path` uses the file's stem as the key. Returns a dict keyed
    `seed.<key>` → capped text. Unreadable/missing paths are skipped.
    """
    out: dict[str, str] = {}
    for spec in specs:
        if "=" in spec:
            key, _, raw_path = spec.partition("=")
            key = key.strip()
            path = Path(raw_path.strip()).expanduser()
        else:
            path = Path(spec.strip()).expanduser()
            key = path.stem
        if not key or not path.is_file():
            logger.warning("seed --input skipped (not a file): %s", spec)
            continue
        text = _read_capped(path)
        if text:
            out[f"seed.{key}"] = text
        else:
            logger.warning("seed --input empty: %s", spec)
    return out
