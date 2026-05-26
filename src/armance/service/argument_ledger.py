"""D.8 — argument_ledger parser + persister.

Mona's `judge` step writes its synthesis to Markdown, with two optional
fenced ```json``` blocks tagged `argument-ledger` and `source-ledger`
that carry structured payloads (schemas D.B + D.C in web-d-pipeline.md).

This module extracts those blocks and persists them as side-car files
next to synthesis.md, so the D.7 routes can serve them without
re-parsing the synthesis on every request.

Spec: web-d-pipeline.md § D.8 + D.B + D.C
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)

# `[ \t]*` is intentional — only horizontal whitespace before the fence,
# so the regex matches a fenced block at the start of a line.
_FENCE_RE = re.compile(
    r"```json\s+(argument-ledger|source-ledger)\s*\n(.*?)```",
    re.DOTALL | re.IGNORECASE,
)

_KIND_TO_SIDECAR: Dict[str, str] = {
    "argument-ledger": "arguments",
    "source-ledger": "sources",
}

_SIDECAR_TO_FILENAME: Dict[str, str] = {
    "arguments": "arguments.json",
    "sources": "sources.json",
}


def extract_sidecars(synthesis_markdown: str) -> Dict[str, dict]:
    """Return { "arguments": <payload>, "sources": <payload> } when
    fenced blocks are present and parse cleanly. Missing or malformed
    blocks are silently skipped (logged at DEBUG).
    """
    out: Dict[str, dict] = {}
    for match in _FENCE_RE.finditer(synthesis_markdown):
        tag = match.group(1).lower()
        raw = match.group(2)
        key = _KIND_TO_SIDECAR.get(tag)
        if key is None:
            continue
        try:
            parsed = json.loads(raw)
        except Exception:
            logger.debug("malformed %s JSON block — skipped", tag)
            continue
        if isinstance(parsed, dict):
            out[key] = parsed
    return out


def persist_sidecars(synthesis_markdown: str, run_dir: Path) -> List[Path]:
    """Extract sidecars and write them as JSON files alongside synthesis.md.

    Returns the list of paths written.  When no sidecar is present, the
    function is a no-op and returns an empty list — the run directory
    stays untouched.
    """
    parsed = extract_sidecars(synthesis_markdown)
    if not parsed:
        return []
    written: List[Path] = []
    for key, payload in parsed.items():
        filename = _SIDECAR_TO_FILENAME.get(key)
        if filename is None:
            continue
        target = run_dir / filename
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        written.append(target)
    return written
