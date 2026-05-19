"""RenderArtifactsPanel — bottom panel listing rendered artifacts for a run.

Watches the run's exports/ directory. Lists files with size + format icon.
Enter → open with system handler (xdg-open / open / start).

Spec: docs/spec/22_circular_outputs.md § 1. Step kind: render
"""
from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_FORMAT_ICONS: dict[str, str] = {
    "pptx": "📊",
    "docx": "📄",
    "xlsx": "📋",
    "pdf": "📑",
    "md": "📝",
}


@dataclass
class RenderArtifactsPanel:
    """In-memory model of the render artifacts bottom panel."""

    artifacts: list[dict[str, Any]] = field(default_factory=list)

    def add_artifact(self, path: Path) -> None:
        suffix = path.suffix.lstrip(".")
        size = path.stat().st_size if path.exists() else 0
        self.artifacts.append({
            "path": str(path),
            "format": suffix,
            "size_bytes": size,
            "icon": self.format_icon(suffix),
        })

    def format_icon(self, fmt: str) -> str:
        return _FORMAT_ICONS.get(fmt.lower(), "📁")

    def open_artifact(self, index: int) -> None:
        """Open artifact at index with the system handler."""
        if index < 0 or index >= len(self.artifacts):
            return
        path = self.artifacts[index]["path"]
        if sys.platform == "darwin":
            subprocess.run(["open", path], check=False)
        elif sys.platform == "win32":
            import os
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            subprocess.run(["xdg-open", path], check=False)

    def summary_line(self, index: int) -> str:
        """One-line summary for display: icon + name + size."""
        if index < 0 or index >= len(self.artifacts):
            return ""
        a = self.artifacts[index]
        size_kb = a["size_bytes"] / 1024
        name = Path(a["path"]).name
        return f"{a['icon']} {name}  ({size_kb:.1f} KB)"
