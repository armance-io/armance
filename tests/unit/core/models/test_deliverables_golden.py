"""Deliverable rendering golden cases (Phase 4.1).

3 fixture reports: short, medium (with code block), long (with table).
For each: render docx, pptx, pdf (if WeasyPrint available).
Assert: file exists, non-zero size, valid zip for docx/pptx.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from armance.core.models.deliverables import parse_report, render_docx, render_pptx


SHORT_REPORT = """\
# Short Report

## Summary

This is a brief summary.
"""

MEDIUM_REPORT = """\
# Technical Review

## Overview

High-level analysis of the system.

## Code Analysis

Key patterns identified in the codebase:

- Pattern A: dependency injection
- Pattern B: event-driven architecture
- Pattern C: CQRS separation

## Recommendations

1. Refactor the auth layer
2. Add integration tests
3. Document public APIs
"""

LONG_REPORT = """\
# Financial Decision Report

## Executive Summary

This report covers the Q3 financial decision framework.

## Market Analysis

Strong demand signals across all segments.

- Segment A: 18% growth
- Segment B: 12% growth
- Segment C: 5% growth

## Risk Assessment

Key risks identified and their mitigations:

- Currency risk: hedge with forward contracts
- Liquidity risk: maintain 3-month runway
- Regulatory risk: engage legal team

## Investment Allocation

| Category | Budget | Priority |
|---|---|---|
| R&D | $2M | High |
| Sales | $1.5M | High |
| Ops | $0.5M | Medium |

## Recommendations

1. Proceed with Series B raise
2. Focus on Segment A expansion
3. Defer Segment C investment to Q4
4. Engage two new enterprise clients in Q3
"""

FIXTURES = [
    ("short", SHORT_REPORT),
    ("medium", MEDIUM_REPORT),
    ("long", LONG_REPORT),
]


@pytest.mark.parametrize("name,report_md", FIXTURES)
def test_render_docx_golden(name: str, report_md: str, tmp_path: Path) -> None:
    tree = parse_report(report_md)
    out = tmp_path / f"{name}.docx"
    render_docx(tree, out)
    assert out.exists()
    assert out.stat().st_size > 0
    assert zipfile.is_zipfile(out), f"{name}.docx is not a valid zip"


@pytest.mark.parametrize("name,report_md", FIXTURES)
def test_render_pptx_golden(name: str, report_md: str, tmp_path: Path) -> None:
    tree = parse_report(report_md)
    out = tmp_path / f"{name}.pptx"
    render_pptx(tree, out)
    assert out.exists()
    assert out.stat().st_size > 0
    assert zipfile.is_zipfile(out), f"{name}.pptx is not a valid zip"


@pytest.mark.parametrize("name,report_md", FIXTURES)
def test_render_pdf_golden(name: str, report_md: str, tmp_path: Path) -> None:
    try:
        from armance.core.models.deliverables import render_pdf
    except ImportError:
        pytest.skip("render_pdf not available")

    out = tmp_path / f"{name}.pdf"
    try:
        render_pdf(tree := parse_report(report_md), out)
    except Exception as exc:
        if "WeasyPrint" in str(exc) or "weasyprint" in str(exc).lower():
            pytest.skip(f"WeasyPrint not available: {exc}")
        raise
    assert out.exists()
    assert out.stat().st_size > 0
