"""Tests for armance.service.session."""
from __future__ import annotations

import time
from pathlib import Path


from armance.service.session import (
    Session,
    SessionState,
    latest_session_id,
    load_state,
    save_state,
    start_or_resume,
)


def test_save_then_load_round_trip(tmp_path: Path) -> None:
    state = SessionState.new()
    state.current_agent = "alpha"
    state.current_workflow = "brainstorm"
    state.current_step_id = "explore"
    save_state(tmp_path, state)

    loaded = load_state(tmp_path, state.id)
    assert loaded.id == state.id
    assert loaded.current_agent == "alpha"
    assert loaded.current_workflow == "brainstorm"
    assert loaded.current_step_id == "explore"
    assert loaded.ledger_path is not None and loaded.ledger_path.endswith("ledger.json")


def test_latest_session_id_picks_newest(tmp_path: Path) -> None:
    s1 = SessionState.new()
    save_state(tmp_path, s1)
    time.sleep(0.01)
    s2 = SessionState.new()
    save_state(tmp_path, s2)

    assert latest_session_id(tmp_path) == s2.id


def test_start_or_resume_fresh_when_resume_false(tmp_path: Path) -> None:
    s1 = SessionState.new()
    save_state(tmp_path, s1)
    fresh = start_or_resume(tmp_path, resume=False)
    assert fresh.id != s1.id


def test_start_or_resume_picks_existing_when_resume_true(tmp_path: Path) -> None:
    s1 = SessionState.new()
    save_state(tmp_path, s1)
    resumed = start_or_resume(tmp_path, resume=True)
    assert resumed.id == s1.id


def test_start_or_resume_falls_back_to_fresh_when_no_prior(tmp_path: Path) -> None:
    state = start_or_resume(tmp_path, resume=True)
    assert state.id is not None
    assert (tmp_path / "sessions" / state.id / "state.json").exists()


# ── SessionState basic operations (TUIState removed) ────────────────────────

def test_session_state_new_creates_id_and_timestamp() -> None:
    s = SessionState.new()
    assert s.id is not None
    assert s.created_at is not None
    assert s.current_agent == "system-context"
    assert s.current_workflow is None
    assert s.ledger_path is None


def test_session_metadata_roundtrip(tmp_path: Path) -> None:
    state = SessionState.new()
    save_state(tmp_path, state)
    sess = Session(state, tmp_path)
    
    sess.metadata["host_buffer"] = ["fact 1", "fact 2"]
    sess.save()
    
    # Reload
    loaded_state = load_state(tmp_path, state.id)
    loaded_sess = Session(loaded_state, tmp_path)
    assert loaded_sess.metadata["host_buffer"] == ["fact 1", "fact 2"]


def test_session_state_round_trip(tmp_path: Path) -> None:
    s = SessionState.new()
    s.current_agent = "system-context"
    s.current_provider = "openrouter"
    s.current_model = "openai/gpt-4o-mini"
    save_state(tmp_path, s)
    loaded = load_state(tmp_path, s.id)
    assert loaded.current_agent == "system-context"
    assert loaded.current_provider == "openrouter"
    assert loaded.current_model == "openai/gpt-4o-mini"


# ── Session wrapper ─────────────────────────────────────────────────────────

def test_session_save(tmp_path: Path) -> None:
    state = SessionState.new()
    save_state(tmp_path, state)
    sess = Session(state, tmp_path)
    sess.save()
    assert (tmp_path / "sessions" / state.id / "state.json").exists()


def test_session_state_property(tmp_path: Path) -> None:
    state = SessionState.new()
    sess = Session(state, tmp_path)
    assert sess.state is state


# ── Atomic write ────────────────────────────────────────────────────────────

def test_atomic_write_leaves_no_tmp(tmp_path: Path) -> None:
    state = SessionState.new()
    save_state(tmp_path, state)
    sdir = tmp_path / "sessions" / state.id
    assert not (sdir / "state.tmp").exists()
    assert (sdir / "state.json").exists()


def test_latest_session_id_returns_none_when_no_sessions(tmp_path: Path) -> None:
    assert latest_session_id(tmp_path) is None
