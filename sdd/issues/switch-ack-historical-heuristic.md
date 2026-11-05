# `MessageBubble` still uses a multilingual heuristic for replayed switch acks

> Status: **known, accepted for now**. Carved out of the closed
> `web-v2-ui-batch-2026-05-31` batch (BUG residual).
> Verified still open on `feat/environmental-impact` (2026-06-04).

## Symptom

`web/frontend/src/components/chat/MessageBubble.tsx` detects
agent-switch acknowledgement lines ("OK — basculé sur …", "OK — switched
to …") via a hard-coded keyword list (`basculé sur`, `switched to`, …)
to suppress them from the transcript. This is a multilingual string
heuristic — it violates the "no language heuristics" web rule and only
covers the languages someone thought to list.

## Cause

The **live** switch-ack case is handled cleanly (a ref flag set at switch
time, no string matching). But acks **replayed from stored history** carry
no such flag, so the component falls back to matching their text. Fixing
the historical case needs a stored marker on the message itself — a
storage-format change, which is why it was deferred.

## Fix sketch

| File | Action |
|---|---|
| message storage / event schema | persist a `kind: "switch-ack"` (or boolean) flag on the message at creation |
| `MessageBubble.tsx` | suppress on the stored flag; delete the keyword list |

## Acceptance

- [ ] No language-keyword list in `MessageBubble.tsx`.
- [ ] Replayed historical switch acks are suppressed via the stored flag,
      in any language.

## Out of scope

The live switch-ack suppression (already correct).
