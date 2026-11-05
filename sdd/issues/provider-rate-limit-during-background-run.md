# Provider rate limit risk during background workflow runs

> Status: **MITIGATED (2026-06-10)** — semaphore + 429-aware backoff
> shipped on `feat/grandma-launcher`. Not fully solved (no token-bucket),
> but the critical path is guarded.
> Surfaces with Phase 3 of [`features/workflow-live-pipeline.md`](workflow-live-pipeline.md).

## Symptom

Once workflow runs go background (Phase 3), the user can chat with
free meta-agents and idle specialists while the workflow drives several
specialists in parallel. All of these calls may hit the **same
provider** (e.g. OpenRouter free tier) and trigger HTTP 429
rate-limit responses.

The agent that gets 429'd surfaces a generic error to the user, and a
workflow step may fail mid-run.

## Cause

V2 has no provider-side rate-limit governor. Each `LLMClient.complete`
call goes out independently. Concurrency was previously bounded by the
TUI itself blocking on the run — background mode removes that natural
limit.

## Why we accept it for V2

- Single-user, single-machine product. Volume stays low.
- Free-tier limits are the only realistic offender; paid tiers handle
  parallelism comfortably.
- A correct fix (token-bucket per provider, per-model retry-with-backoff,
  cross-call coordination) is a project of its own and would block the
  Phase 3 ship for marginal benefit at this volume.

## Mitigations already in place

- Each `LLMClient` already retries `429` once with a short backoff
  (`providers/openrouter.py`, `providers/gemini.py`).
- Workflow steps that fail propagate `_run_aborted`, so downstream
  steps don't burn more tokens needlessly.

## Mitigations shipped (2026-06-10)

**`service/rate_limit.py`** — new module:
- `provider_semaphore(provider)` → `asyncio.Semaphore(2)` per provider
  (global registry, created once)
- `is_rate_limit(exc)` → checks `status_code == 429`
- `backoff_for(exc, attempt, base_backoff)` → respects `Retry-After`
  header with a floor of 10s × attempt

**Provider error classes extended:**
- `LLMHTTPError` (openrouter) and `GeminiHTTPError` now carry `status_code`
  and `retry_after` attributes
- `_retry_after_seconds(response)` helper in both providers

**`service/llm_service.py`** — `call_with_ledger` now:
```python
async with provider_semaphore(provider):
    response = await client.stream_complete(...)
# on 429: wait_s = backoff_for(exc, attempt, backoff)
```

## Remaining

No token-bucket (RPM/RPS per model). Still no telemetry event on
semaphore wait. Good enough for single-user single-machine V2.

## Fix sketch (if demand grows)

- Replace `Semaphore(2)` with `aiolimiter.AsyncLimiter` tuned from
  provider catalogue's RPS/RPM hints.
- Emit `rate_limit_wait` telemetry event so the live panel shows a
  spinner instead of silence.
