from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from armance.platform.storage import Storage

logger = logging.getLogger(__name__)


def extract_markdown_title(path: Path) -> str:
    """Extract the first heading from a Markdown file, falling back to the filename stem."""
    if not path.exists():
        return path.stem
    try:
        content = path.read_text(encoding="utf-8")
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("#"):
                title = line.lstrip("#").strip()
                if title:
                    return title
    except Exception as e:
        logger.warning("Failed to extract title from %s: %s", path, e)
    return path.stem


async def get_starred_ids(storage: Storage) -> list[str]:
    """Read starred deliverable IDs from deliverables.json."""
    key = "deliverables.json"
    if await storage.exists(key):
        try:
            content = await storage.read_text(key)
            data = json.loads(content)
            if isinstance(data, dict) and "starred" in data:
                return list(data["starred"])
        except Exception as e:
            logger.warning("Failed to read starred deliverables: %s", e)
    return []


async def set_starred_id(storage: Storage, deliverable_id: str, starred: bool) -> None:
    """Add or remove a deliverable ID from deliverables.json."""
    key = "deliverables.json"
    starred_ids = await get_starred_ids(storage)
    if starred:
        if deliverable_id not in starred_ids:
            starred_ids.append(deliverable_id)
    else:
        if deliverable_id in starred_ids:
            starred_ids.remove(deliverable_id)
    
    data = {"starred": starred_ids}
    await storage.write_text(key, json.dumps(data, indent=2))


async def list_deliverables(armance_root: Path, storage: Storage) -> list[dict[str, Any]]:
    """Walk both sources of deliverables and return an aggregated index.
    
    Source 1: Every synthesis.md and any *.pdf|docx|pptx under exports/<workflow>/run-*/
    Source 2: Every mona-*.md under docs/
    """
    starred_ids = await get_starred_ids(storage)
    deliverables = []

    # Source 1: Exports
    exports_dir = armance_root / "exports"
    if exports_dir.exists():
        for wf_dir in exports_dir.iterdir():
            if not wf_dir.is_dir():
                continue
            workflow_name = wf_dir.name
            for run_dir in wf_dir.iterdir():
                if not run_dir.is_dir() or not run_dir.name.startswith("run-"):
                    continue
                run_id = run_dir.name
                
                # Check for synthesis.md
                synth_path = run_dir / "synthesis.md"
                if synth_path.exists() and synth_path.is_file():
                    rel_path = f"exports/{workflow_name}/{run_id}/synthesis.md"
                    created_at = datetime.fromtimestamp(
                        synth_path.stat().st_mtime, timezone.utc
                    ).isoformat().replace("+00:00", "Z")
                    title = extract_markdown_title(synth_path)
                    deliverables.append({
                        "id": rel_path,
                        "title": title,
                        "kind": "synthesis",
                        "format": "md",
                        "workflow": workflow_name,
                        "run_id": run_id,
                        "created_at": created_at,
                        "size_bytes": synth_path.stat().st_size,
                        "starred": rel_path in starred_ids,
                    })
                
                # Check for *.pdf, *.docx, *.pptx
                for file in run_dir.iterdir():
                    if file.is_file() and file.suffix.lower() in [".pdf", ".docx", ".pptx"]:
                        ext = file.suffix.lower()[1:]
                        rel_path = f"exports/{workflow_name}/{run_id}/{file.name}"
                        created_at = datetime.fromtimestamp(
                            file.stat().st_mtime, timezone.utc
                        ).isoformat().replace("+00:00", "Z")
                        
                        # Try to get title from synthesis.md in same folder, fallback to stem
                        synth_sibling = run_dir / "synthesis.md"
                        if synth_sibling.exists():
                            title = extract_markdown_title(synth_sibling)
                        else:
                            title = file.stem
                        
                        deliverables.append({
                            "id": rel_path,
                            "title": title,
                            "kind": "export",
                            "format": ext,
                            "workflow": workflow_name,
                            "run_id": run_id,
                            "created_at": created_at,
                            "size_bytes": file.stat().st_size,
                            "starred": rel_path in starred_ids,
                        })

    # Source 2: Docs (mona-*.md)
    docs_dir = armance_root / "docs"
    if docs_dir.exists():
        for file in docs_dir.iterdir():
            if file.is_file() and file.name.startswith("mona-") and file.suffix.lower() == ".md":
                rel_path = f"docs/{file.name}"
                created_at = datetime.fromtimestamp(
                    file.stat().st_mtime, timezone.utc
                ).isoformat().replace("+00:00", "Z")
                title = extract_markdown_title(file)
                deliverables.append({
                    "id": rel_path,
                    "title": title,
                    "kind": "mona-deliverable",
                    "format": "md",
                    "workflow": "",
                    "run_id": "",
                    "created_at": created_at,
                    "size_bytes": file.stat().st_size,
                    "starred": rel_path in starred_ids,
                })

    # Sort: Starred items float to the top, then sorted by created_at desc
    deliverables.sort(key=lambda x: (x["starred"], x["created_at"]), reverse=True)
    return deliverables
