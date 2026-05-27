"""A.10 — LAN bind: --bind 0.0.0.0 boots; /healthz answers from 127.0.0.1.

Per spec: armance web --bind 0.0.0.0 boots; the server is accessible on
any interface. The test verifies the boot succeeds and the LAN warning
is printed to stderr.
"""
from __future__ import annotations

import asyncio
import socket
import subprocess
import sys
import time
import os
import pytest
import httpx
from pathlib import Path


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.asyncio
async def test_lan_bind_boots_and_healthz(armance_root: Path) -> None:
    """armance web --bind 0.0.0.0 boots; /healthz answers from 127.0.0.1."""
    port = _free_port()
    env = {**os.environ, "ARMANCE_ROOT": str(armance_root.parent)}
    web_dir = Path(__file__).parent.parent.parent  # web/

    proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn",
            "backend.main:app",
            "--host", "0.0.0.0",
            "--port", str(port),
        ],
        cwd=str(web_dir),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        deadline = time.monotonic() + 10.0
        up = False
        async with httpx.AsyncClient() as client:
            while time.monotonic() < deadline:
                await asyncio.sleep(0.2)
                try:
                    resp = await client.get(f"http://127.0.0.1:{port}/healthz")
                    if resp.status_code == 200:
                        up = True
                        break
                except httpx.ConnectError:
                    pass
        assert up, f"Server bound to 0.0.0.0:{port} did not answer on 127.0.0.1"
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_lan_warning_printed_on_bind_0000(tmp_path: Path) -> None:
    """cmd_web prints LAN exposure warning when --bind 0.0.0.0 is given."""
    import io
    from contextlib import redirect_stderr
    from unittest.mock import patch

    # Monkeypatch subprocess.run to avoid actually starting a server.
    with patch("subprocess.run"):
        buf = io.StringIO()
        with redirect_stderr(buf):
            from armance.cli import cmd_web
            cmd_web(repo_root=tmp_path, remaining=["--bind", "0.0.0.0", "--no-browser"])
        assert "LAN exposure" in buf.getvalue()
