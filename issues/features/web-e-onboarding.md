# Web Epic E · Onboarding in the browser

> Status: **E1 ready, E2 depends on
> [`auto-embed-discovery.md`](auto-embed-discovery.md)**.
> Part of [`web-layer-stories.md`](web-layer-stories.md).

## Goal

`armance init` today is a terminal flow. Claire — the non-technical
persona — never gets there. Onboarding moves into the browser: a fresh
project is configured in three questions (provider, default model,
budget), and Armance proposes an embedding model the first time the
user drops a document.

## User stories covered

- **E1** — First-run setup in the browser (3 questions, no terminal).
- **E2** — Embedding proposal in the browser when the user adds their
  first document.
- **E3** — Empty-state teaches what Armance is for.

## Backend dependencies

| Story | Dependency | Status |
|---|---|---|
| E1 | `armance.config.load_config` + write `.armance/config.yaml` | ✅ |
| E1 | Provider catalogue (`armance.providers.model_discovery`) | ✅ |
| E2 | `infer_embedding_shape` + `propose_embedding_model` | ⏳ ships with [`auto-embed-discovery.md`](auto-embed-discovery.md) |
| E2 | `[EXECUTE:/library-configure-embedding:<provider>:<model>]` tag | ⏳ ships with [`auto-embed-discovery.md`](auto-embed-discovery.md) |
| E3 | None — pure frontend | ✅ |

## File / module layout

```
web/backend/routes/
  setup.py             GET /setup/status
                       POST /setup/init   {provider, model, budget, language}
  models.py            GET /providers     live catalogue per configured provider

web/frontend/app/
  setup/
    page.tsx           three-step wizard
    ProviderStep.tsx
    ModelStep.tsx
    BudgetStep.tsx
  session/[id]/
    EmptyState.tsx     E3 — what Armance is for, first moves
```

## TDD task list

### Task E.1 — `GET /setup/status`
1. Backend test (red): on a fresh directory with no `.armance/config.yaml`,
   returns 200 `{"configured": false, "missing": ["provider", "model"]}`.
2. Backend test (red): on a configured directory, returns
   `{"configured": true}`.
3. Implement: read `config.yaml` if present; report which mandatory
   fields are empty.

### Task E.2 — `GET /providers`
1. Backend test (red): with `OPENROUTER_API_KEY` set, returns a JSON
   list of providers, each with a `name`, `models` list (id, tier),
   and `embedding_models` list (id, shape).
2. Backend test (red): with no key set, returns an empty list and a
   `hint: "set OPENROUTER_API_KEY in .armance/.env"`.
3. Implement: delegate to `model_discovery.discover_all(cfg)`.

### Task E.3 — `POST /setup/init`
1. Backend test (red): valid body
   `{"provider": "openrouter", "model": "openai/gpt-4o-mini",
   "budget": "medium", "language": "fr"}` writes
   `.armance/config.yaml` with the matching fields and returns 201.
2. Backend test (red): invalid budget enum → 422.
3. Backend test (red): provider not in the discovered catalogue → 400
   `{"error": "unknown_provider"}`.
4. Implement.

### Task E.4 — Frontend wizard (E1)
1. Frontend test (red — Playwright): on a fresh directory the user
   lands on `/setup`, sees three steps, picks one option per step, and
   submits. The resulting `GET /sessions` is then offered.
2. Implement `ProviderStep` (radio over the `/providers` response),
   `ModelStep` (filtered by the picked provider), `BudgetStep` (radio
   over `free-first / low / medium / high`).

### Task E.5 — Empty state (E3)
1. Frontend test (red): on first `/session/<sid>` with an empty chat
   transcript, the chat area shows two suggestions: *« décrivez une
   décision que vous pesez »* and *« déposez un document que vous
   voulez examiner »*. Each is a clickable prompt that pre-fills the
   chat input.
2. Implement `EmptyState`.

### Task E.6 — Embedding proposal flow (E2, gated)
1. Gated on the merge of
   [`auto-embed-discovery.md`](auto-embed-discovery.md). When that ships,
   the proposal arrives as a checkpoint of `kind: confirm` with the
   proposed model in the prompt; the existing C2 / C5 drawer already
   handles it.
2. Frontend test (red): with a stubbed checkpoint, the drawer renders
   the model proposal; confirming sends back `"yes"` and the
   `[EXECUTE:/library-configure-embedding:<provider>:<model>]` tag is
   intercepted by the backend.
3. Implement nothing new on the web side — the existing checkpoint
   drawer is enough. The test exists to assert the end-to-end flow.

## Acceptance criteria (epic-level)

- [ ] A fresh project is fully configured from the browser; the
      resulting `config.yaml` is byte-identical to what the CLI would
      have written.
- [ ] Dropping a file in the browser triggers Armance's embedding
      proposal as a checkpoint (after `auto-embed-discovery` lands).
- [ ] No dead-end blank screen on first open.
- [ ] Coverage ≥ 85 % on the new backend routes.

## Out of scope

- API-key management UI (V3 may add it; V2 still expects the user to
  edit `.armance/.env` by hand or via documentation).
- Reset / delete project from the UI (V3).
