"""server_lock — pidfile single-instance + stop lifecycle."""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from armance.web import server_lock as sl


def test_write_read_clear_roundtrip(tmp_path: Path) -> None:
    # Use our own pid so the liveness check passes.
    sl.write_lock(tmp_path, os.getpid(), 8000)
    info = sl.read_lock(tmp_path)
    assert info is not None
    assert info.pid == os.getpid()
    assert info.port == 8000

    sl.clear_lock(tmp_path)
    assert sl.read_lock(tmp_path) is None


def test_read_lock_dead_pid_is_stale(tmp_path: Path) -> None:
    # A pid that is extremely unlikely to be alive.
    sl.write_lock(tmp_path, 2_000_000_001, 8000)
    assert sl.read_lock(tmp_path) is None
    # Stale pidfile was removed.
    assert not sl.pidfile_path(tmp_path).exists()


def test_read_lock_corrupt_is_stale(tmp_path: Path) -> None:
    path = sl.pidfile_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not json", encoding="utf-8")
    assert sl.read_lock(tmp_path) is None
    assert not path.exists()


def test_stop_server_no_lock(tmp_path: Path) -> None:
    stopped, msg = sl.stop_server(tmp_path)
    assert stopped is False
    assert "no running server" in msg


def test_stop_server_signals_and_clears(tmp_path: Path) -> None:
    sl.write_lock(tmp_path, os.getpid(), 8000)
    # Pretend the process dies right after the first signal.
    # read_lock checks alive (True), then the stop loop sees it die (False).
    with patch.object(sl, "_signal") as sig, \
         patch.object(sl, "_pid_alive", side_effect=[True, False]):
        stopped, msg = sl.stop_server(tmp_path)
    assert stopped is True
    assert sig.called
    assert sl.read_lock(tmp_path) is None
