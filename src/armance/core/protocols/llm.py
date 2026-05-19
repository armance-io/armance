"""LLM client abstraction, factory, and continuation handling.

LLMClient is an ABC. Concrete clients live in armance.providers.*.
get_client() resolves by provider name. complete_with_continuation()
implements the spec's truncation policy: on finish_reason == "length",
retry exactly once with the partial assistant turn appended plus a
"continue" user turn, then return the concatenated text. If the second
call also returns "length", the concatenated text is returned with
finish_reason still "length" so the caller can mark the report partial.
"""
from __future__ import annotations

import json
import logging
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal

from armance.config import Config, ProviderConfig

logger = logging.getLogger(__name__)

FinishReason = Literal["stop", "length", "error", "other"]


class BudgetExceeded(Exception):
    """Raised when cumulative spend would exceed the configured budget cap."""


@dataclass(slots=True)
class LLMResponse:
    text: str
    tokens_in: int
    tokens_out: int
    finish_reason: FinishReason
    cost_usd: float | None = None


class LLMClient(ABC):
    @abstractmethod
    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str,
        **params: Any,
    ) -> LLMResponse:
        ...

    @abstractmethod
    async def embed(
        self,
        text: str,
        model: str,
    ) -> list[float]:
        ...

    async def stream_complete(
        self,
        messages: list[dict[str, str]],
        model: str,
        on_token: Callable[[str], None],
        **params: Any,
    ) -> LLMResponse:
        """Default: fall back to non-streaming complete, then call on_token with full text.

        Concrete providers that support true streaming should override this method.
        """
        response = await self.complete(messages, model, **params)
        if response.text:
            on_token(response.text)
        return response


# --- Provider registry (filled by armance.providers on first import) -------
#
# The registry indirection keeps `core/` free of imports from upper layers.
# Concrete provider modules call `register_client` at import time. Callers
# of `get_client` import `armance.providers` lazily here (the package's
# __init__ runs the registrations); after the first call the registry is
# populated and no further upper-layer imports are needed.

ClientFactory = Callable[[ProviderConfig], "LLMClient"]
_CLIENT_REGISTRY: dict[str, ClientFactory] = {}


def register_client(provider_name: str, factory: ClientFactory) -> None:
    """Register a concrete LLMClient factory for `provider_name`.

    Provider modules in `armance.providers.*` are expected to call this at
    import time. Re-registration is allowed (last writer wins).
    """
    _CLIENT_REGISTRY[provider_name] = factory


def get_client(provider_name: str, config: Config) -> LLMClient:
    provider_cfg = config.provider(provider_name)
    if not _CLIENT_REGISTRY:
        # Trigger provider package import so it can register its clients.
        # This is the only acceptable "upper layer" reference and it is
        # localised: nothing in core imports a provider symbol directly.
        import importlib
        importlib.import_module("armance.providers")
    factory = _CLIENT_REGISTRY.get(provider_cfg.name)
    if factory is None:
        raise ValueError(f"unknown provider: {provider_cfg.name}")
    return factory(provider_cfg)


async def complete_with_continuation(
    client: LLMClient,
    messages: list[dict[str, str]],
    model: str,
    *,
    max_rounds: int = 10,
    **params: Any,
) -> LLMResponse:
    """Run client.complete; loop on finish_reason == "length" up to max_rounds.

    Pattern per spec:
      [system prompt] [user prompt] [assistant: fragment1+…+fragmentN-1] [user: "Continue."]

    Guards: stop if fragment is empty, <20 chars, or identical to previous.
    Fragments are joined with no separator; the LLM resumes mid-sentence.
    """
    fragments: list[str] = []
    tokens_in_total = 0
    tokens_out_total = 0
    cost_total: float | None = None
    current_messages = list(messages)

    for round_n in range(max_rounds):
        resp = await client.complete(current_messages, model, **params)
        fragments.append(resp.text)
        tokens_in_total += resp.tokens_in
        tokens_out_total += resp.tokens_out
        cost_total = _sum_optional(cost_total, resp.cost_usd)

        if resp.finish_reason not in {"length", "max_tokens"}:
            break

        # Loop guards
        fragment = resp.text
        if not fragment.strip() or len(fragment) < 20:
            logger.warning("continuation: fragment too short (%d chars) — stopping", len(fragment))
            break
        if len(fragments) >= 2 and fragments[-1] == fragments[-2]:
            logger.warning("continuation: identical fragment detected — stopping")
            break

        n_continued = len(fragments)
        logger.info("continuation round %d/%d — %d chars so far", n_continued, max_rounds, sum(len(f) for f in fragments))
        current_messages = list(messages) + [
            {"role": "assistant", "content": "".join(fragments)},
            {"role": "user", "content": "Continue."},
        ]

    text = "".join(fragments)
    # finish_reason of last fragment; "stop" if we exited naturally
    final_reason = resp.finish_reason  # type: ignore[possibly-undefined]
    if len(fragments) > 1:
        logger.info(
            "continued ×%d — total %d chars, finish_reason=%s",
            len(fragments) - 1, len(text), final_reason,
        )
    return LLMResponse(
        text=text,
        tokens_in=tokens_in_total,
        tokens_out=tokens_out_total,
        finish_reason=final_reason,
        cost_usd=cost_total,
    )


