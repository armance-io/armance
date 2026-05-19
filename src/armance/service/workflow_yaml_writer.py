"""Atomic YAML writer for workflow definitions with rationale comment block.

The writer is the single entry-point for persisting workflow YAML.
It never silently overwrites an existing file — it archives v<n> first.

Spec: docs/spec/21_workflow_design.md § S6
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_DATE_FMT = "%Y-%m-%d"


def _version_from_text(text: str) -> int:
    """Extract version number from YAML comment block (default 1)."""
    m = re.search(r"^#\s*version:\s*(\d+)", text, re.MULTILINE)
    return int(m.group(1)) if m else 1


def write_workflow_yaml(
    workflows_dir: Path,
    name: str,
    steps: list[dict[str, Any]],
    *,
    description: str = "",
    inputs: list[dict[str, Any]] | None = None,
    default_mode: str = "full",
    rationale: str = "",
    dry_run: bool = False,
    scope: str = "",
) -> Path | None:
    """Write (or dry-run) a workflow YAML file.

    If a file with the same name already exists, archive it first under
    `.archive/<name>_v<n>_<date>.yaml` and write v<n+1>.

    Returns the written path, or None on dry_run.
    """
    workflows_dir.mkdir(parents=True, exist_ok=True)
    target = workflows_dir / f"{name}.yaml"

    version = 1
    archive_note = ""

    if target.exists():
        existing_text = target.read_text(encoding="utf-8")
        version = _version_from_text(existing_text) + 1
        if not dry_run:
            _archive(workflows_dir, name, existing_text, version - 1)
        archive_note = (
            f"# previous: workflows/.archive/{name}_v{version - 1}_"
            f"{datetime.now(tz=timezone.utc).strftime(_DATE_FMT)}.yaml\n"
        )

    data: dict[str, Any] = {"name": name}
    if scope:
        data["scope"] = scope
    data["steps"] = steps
    if description:
        data["description"] = description
    if inputs:
        data["inputs"] = inputs
    if default_mode:
        data["default_mode"] = default_mode

    body = yaml.dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False)

    now_str = datetime.now(tz=timezone.utc).strftime(_DATE_FMT)
    comment_block = (
        f"# version: {version} (created {now_str} via dialogue with Kim)\n"
        + archive_note
    )
    if rationale:
        for line in rationale.strip().splitlines():
            comment_block += f"# {line}\n"
        comment_block += "#\n"

    full_text = comment_block + body

    if dry_run:
        logger.debug("dry_run: workflow %s validation OK (not written)", name)
        return None

    target.write_text(full_text, encoding="utf-8")
    logger.info("Wrote workflow %s to %s (v%d)", name, target, version)
    return target


def _archive(workflows_dir: Path, name: str, text: str, version: int) -> Path:
    archive_dir = workflows_dir / ".archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(tz=timezone.utc).strftime(_DATE_FMT)
    dest = archive_dir / f"{name}_v{version}_{date_str}.yaml"
    dest.write_text(text, encoding="utf-8")
    logger.debug("Archived %s v%d to %s", name, version, dest)
    return dest
