"""Tests for armance.service.report."""
from __future__ import annotations

from pathlib import Path

from armance.service.report import (
    PARTIAL_MARKER,
    Report,
    next_version,
    read_report,
    truncate_prompt,
    write_report,
)
from armance.core.models.task import Task


def test_truncate_prompt_caps_at_150_chars() -> None:
    long = "a" * 500
    assert len(truncate_prompt(long)) == 150


def test_task_round_trip() -> None:
    t = Task(prompt="hi", role="backend", mode="full")
    assert t.role == "backend"
    assert t.mode == "full"


def test_write_report_increments_version(tmp_path: Path) -> None:
    r1 = Report.from_completion(
        agent_name="alpha", role="backend", prompt="p", content="body1", finish_reason="stop"
    )
    p1 = write_report(r1, tmp_path)
    assert p1.name == "alpha_v1.md"

    r2 = Report.from_completion(
        agent_name="alpha", role="backend", prompt="p", content="body2", finish_reason="stop"
    )
    p2 = write_report(r2, tmp_path)
    assert p2.name == "alpha_v2.md"

    # different agent, fresh sequence
    r3 = Report.from_completion(
        agent_name="beta", role="backend", prompt="p", content="body3", finish_reason="stop"
    )
    p3 = write_report(r3, tmp_path)
    assert p3.name == "beta_v1.md"

    assert next_version(tmp_path / "backend", "alpha") == 3


def test_partial_flag_prepends_marker(tmp_path: Path) -> None:
    r = Report.from_completion(
        agent_name="alpha",
        role="backend",
        prompt="p",
        content="cut off here",
        finish_reason="length",
    )
    assert r.partial is True
    path = write_report(r, tmp_path)
    body = path.read_text(encoding="utf-8")
    # frontmatter then marker
    assert "partial: true" in body
    assert PARTIAL_MARKER in body
    after_close = body.split("---", 2)[2]
    assert after_close.lstrip().startswith(PARTIAL_MARKER)


def test_round_trip_read_report(tmp_path: Path) -> None:
    r = Report.from_completion(
        agent_name="alpha",
        role="backend",
        prompt="abc",
        content="hello",
        finish_reason="stop",
    )
    path = write_report(r, tmp_path)
    loaded = read_report(path)
    assert loaded.agent_name == "alpha"
    assert loaded.role == "backend"
    assert loaded.partial is False
    assert "hello" in loaded.content
