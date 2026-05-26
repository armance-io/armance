"""D.8 — argument_ledger extract + persist tests."""
from __future__ import annotations

import json
from pathlib import Path

from armance.service.argument_ledger import (
    extract_sidecars,
    persist_sidecars,
)


_FAKE_SYNTH = """## Synthèse

Voici la synthèse en quelques lignes.

```json argument-ledger
{
  "version": 1,
  "run_id": "run-1",
  "arguments": [
    {"id": "a_001", "claim": "Lancer en mode réduit.", "status": "retained"}
  ]
}
```

```json source-ledger
{
  "version": 1,
  "sources": [
    {"id": "s_001", "kind": "doc", "ref": "docs/x.pdf#chunk_1"}
  ]
}
```
"""


def test_extract_both_sidecars() -> None:
    out = extract_sidecars(_FAKE_SYNTH)
    assert set(out.keys()) == {"arguments", "sources"}
    assert out["arguments"]["version"] == 1
    assert out["arguments"]["arguments"][0]["id"] == "a_001"
    assert out["sources"]["sources"][0]["kind"] == "doc"


def test_extract_missing_returns_empty() -> None:
    assert extract_sidecars("Pure synthesis prose. No JSON.") == {}


def test_extract_malformed_json_skipped() -> None:
    md = (
        "## S\n"
        "```json argument-ledger\n"
        "{ not json }\n"
        "```\n"
    )
    assert extract_sidecars(md) == {}


def test_persist_writes_files(tmp_path: Path) -> None:
    paths = persist_sidecars(_FAKE_SYNTH, tmp_path)
    names = sorted(p.name for p in paths)
    assert names == ["arguments.json", "sources.json"]
    args = json.loads((tmp_path / "arguments.json").read_text())
    assert args["run_id"] == "run-1"


def test_persist_noop_without_sidecars(tmp_path: Path) -> None:
    assert persist_sidecars("Pure prose.", tmp_path) == []
    assert list(tmp_path.iterdir()) == []


def test_extract_argument_only(tmp_path: Path) -> None:
    md = (
        "Synth\n"
        "```json argument-ledger\n"
        '{"version": 1, "run_id": "x", "arguments": []}\n'
        "```\n"
    )
    out = extract_sidecars(md)
    assert "arguments" in out
    assert "sources" not in out
