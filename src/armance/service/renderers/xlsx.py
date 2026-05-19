"""XLSX renderer — markdown tables → sheets.

Requires openpyxl (optional [render] extra). Falls back gracefully.

Spec: docs/spec/22_circular_outputs.md § Supported formats (xlsx)
"""
from __future__ import annotations

import re
from pathlib import Path

from .base import Deliverable, RenderResult


def _parse_tables(content: str) -> list[list[list[str]]]:
    """Extract markdown tables as list of rows (each row is list of cells)."""
    tables: list[list[list[str]]] = []
    current: list[list[str]] = []
    for line in content.splitlines():
        if re.match(r"^\|[-| ]+\|$", line.strip()):
            continue  # separator row
        if line.strip().startswith("|") and line.strip().endswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            current.append(cells)
        else:
            if current:
                tables.append(current)
                current = []
    if current:
        tables.append(current)
    return tables


class XlsxRenderer:
    """Renders markdown tables in deliverables into Excel sheets."""

    format = "xlsx"

    async def render(
        self,
        deliverables: list[Deliverable],
        template: Path | None,
        options: dict,
        output_path: Path,
    ) -> RenderResult:
        try:
            import openpyxl  # type: ignore
        except ImportError:
            return RenderResult(
                output_path=output_path,
                warnings=["openpyxl not installed; install with: pip install armance[render]"],
                error="openpyxl not installed",
            )

        wb = openpyxl.Workbook()
        combined = "\n\n".join(d.content for d in deliverables)
        tables = _parse_tables(combined)

        if not tables:
            ws = wb.active
            ws.title = "Output"
            ws.append(["No tables found in deliverables"])
        else:
            for i, table in enumerate(tables):
                ws = wb.active if i == 0 else wb.create_sheet(f"Table {i + 1}")
                if i == 0:
                    ws.title = "Table 1"
                for row in table:
                    ws.append(row)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        wb.save(str(output_path))
        size = output_path.stat().st_size
        return RenderResult(
            output_path=output_path,
            bytes_written=size,
            pages_or_slides=len(tables) or 1,
        )