def _sum_optional(a: float | None, b: float | None) -> float | None:
    if a is None and b is None:
        return None
    return (a or 0.0) + (b or 0.0)


@dataclass(slots=True)
class LedgerEntry:
    agent: str
    tokens_in: int
    tokens_out: int
    cost_usd: float | None


@dataclass(slots=True)
class TokenLedger:
    """Per-session aggregate of LLM usage.

    Persisted to .armance/sessions/<id>/ledger.json. Each call appends an
    entry under the agent's key; snapshot() returns a per-agent +
    grand-total view suitable for the TUI.
    """

    entries: list[LedgerEntry] = field(default_factory=list)
    persist_path: Path | None = None
    budget_cap_usd: float | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def check_budget(self) -> None:
        """Raise BudgetExceeded if current cumulative cost meets or exceeds the cap."""
        if self.budget_cap_usd is None:
            return
        with self._lock:
            current = sum(e.cost_usd or 0.0 for e in self.entries)
        if current >= self.budget_cap_usd:
            raise BudgetExceeded(
                f"budget cap ${self.budget_cap_usd:.4f} reached (spent ${current:.4f})"
            )

    def record(
        self,
        agent_name: str,
        tokens_in: int,
        tokens_out: int,
        cost_usd: float | None = None,
    ) -> None:
        with self._lock:
            self.entries.append(
                LedgerEntry(
                    agent=agent_name,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    cost_usd=cost_usd,
                )
            )
            if self.persist_path is not None:
                self._flush_locked()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            per_agent: dict[str, dict[str, Any]] = {}
            for entry in self.entries:
                bucket = per_agent.setdefault(
                    entry.agent,
                    {"tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, "calls": 0},
                )
                bucket["tokens_in"] += entry.tokens_in
                bucket["tokens_out"] += entry.tokens_out
                bucket["cost_usd"] += entry.cost_usd or 0.0
                bucket["calls"] += 1

            total = {
                "tokens_in": sum(b["tokens_in"] for b in per_agent.values()),
                "tokens_out": sum(b["tokens_out"] for b in per_agent.values()),
                "cost_usd": sum(b["cost_usd"] for b in per_agent.values()),
                "calls": sum(b["calls"] for b in per_agent.values()),
            }
            return {"per_agent": per_agent, "total": total}

    def _flush_locked(self) -> None:
        assert self.persist_path is not None
        self.persist_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "entries": [
                {
                    "agent": e.agent,
                    "tokens_in": e.tokens_in,
                    "tokens_out": e.tokens_out,
                    "cost_usd": e.cost_usd,
                }
                for e in self.entries
            ],
            "snapshot_unsafe": None,
        }
        # snapshot inside same lock — caller already holds it
        per_agent: dict[str, dict[str, Any]] = {}
        for entry in self.entries:
            bucket = per_agent.setdefault(
                entry.agent,
                {"tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, "calls": 0},
            )
            bucket["tokens_in"] += entry.tokens_in
            bucket["tokens_out"] += entry.tokens_out
            bucket["cost_usd"] += entry.cost_usd or 0.0
            bucket["calls"] += 1
        payload["snapshot_unsafe"] = {
            "per_agent": per_agent,
            "total": {
                "tokens_in": sum(b["tokens_in"] for b in per_agent.values()),
                "tokens_out": sum(b["tokens_out"] for b in per_agent.values()),
                "cost_usd": sum(b["cost_usd"] for b in per_agent.values()),
                "calls": sum(b["calls"] for b in per_agent.values()),
            },
        }
        tmp = self.persist_path.with_suffix(self.persist_path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self.persist_path)


_GLOBAL_LEDGER = TokenLedger()


def get_ledger() -> TokenLedger:
    return _GLOBAL_LEDGER


def set_ledger(ledger: TokenLedger) -> None:
    global _GLOBAL_LEDGER
    _GLOBAL_LEDGER = ledger


async def call_with_ledger(
    client: LLMClient,
    agent_name: str,
    messages: list[dict[str, str]],
    model: str,
    *,
    ledger: TokenLedger | None = None,
    **params: Any,
) -> LLMResponse:
    """Run complete_with_continuation and append usage to the ledger.

    Raises BudgetExceeded before making the call if the ledger's cap is set
    and current cumulative spend already meets or exceeds it.
    """
    target = ledger if ledger is not None else _GLOBAL_LEDGER
    target.check_budget()
    response = await complete_with_continuation(client, messages, model, **params)
    target.record(agent_name, response.tokens_in, response.tokens_out, response.cost_usd)
    return response
