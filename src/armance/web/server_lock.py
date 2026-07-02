"""Single-instance lock + lifecycle for the `armance web` server.

A pidfile at ``.armance/web-server.pid`` records the running server's pid,
port and start time. It enforces one instance per project folder and lets
``armance web --stop`` find and terminate the server.

Liveness uses ``os.kill(pid, 0)`` (stdlib) so no extra dependency is needed.
On POSIX the server is launched in its own session (``start_new_session``),
so stopping signals the whole process group.
"""
from __future__ import annotations

import json
import logging
import os
import signal
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

PIDFILE_NAME = "web-server.pid"


@dataclass
class LockInfo:
    pid: int
    port: int
    started_at: float


def pidfile_path(data_dir: Path) -> Path:
    """Return the pidfile path inside *data_dir*.

    *data_dir* is the directory that holds the server's runtime files — for a
    project it is ``<folder>/.armance``; for the global launcher it is the
    global config dir itself (so the launcher does not nest a redundant
    ``.armance`` under ``~/.config/armance``).
    """
    return data_dir / PIDFILE_NAME


def _pid_alive(pid: int) -> bool:
    """True if a process with *pid* exists and is signalable by us."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except PermissionError:
        # Exists but owned by another user — still "alive" for our purposes.
        return True
    except OSError:
        # On POSIX, catches ProcessLookupError. On Windows, OSError [WinError 87]
        # represents a dead or non-existent process.
        return False
    return True


def read_lock(data_dir: Path) -> LockInfo | None:
    """Return the live lock in *data_dir*, or None.

    A pidfile whose process is no longer running is stale: it is removed and
    None is returned, so a fresh launch can proceed.
    """
    path = pidfile_path(data_dir)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        info = LockInfo(
            pid=int(data["pid"]),
            port=int(data.get("port", 0)),
            started_at=float(data.get("started_at", 0.0)),
        )
    except (ValueError, KeyError, OSError):
        logger.warning("unreadable web pidfile %s — treating as stale", path)
        _remove(path)
        return None
    if not _pid_alive(info.pid):
        _remove(path)
        return None
    return info


def write_lock(data_dir: Path, pid: int, port: int) -> None:
    """Record the running server's pid + port."""
    path = pidfile_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"pid": pid, "port": port, "started_at": time.time()}
    path.write_text(json.dumps(payload), encoding="utf-8")


def clear_lock(data_dir: Path) -> None:
    """Remove the pidfile (no-op if absent)."""
    _remove(pidfile_path(data_dir))


def _remove(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    except OSError as exc:
        logger.warning("could not remove pidfile %s: %s", path, exc)


def stop_server(data_dir: Path, *, timeout: float = 10.0) -> tuple[bool, str]:
    """Stop the running server recorded in *data_dir*.

    Returns ``(stopped, message)``. ``stopped`` is False when no live server
    was found. Sends SIGTERM (to the process group on POSIX), waits up to
    *timeout* seconds, then escalates to SIGKILL.
    """
    info = read_lock(data_dir)
    if info is None:
        return False, "no running server found"

    pid = info.pid
    _signal(pid, signal.SIGTERM)

    deadline = time.time() + timeout
    while time.time() < deadline:
        if not _pid_alive(pid):
            clear_lock(data_dir)
            return True, f"stopped web server (pid {pid})"
        time.sleep(0.2)

    # Escalate. signal.SIGKILL does not exist on Windows — fall back to
    # SIGTERM there (the only signal os.kill honours on that platform).
    _signal(pid, getattr(signal, "SIGKILL", signal.SIGTERM))
    time.sleep(0.3)
    clear_lock(data_dir)
    if _pid_alive(pid):
        return True, f"sent SIGKILL to web server (pid {pid}) — verify it exited"
    return True, f"killed web server (pid {pid})"


def _signal(pid: int, sig: int) -> None:
    """Signal the server's process group on POSIX, else the process."""
    try:
        if hasattr(os, "killpg"):
            try:
                os.killpg(os.getpgid(pid), sig)
                return
            except (ProcessLookupError, PermissionError, OSError):
                pass
        os.kill(pid, sig)
    except ProcessLookupError:
        pass
    except OSError as exc:
        logger.warning("failed to signal pid %s: %s", pid, exc)
