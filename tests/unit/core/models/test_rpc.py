"""Tests for core/models/rpc.py — JSON-RPC 2.0 envelope dataclasses."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from armance.core.models.rpc import RpcError, RpcRequest, RpcResponse


# ---------------------------------------------------------------------------
# RpcRequest
# ---------------------------------------------------------------------------

def test_rpc_request_happy_path() -> None:
    req = RpcRequest(id=1, method="armance.recruit", params={"role": "historian"})
    assert req.jsonrpc == "2.0"
    assert req.method == "armance.recruit"
    assert req.params == {"role": "historian"}


def test_rpc_request_id_can_be_str() -> None:
    req = RpcRequest(id="abc-123", method="armance.recruit", params={})
    assert req.id == "abc-123"


def test_rpc_request_id_int_roundtrip() -> None:
    req = RpcRequest(id=42, method="armance.recruit", params=[])
    assert req.id == 42


def test_rpc_request_jsonrpc_must_be_2_0() -> None:
    with pytest.raises(ValidationError):
        RpcRequest(jsonrpc="1.0", id=1, method="x", params={})  # type: ignore[arg-type]


def test_rpc_request_params_list_accepted() -> None:
    req = RpcRequest(id=1, method="m", params=["a", "b"])
    assert req.params == ["a", "b"]


# ---------------------------------------------------------------------------
# RpcResponse — success
# ---------------------------------------------------------------------------

def test_rpc_response_success() -> None:
    resp = RpcResponse(id=1, result={"agents": ["aisha"]})
    assert resp.jsonrpc == "2.0"
    assert resp.result == {"agents": ["aisha"]}
    assert resp.error is None


def test_rpc_response_str_id() -> None:
    resp = RpcResponse(id="abc", result="ok")
    assert resp.id == "abc"


# ---------------------------------------------------------------------------
# RpcResponse — error
# ---------------------------------------------------------------------------

def test_rpc_response_error() -> None:
    err = RpcError(code=-32600, message="Invalid Request")
    resp = RpcResponse(id=1, error=err)
    assert resp.error is not None
    assert resp.error.code == -32600
    assert resp.result is None


def test_rpc_error_optional_data() -> None:
    err = RpcError(code=-32603, message="Internal error", data={"detail": "boom"})
    assert err.data == {"detail": "boom"}


def test_rpc_error_no_data_by_default() -> None:
    err = RpcError(code=-32600, message="bad")
    assert err.data is None


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------

def test_rpc_request_serialises_jsonrpc_field() -> None:
    import json
    req = RpcRequest(id=1, method="armance.run", params={})
    data = json.loads(req.model_dump_json())
    assert data["jsonrpc"] == "2.0"


def test_rpc_response_serialises_error() -> None:
    import json
    resp = RpcResponse(id=2, error=RpcError(code=-1, message="fail"))
    data = json.loads(resp.model_dump_json())
    assert data["error"]["code"] == -1
    assert data["jsonrpc"] == "2.0"
