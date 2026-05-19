"""Provenance sidecar writer for kind=render artifacts.

Every rendered artifact gets a <path>.provenance.yaml that traces it
back to its source workflow run, steps, context versions, and claim refs.

Spec: docs/spec/22_circular_outputs.md § Provenance frontmatter
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


def write_provenance(
    artifact_path: Path,
    *,
    workflow: str,
    run_id: str,
    step_id: str,
    format: str,  # noqa: A002 — mirrors spec field name
    template: Path | None = None,
    inputs_from: list[str] | None = None,
    context_versions: list[str] | None = None,
    claim_refs: list[str] | None = None,
) -> Path:
    """Write a .provenance.yaml sidecar next to artifact_path.

    Returns the sidecar path.
    """
    sha256 = ""
    if artifact_path.exists():
        h = hashlib.sha256(artifact_path.read_bytes())
        sha256 = h.hexdigest()

    fmt = format
    data: dict[str, Any] = {
        "artifact": str(artifact_path),
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "workflow": workflow,
        "run_id": run_id,
        "step": step_id,
        "format": fmt,
        "template": str(template) if template else None,
        "inputs_from": inputs_from or [],
        "context_versions": context_versions or [],
        "claim_refs": claim_refs or [],
        "sha256": sha256,
    }

    sidecar = artifact_path.parent / (artifact_path.name + ".provenance.yaml")
    sidecar.write_text(yaml.dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    logger.debug("Wrote provenance to %s", sidecar)
    return sidecar
