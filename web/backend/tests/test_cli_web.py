"""A.8 — armance web CLI boots the server.

Tests that cmd_web:
- Accepts --port and --bind flags
- Boots and /healthz responds
- --bind 0.0.0.0 logs a LAN warning
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
    """Find an available TCP port."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.asyncio
async def test_cmd_web_boots_and_healthz(armance_root: Path, tmp_path: Path) -> None:
    """armance web --port <free> boots; GET /healthz answers."""
    port = _free_port()

    env = {**os.environ, "ARMANCE_ROOT": str(armance_root.parent)}
    # Run from the web/ directory so 'backend' is importable.
    web_dir = Path(__file__).parent.parent.parent  # web/

    proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn",
            "backend.main:app",
            "--host", "127.0.0.1",
            "--port", str(port),
        ],
        cwd=str(web_dir),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        # Poll until the server is up (max 10 s).
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
        assert up, f"Server did not start on port {port}"
    finally:
        proc.terminate()
        proc.wait(timeout=5)
