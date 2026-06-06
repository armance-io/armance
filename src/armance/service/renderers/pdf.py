"""PDF renderer — Markdown → HTML → PDF via weasyprint (or pandoc fallback).

Spec: docs/spec/22_circular_outputs.md § Supported formats (pdf)
"""
from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path

from .base import Deliverable, RenderResult

logger = logging.getLogger(__name__)


def _md_to_html(content: str) -> str:
    """Convert markdown to minimal HTML."""
    try:
        import markdown  # type: ignore
        return f"<html><body>{markdown.markdown(content)}</body></html>"
    except ImportError:
        # Fallback: wrap raw text in pre
        escaped = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return f"<html><body><pre>{escaped}</pre></body></html>"


class PdfRenderer:
    """Renders deliverables into a PDF document."""

    format = "pdf"

    async def render(
        self,
        deliverables: list[Deliverable],
        template: Path | None,
        options: dict,
        output_path: Path,
    ) -> RenderResult:
        combined = "\n\n".join(d.content for d in deliverables)
        html = _md_to_html(combined)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Try weasyprint first
        try:
            from weasyprint import HTML  # type: ignore
            HTML(string=html).write_pdf(str(output_path))
            size = output_path.stat().st_size
            return RenderResult(
                output_path=output_path,
                bytes_written=size,
                pages_or_slides=1,
            )
        except ImportError:
            pass

        # Fallback: pandoc
        pandoc = subprocess.run(["which", "pandoc"], capture_output=True)
        if pandoc.returncode == 0:
            with tempfile.NamedTemporaryFile(suffix=".md", delete=False, mode="w") as f:
                f.write(combined)
                tmp = f.name
            r = subprocess.run(
                ["pandoc", tmp, "-o", str(output_path)],
                capture_output=True,
            )
            if r.returncode == 0:
                size = output_path.stat().st_size
                return RenderResult(
                    output_path=output_path,
                    bytes_written=size,
                    pages_or_slides=1,
                    warnings=["used pandoc fallback (weasyprint not installed)"],
                )
            return RenderResult(
                output_path=output_path,
                error=f"pandoc failed: {r.stderr.decode()}",
                warnings=["pandoc fallback failed"],
            )

        return RenderResult(
            output_path=output_path,
            warnings=[
                "weasyprint not installed; install with: pip install 'armance[pdf]'",
                "pandoc not found either",
            ],
            error="no PDF renderer available; install weasyprint or pandoc",
        )
