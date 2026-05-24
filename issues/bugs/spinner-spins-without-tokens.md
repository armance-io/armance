# Agent spinner spins even when no tokens are flowing

> Status: **known limitation, will land with Phase 2** of
> [`features/workflow-live-pipeline.md`](../features/workflow-live-pipeline.md).

## Symptom

Once the agent spinner ships (Phase 2 of the workflow live pipeline), the
spinner will turn on the moment `mark_step_started` writes to the
manifest, and turn off on `mark_step_completed`. Between those two
events, the agent may in fact be idle — waiting for the provider's TCP
handshake, the provider's queue, a cold start, a retry backoff. The
spinner suggests work is happening when nothing is happening on the
agent side.

## Cause

`mark_step_started` fires before the LLM call actually streams a token.
The wall-clock interval `started_at → first_token` can be several seconds
on free-tier OpenRouter or on a cold Claude-code subscription model.

## Fix

Plumb the existing `SpecialistRunner.on_token` callback (currently used
only for direct-message streaming) through to the sidebar via the event
bus. The sidebar spinner ticks while `on_token` is firing for a given
agent and freezes otherwise.

Concretely:

- `workflow_hooks` or the step adapter wires an `on_token` that emits
  an `agent_streaming` event on the bus with the agent name.
- The sidebar widget subscribes to the bus and toggles the spinner
  per-agent based on the last `agent_streaming` timestamp (active if
  < 1.5s ago).
- Once the step completes, `mark_step_completed` emits a
  `agent_streaming_end` event that forces the spinner off.

## Acceptance

- [ ] Spinner stays off during the `started_at → first_token` window.
- [ ] Spinner turns on with the first token and ticks as long as tokens
      keep arriving.
- [ ] Spinner turns off within ~2s of the last token / step end.
- [ ] Direct-message chats that already stream via `on_token` keep
      working unchanged.

## Workaround until then

The Phase 2 first cut uses `mark_step_started` / `mark_step_completed`
as the spinner gate. The UX is honest about what it knows (the step is
running) without claiming what it doesn't (the agent is actively
thinking).
