# Web Epic C · The deliberation surface

> Status: **ready to implement after Epic A**.
> Part of [`web-layer-stories.md`](web-layer-stories.md).

## Goal

The chat surface where the firm metaphor becomes visible. NL-first, with
visible agent identity, a real form for checkpoints, and a transparent
recruitment view. Slash commands remain available for power users.

## User stories covered

- **C1** — Talk to the firm in plain language; each agent visually
  distinct.
- **C2** — A checkpoint renders as a native form.
- **C3** — Malik's recruited panel renders as cards with the axis of
  disagreement; approval is explicit.
- **C4** — `/switch`, `/model`, `/effort` equivalents as UI controls.
- **C5** — Mona's autonomous-mode hypotheses are listed as reviewable
  assumptions alongside the deliverable.

## Backend dependencies (all green or queued)

| Story | Dependency | Status |
|---|---|---|
| C1 | `dispatch_input` + per-tab `LoopContext` | ✅ (Epic A) |
| C2 | `WebCheckpointHandler` (kind = text / select / confirm) | ✅ (Epic A) |
| C3 | Malik's recruit YAML round-trip + agent file write | ✅ existing |
| C4 | `/model`, `/effort`, `/switch` slash commands | ✅ existing |
| C5 | Mona's hypothesis marker convention | ✅ existing (frontmatter rule in system-judge.md) |

## File / module layout

```
web/frontend/
  app/
    session/[id]/
      page.tsx          three-column session view
      chat/
        ChatStream.tsx  SSE consumer + message list
        ChatInput.tsx   NL input bar
        MessageBubble.tsx
      checkpoint/
        CheckpointDrawer.tsx  triggered by checkpoint_requested events
        TextField.tsx / SelectField.tsx / ConfirmField.tsx
      panel/
        PanelCards.tsx  C3 — recruited specialists with axis labels
        ApproveBar.tsx
      controls/
        AgentSwitcher.tsx
        ModelSwitcher.tsx
        EffortSwitcher.tsx
      hypotheses/
        HypothesisList.tsx  C5
```

## TDD task list

### Task C.1 — Chat stream consumer (frontend)
1. Frontend test (red — Playwright): on `/session/<sid>`, sending text
   *« Bonjour »* via the chat input results in an outgoing
   `POST /turn` request; the assistant reply appears in the transcript
   once the bus emits `turn_completed`.
2. Implement `ChatInput` → `POST /turn` and `ChatStream` → SSE
   consumer.

### Task C.2 — Agent identity in bubbles
1. Frontend test (red): a message from `system-context` renders with
   *« Armance »* + the portrait `portraits/armance.png`; from a
   specialist named `Aisha`, it renders with her name + a placeholder
   monogram.
2. Implement `MessageBubble` with an agent-to-portrait map and a
   monogram fallback.

### Task C.3 — Checkpoint drawer (text)
1. Frontend test (red): a `checkpoint_requested` SSE event with
   `kind: text` opens a drawer with a textarea; submit → `POST /checkpoint`
   with the value; the drawer closes; the agent reply appears.
2. Implement.

### Task C.4 — Checkpoint drawer (select)
1. Frontend test (red): `kind: select` with `options: [a, b, c]` opens
   a dropdown; submitting one option posts the chosen value.
2. Implement.

### Task C.5 — Checkpoint drawer (confirm)
1. Frontend test (red): `kind: confirm` with `prompt: "Run now?"` opens
   a Yes / No pair of buttons; Yes posts `"yes"`, No posts `"no"`,
   `Cancel` posts `is_abort: true`.
2. Implement.

### Task C.6 — Panel cards (C3)
1. Backend test (red): when Malik emits `[EXECUTE:/recruit]`, the bus
   receives an `agents_proposed` event with the parsed YAML structure
   (one entry per agent: name, persona, role, axis).
2. Implement an interceptor in `service/chat_handlers/malik.py` (or
   wherever the recruit YAML is parsed) that emits this event. (Tiny
   change in `src/armance/`, justified because Step 1 of Malik's
   protocol is the *« propose »* step where the panel is named but not
   yet written to disk. We expose that structure to the UI.)
3. Frontend test (red): an `agents_proposed` event renders a column of
   cards (name, persona label, axis chip); an explicit *Approve*
   button is the only way to send the user's approval back as a chat
   message.
4. Implement.

### Task C.7 — Model / effort / switch controls (C4)
1. Frontend test (red): the model dropdown lists models from
   `GET /sessions/{sid}/models` (new lightweight route returning the
   discovered catalogue via `providers.model_discovery`). Selecting
   one issues a `/model <provider>:<model>` slash call.
2. Backend test (red): `GET /models` returns the live catalogue from
   `discover_openrouter_models()` (cached for 60 s).
3. Implement both.

### Task C.8 — Hypothesis ledger (C5)
1. Backend test (red): `GET /sessions/{sid}/workflows/{name}/runs/{run_id}/hypotheses`
   returns a JSON list of every `**Hypothèse (Mona) :**` (or
   `**Hypothesis (Mona):**`) entry detected across the run's step
   outputs. Each entry: `{step_id, text, invalidator?}`.
2. Implement a small parser that walks `step-*.md` files in the run
   directory and extracts the entries.
3. Frontend test (red): the deliverable view shows a *« Hypothèses
   assumées »* sidebar listing every entry, visually marked as
   assumption.
4. Implement.

### Task C.9 — Coverage gate
1. Backend tests for C6 / C7 / C8 contribute to the same 85 % gate.

## Acceptance criteria (epic-level)

- [ ] A full Armance → Malik → Kim journey is completable in the
      browser without typing a slash command.
- [ ] Every `checkpoint.kind` (text / select / confirm) renders the
      appropriate native control and resumes the run on submit.
- [ ] Malik's panel proposal renders as cards with explicit *Approve*;
      no workflow starts before the user has approved a panel they can
      actually read.
- [ ] Mona's autonomous-mode hypotheses are visible as a distinct,
      reviewable list attached to the deliverable.
- [ ] Coverage ≥ 85 % on the new backend routes.

## Out of scope

- Edit / regenerate a past reply (V3).
- Multi-driver collaboration (Epic A scopes the read-along model).
- Voice input (V3).
