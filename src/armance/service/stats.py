"""Per-agent token/cost/latency statistics derived from llm_exchanges.jsonl.

Pure read — never mutates the ledger.
"""
from __future__ import annotations

from typing import Any


def _empty_agent() -> dict[str, Any]:
    return {
        "tokens_in": 0,
        "tokens_out": 0,
        "cost_usd": 0.0,
        "msg_count": 0,
        "total_latency_ms": 0.0,
        "avg_latency_ms": 0.0,
    }


def compute_stats(records: list[dict]) -> dict[str, Any]:
    """Derive per-agent stats from a list of log records.

    Each response record contributes one message count + token/cost totals.
    ``latency_ms`` comes from the record's own field when present.
    """
    agents: dict[str, dict[str, Any]] = {}

    for rec in records:
        if rec.get("event") != "response":
            continue
        agent = rec.get("agent", "unknown")
        if agent not in agents:
            agents[agent] = _empty_agent()
        a = agents[agent]
        a["tokens_in"] += rec.get("tokens_in") or 0
        a["tokens_out"] += rec.get("tokens_out") or 0
        a["cost_usd"] += rec.get("cost_usd") or 0.0
        a["msg_count"] += 1
        lat = rec.get("latency_ms")
        if lat is not None:
            a["total_latency_ms"] += lat

    for a in agents.values():
        if a["msg_count"] > 0:
            a["avg_latency_ms"] = a["total_latency_ms"] / a["msg_count"]
        del a["total_latency_ms"]

    total_tokens_in = sum(a["tokens_in"] for a in agents.values())
    total_tokens_out = sum(a["tokens_out"] for a in agents.values())
    total_cost = sum(a["cost_usd"] for a in agents.values())
    total_msgs = sum(a["msg_count"] for a in agents.values())

    return {
        "agents": agents,
        "global": {
            "tokens_in": total_tokens_in,
            "tokens_out": total_tokens_out,
            "cost_usd": total_cost,
            "msg_count": total_msgs,
        },
    }
