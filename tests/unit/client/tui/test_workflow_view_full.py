"""T-25i: TUI surfacing of claims, render artifacts, Serge output.

Spec: docs/spec/19_claim_ledger.md § TUI surfacing
"""
from __future__ import annotations

import pytest

from armance.client.tui.widgets.workflow_view import (
    render_dag_ascii,
    format_claim_density,
    classify_agent_kind,
)
from armance.client.tui.widgets.claims_panel import ClaimsPanel
from armance.client.tui.widgets.render_artifacts_panel import RenderArtifactsPanel


# ---------------------------------------------------------------------------
# render_dag_ascii (already tested implicitly by T-25e; extend here)
# ---------------------------------------------------------------------------

def test_dag_ascii_single_step() -> None:
    steps = [{"id": "s1", "kind": "task", "depends_on": []}]
    out = render_dag_ascii(steps)
    assert "s1" in out
    assert "task" in out


def test_dag_ascii_chain() -> None:
    steps = [
        {"id": "a", "kind": "task", "depends_on": []},
        {"id": "b", "kind": "judge", "depends_on": ["a"]},
    ]
    out = render_dag_ascii(steps)
    assert "a" in out
    assert "b" in out


# ---------------------------------------------------------------------------
# format_claim_density
# ---------------------------------------------------------------------------

def test_claim_density_format() -> None:
    header = format_claim_density(total=4, verified=2, disputed=1, unsourced=1)
    assert "4" in header
    assert "2" in header
    assert "verified" in header.lower() or "✓" in header
    assert "disputed" in header.lower() or "!" in header


def test_claim_density_zeros() -> None:
    header = format_claim_density(total=0, verified=0, disputed=0, unsourced=0)
    assert "0" in header


# ---------------------------------------------------------------------------
# classify_agent_kind — Serge vs Mona vs others
# ---------------------------------------------------------------------------

def test_classify_mona() -> None:
    kind = classify_agent_kind("Mona · synthesis")
    assert kind == "synthesis"


def test_classify_serge() -> None:
    kind = classify_agent_kind("Serge · challenger")
    assert kind == "critique"


def test_classify_specialist() -> None:
    kind = classify_agent_kind("Lars · historian")
    assert kind == "specialist"


def test_classify_unknown() -> None:
    kind = classify_agent_kind("")
    assert kind == "specialist"


# ---------------------------------------------------------------------------
# ClaimsPanel — pure data model (no Textual)
# ---------------------------------------------------------------------------

def test_claims_panel_constructs() -> None:
    panel = ClaimsPanel()
    assert panel.total == 0
    assert panel.verified == 0
    assert panel.disputed == 0
    assert panel.unsourced == 0


def test_claims_panel_update() -> None:
    panel = ClaimsPanel()
    panel.update(total=5, verified=3, disputed=1, unsourced=1)
    assert panel.total == 5
    assert panel.header_text  # non-empty after update


def test_claims_panel_claim_list() -> None:
    panel = ClaimsPanel()
    panel.add_claim(claim_id="c_abc", text="Main claim", status="verified")
    panel.add_claim(claim_id="c_def", text="Another claim", status="disputed")
    assert len(panel.claims) == 2
    ids = [c["id"] for c in panel.claims]
    assert "c_abc" in ids


# ---------------------------------------------------------------------------
# RenderArtifactsPanel
# ---------------------------------------------------------------------------

def test_render_artifacts_panel_constructs() -> None:
    panel = RenderArtifactsPanel()
    assert panel.artifacts == []


def test_render_artifacts_panel_add_file(tmp_path) -> None:
    f = tmp_path / "report.pptx"
    f.write_bytes(b"fake pptx")
    panel = RenderArtifactsPanel()
    panel.add_artifact(path=f)
    assert len(panel.artifacts) == 1
    entry = panel.artifacts[0]
    assert entry["path"] == str(f)
    assert entry["format"] == "pptx"
    assert entry["size_bytes"] == 9


def test_render_artifacts_panel_format_icon() -> None:
    panel = RenderArtifactsPanel()
    assert panel.format_icon("pptx") != ""
    assert panel.format_icon("pdf") != ""
    assert panel.format_icon("md") != ""
