# Provider rate limit risk during background workflow runs

> Status: **known limitation, accepted for V2**.
> Surfaces with Phase 3 of [`features/workflow-live-pipeline.md`](../features/workflow-live-pipeline.md).

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

## Fix sketch (when we get there)

- New `service/rate_limit.py` with a per-provider `AsyncLimiter`
  (`aiolimiter` or hand-rolled token bucket) tuned from the provider
  catalogue's RPS / RPM hint when available.
- LLM client wrappers acquire the limiter before posting.
- Telemetry on the bus when a call waits > 200ms for the limiter, so
  the user sees that the system is throttling rather than hanging.

Out of scope until a user actually reports the symptom in normal use.
