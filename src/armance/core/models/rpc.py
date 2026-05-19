"""JSON-RPC 2.0 envelope dataclasses.

Spec: docs/spec/23_future_web_layer.md § Invariant 6

V1: wraps in-process Python calls.
Future P4: same DTOs cross the wire over HTTP/gRPC — no structural change.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class RpcError(BaseModel):
    """JSON-RPC 2.0 error object."""

    code: int
    message: str
    data: dict[str, Any] | None = None


class RpcRequest(BaseModel):
    """JSON-RPC 2.0 request envelope."""

    jsonrpc: Literal["2.0"] = "2.0"
    id: str | int
    method: str
    params: dict[str, Any] | list[Any]


class RpcResponse(BaseModel):
    """JSON-RPC 2.0 response envelope.

    Exactly one of `result` or `error` is non-None on a real response.
    Both may be None on a notification-style response (id omitted by caller).
    """

    jsonrpc: Literal["2.0"] = "2.0"
    id: str | int
    result: Any | None = None
    error: RpcError | None = None
