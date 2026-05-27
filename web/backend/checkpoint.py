"""WebCheckpointHandler — bridges CheckpointHandler protocol to HTTP round-trip.

When the service layer hits a checkpoint:
  1. Mint a checkpoint id (unique per prompt call).
  2. Emit a 'checkpoint_requested' SSE event to the connected client.
  3. Wait on an asyncio.Future for the matching POST /…/checkpoint.

The matching resolve() is called from the checkpoint route handler.

Per web-layer.md § 3.
"""
from __future__ import annotations

import asyncio
import uuid
import logging

from armance.service.checkpoint import (
    Checkpoint,
    CheckpointResponse,
)

logger = logging.getLogger(__name__)


class WebCheckpointHandler:
    """Implements CheckpointHandler for the web frontend."""

    def __init__(self, bus: object, timeout: float = 600.0) -> None:
        self._bus = bus
        self._timeout = timeout
        self._pending: dict[str, asyncio.Future[CheckpointResponse]] = {}

    async def prompt(self, checkpoint: Checkpoint) -> CheckpointResponse:
        """Block until the frontend resolves this checkpoint via POST /checkpoint."""
        cp_id = f"{checkpoint.id}:{uuid.uuid4().hex[:8]}"
        loop = asyncio.get_event_loop()
        fut: asyncio.Future[CheckpointResponse] = loop.create_future()
        # Register BEFORE publishing — no race window.
        self._pending[cp_id] = fut
        # Emit as 'checkpoint.requested' (component.action format).
        # Complex values (options dict) are JSON-serialised to strings.
        import json
        await self._bus.emit("checkpoint.requested", attributes={
            "checkpoint_id": cp_id,
            "kind": checkpoint.kind,
            "prompt": checkpoint.prompt,
            "options": json.dumps(checkpoint.options),
        })
        try:
            return await asyncio.wait_for(fut, timeout=self._timeout)
        finally:
            self._pending.pop(cp_id, None)

    def resolve(self, cp_id: str, content: str, is_abort: bool = False) -> bool:
        """Called from POST /…/checkpoint.  Returns True if resolved."""
        fut = self._pending.get(cp_id)
        if fut is None or fut.done():
            return False
        fut.set_result(CheckpointResponse(content=content, is_abort=is_abort))
        return True
