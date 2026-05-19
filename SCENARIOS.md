# Armance — V1 Test Scenarios (fil rouge)

> Manual scenarios to drive interactive convergence testing of V1.
> Each scenario = a starting state + an action sequence + observable
> expected outcomes. Pick freely — order doesn't matter unless noted.
> Report bugs through `BUG_FIXING_GUIDE.md`.

---

## S0 — Smoke install + run

**Goal:** Armance starts cleanly from scratch.

1. `rm -rf .armance/` (clean slate)
2. `armance init` (interactive) — pick openrouter, type a fake key, free-first.
3. `armance run` → TUI opens, no traceback, Armance greets in the chosen language.
4. Sidebar shows: 📚 inactive (no embed model picked), Staff section with 4 metas.

**Expect:** no Python crash; greeting under ~14 lines; cursor in the input bar.

---

## S1 — Oneliner non-interactive init

**Goal:** External cowork agent can install + configure in one shell line.

```bash
rm -rf .armance/ && armance init --yes \
  --provider openrouter \
  --api-key openrouter=$OPENROUTER_API_KEY \
  --default-provider openrouter \
  --default-model poolside/laguna-xs.2:free \
  --embedding-provider openrouter \
  --embedding-model nvidia/llama-nemotron-embed-vl-1b-v2:free \
  --budget free-first \
  --language fr
```

**Expect:** RC=0; one-line summary printed; `.armance/config.yaml` matches; `.env` contains `OPENROUTER_API_KEY=...`; no questionary prompts shown.

---

## S2 — Library ACTIVE: index then load a doc

**Pre:** S1 ran. Drop a real markdown into `.armance/docs/sample.md`.

1. `armance run`
2. Type "bonjour" → Armance greets, mentions `sample.md` is `⏳ pas encore indexé`.
3. Armance lists 4 options A/B/C/D.
4. Reply **C** ("les deux").
5. Observe: spinner switches to "Indexation des documents dans la bibliothèque…", finishes with "N feuillets total" + per-doc breakdown. Then doc is loaded (`📖 chargé`).
6. Sidebar 📚 Library badge flips to `✓ active openrouter/<model> | 1 doc · N feuillets`.
7. Type "que dit le doc ?" — Armance should reference content from the loaded doc.
8. `.armance/logs/llm_exchanges.jsonl` should now contain `event: request agent: embedding`.

**Expect:** dim probed (no hardcoded 1536 mismatch); ledger total includes embed cost; no UI freeze during ingest.

---

## S3 — Library INACTIVE: Armance refuses A/C

**Pre:** Edit `.armance/config.yaml`, set `embedding_provider: ""` and `embedding_model: ""`. Restart.

1. Drop a doc into `.armance/docs/`. `armance run`.
2. Armance should now list **only B and D** (no A, no C).
3. Append in the prompt: "indexe le quand même" → Armance politely explains the library is inactive and offers either to help activate it or fall back to B.
4. Type "comment activer la bibliothèque ?" — Armance should explain (drawing on `_armance_concepts.md`) that you need to set `embedding_provider`+`embedding_model` in `.armance/config.yaml`.

**Expect:** sidebar shows `✗ inactive — no embedding model`. Never proposes `[EXECUTE:/library-index]`.

---

## S4 — Malik recruits with provider mix

**Pre:** S2 state with multiple providers (add `claude-code` and/or `gemini` providers to config).

1. `armance run` → Armance frames a project (e.g. "I want to write a research brief on medieval trade routes for a blog post"). Save with `/save`.
2. Pick Malik when offered.
3. Malik proposes a panel. **Expect**: each agent line shows `<provider>/<model>` with a 🟢/🟡/🟠/🔴 marker. Different providers across the panel when more than one is configured.
4. Confirm with "ok". Malik emits `[EXECUTE:/recruit]` + YAML. Specialists created in `.armance/agents/`.

**Expect:** YAML output has `provider:` AND `model:` on every agent. No `reasoning:` field unless model is in REASONING_SUPPORT.

---

## S5 — Kim workflow design + run

**Pre:** S4 has at least 2 specialists + Serge.

1. Type "Kim, design moi un workflow pour ce projet".
2. Kim walks S0–S6. **Expect S2 step ids are project-specific** (not `analyse / synthesise` literally) — they should mention the medieval-trade-routes context.
3. Confirm. Workflow saved to `.armance/workflows/<name>.yaml`.
4. `/workflow run <name>` → cost preflight (NLS-rendered), confirm → run. Spinner ticks; step icons in sidebar.
5. After all steps: `## <step_id>` blocks for each step.

**Expect:** if your project triggers consensus heuristic (3+ judges with empty Divergence), an `auto_serge_critique` step is appended automatically.

---

## S6 — Deliverable rendering

**Pre:** S5 finished, `ctx._last_output` has content.

1. `/deliverable md test_out` → `.armance/exports/test_out.md` exists, > 0 bytes.
2. `/deliverable docx test_out` → `.armance/exports/test_out.docx`, valid ZIP, > 200 bytes.
3. `/deliverable pdf test_out` → `.armance/exports/test_out.pdf` (requires WeasyPrint installed).

---

## S7 — Library state separation

1. `/library status` → shows indexed + read sections separately.
2. `/library load <file>` (no `--persist`) → doc loaded for this session only. Restart → `read.json` empty.
3. `/library load <file> --persist` → restart, `read.json` keeps it. Specialists see it.
4. `/library unload <file>` → vanishes from read state but stays indexed.
5. `/library unindex <file>` → vanishes from RAG (manifest + sqlite-vec rows).

---

## S8 — Multi-doc per-doc choice

**Pre:** Drop 3 docs at once.

1. `armance run`. Armance lists all 3 with `⏳`.
2. Armance asks doc-by-doc. Reply `A`, then `B`, then `D` (one per doc).
3. Verify: first doc indexed only, second loaded only, third untouched.

---

## S9 — Language switch

1. `armance init --yes ... --language es` → re-run. Armance speaks Spanish.
2. Sidebar labels, /help, prompts all in Spanish (or English fallback if keys missing — log silently).
3. Specialists also reply in Spanish (voice overlay).

---

## S10 — Embedding model switch (dim change)

1. Index a doc with `nvidia/...:free` (2048d). Verify `vector/embedding_meta.json` shows `dim: 2048`.
2. Edit config to a different model (e.g. `openai/text-embedding-3-small` if available — 1536d).
3. `/library index` → silent rebuild: DB + manifest dropped, full re-index. Verify `embedding_meta.json` now `dim: 1536`.

**Expect:** no user-visible "dim mismatch" error. Transparent.

---

## S11 — Slash commands smoke

Try in one session: `/help` `/agents` `/role list` `/library status` `/model` `/effort` `/save` `/feedback-loop` `/iterate-from`. None should crash. Every reply should be NLS-rendered in the chosen language.

---

## S12 — Cross-family safety net

**Pre:** Config has ONLY openrouter (single family).

1. Run a workflow that contains a `critique` step (Serge).
2. **Expect:** the engine ABORTS pre-run with the cross-family error message, suggesting the user configure a second provider family. Workflow does not execute.

---

## S13 — Embed failure path

**Pre:** Set `OPENROUTER_API_KEY=invalid` in `.env`.

1. `/library index` → expect: `❌ indexation échouée` + clear error string (HTTP 401 etc).
2. Sidebar 📚 stays `✓ active` (config is right) but no docs are indexed.
3. **No process freeze**, no unkillable state, control returns to the prompt.

---

## S14 — Boot scan, no auto-ingest

1. Drop a doc. `armance run`. **Expect:** Armance lists it as `⏳ pas encore indexé`. NO automatic ingestion has happened. `vector/manifest.json` either absent or empty for this doc.

---

## S15 — TUI keys + quit

- Ctrl+S saves the session.
- Ctrl+K clears the chat.
- Double-Ctrl+C within 2s quits cleanly.
- Esc during a checkpoint aborts the workflow.

---

## S16 — Concepts self-explainer

Type:
- "comment ça marche Armance ?"
- "c'est quoi un feuillet ?"
- "pourquoi je n'ai pas de bibliothèque ?"
- "explique-moi les workflows"
- "quels providers sont supportés ?"

Armance should answer each accurately, vulgarising. Should never recite the `_armance_concepts.md` verbatim. Should adapt vocabulary to the user's apparent technical level.

---

## S17 — Edge: empty docs dir

1. `rm -rf .armance/docs/*` then `armance run` → Armance says "vous pouvez déposer PDF/MD/...", then asks about the project. No doc menu shown.

---

## S18 — Edge: very long doc load

1. Drop a 200KB markdown. `B` (load only).
2. Armance trims to 6000 chars per doc when injecting raw — no token explosion.

---

## S19 — Edge: special chars in filename

1. `mv doc.md "spëçìàl filé.md"` → drop it. `/library load "spëçìàl filé.md"` → works.

---

## S20 — Convergence run: full happy path

End-to-end in one session, no restart:

1. `armance init --yes ...` (S1)
2. drop doc → `armance run`
3. Armance greets, A/B/C/D menu → C for the doc
4. Project description → Armance summarises → `/save`
5. → Malik → recruit panel mix-providers
6. → Kim → design workflow → run
7. → `/deliverable md result`
8. `/quit` clean

This is the canonical demo. Time + tokens + cost should appear in the ledger total.

---

---

## S21 — Resume session prompt

1. End session (Ctrl+C×2). `armance run` again.
2. **Expect**: pre-TUI line "Previous session found: <id> · N turns · ~M tokens · last update <ts>" + "Resume? [Y/n]".
3. Y → session reloaded, conversation visible in chat. N → fresh session.
4. `ARMANCE_NO_RESUME=1 armance run` → no prompt, fresh session.

## S22 — Ctrl+C×2 save modal

1. Type a few project messages with Armance. Ctrl+C twice.
2. **Expect** confirm "Save the session context before quitting?" Y/N.
3. Y → `.armance/context/L0/v<NNN>_*_quit-quick-save.md` created. Quit.
4. N → quit without save. Restart, no new L0.
5. Empty buffer → Ctrl+C×2 quits silently (no modal).

## S23 — Kim 4-phase workflow protocol

1. `@Kim` → "j'ai besoin d'un workflow".
2. **Phase 1**: Kim asks "quel objectif souhaitez-vous atteindre ?". Stops. No shape/role yet.
3. Reply with goal.
4. **Phase 2**: Kim proposes ONE shape + roles + mapping to existing roster + per-role I/O + aggregation. If no agent fits a role: `@Malik, peux-tu recruter <role> ?` + stop.
5. Reply "ok" → **Phase 3**: `[EXECUTE:/workflow-design]` fires; DesignWorkflowSkill dialogue takes over.
6. Once saved → **Phase 4**: Kim points at Mona for synthesis after run.

## S24 — Sandbox: specialist cannot trigger tags

1. Recruit a specialist (e.g. Aria architect).
2. `@Aria` → "recrute-moi 3 développeurs".
3. **Expect**: Aria refuses (or her reply doesn't fire `[EXECUTE:/recruit]` thanks to the sandbox scrub). Specialist replies should mention `@Malik` instead.
4. Check `.armance/logs/llm_exchanges.jsonl`: if specialist emitted a forbidden tag, warning `stripped 1 unauthorised [EXECUTE:/...] tag(s) from specialist reply: ['recruit']` is logged.

## S25 — Mona /save-deliverable + /load-run

**Pre**: at least one workflow run exists.

1. `@Mona` → "synthétise les résultats du dernier run".
2. Mona produces a synthesis.
3. "OK garde-la dans la bibliothèque" → Mona emits `[EXECUTE:/save-deliverable:my-synth]`.
4. **Expect**: `.armance/docs/mona-my-synth-<ts>.md` written.
5. "Indexe-la" → user @Armance + /library index. Now searchable.
6. Run the same workflow a second time.
7. `/workflow compare <name> <run-1> <run-2>` → active agent switches to Mona, both runs queued in his context.
8. "compare-les" → Mona diffs in prose (consensus shifts, positions adopted/dropped).

## S26 — Versioned exports tree

1. Run workflow `architecture-technique` twice.
2. `.armance/exports/architecture-technique/run-<ts1>/` and `run-<ts2>/` both exist with `step-*.md`, `synthesis.md`, `manifest.json`.
3. `.armance/exports/architecture-technique/runs.json` lists both, oldest first.
4. Never overwrites: re-run does NOT touch the previous dir.
5. `/workflow list architecture-technique` shows both.

## S27 — Cross-family is a warning, never aborts

1. `.armance/config.yaml` with single provider (openrouter).
2. Kim creates a workflow with a `critique` step (Serge).
3. Run workflow.
4. **Expect**: warning surfaced in chat: `[cross_family_warning] ⚠️ Pression adversarial limitée ...`, run continues all the way through. Never aborts.

## S28 — Malik single-agent update YAML scope

1. Malik recruits 4 agents.
2. "Serge passe sur nemotron 120b".
3. Malik proposes the swap, user ok.
4. **Expect** Malik's YAML contains ONLY `Serge` (not the 4 agents). Existing Alex / Sam / Ravi files untouched.
5. Sidebar refreshes — Serge model line shows the new model.

## S29 — Specialist sees content history

1. Recruit Aria + Leo (both architects).
2. `@Aria` → asks question, gets answer A.
3. `@Leo` → asks "que penses-tu de la proposition d'Aria ?".
4. **Expect**: Leo references Aria's answer A in his reply. Specialist history broadened to include peer content.

## S30 — Staff agents must NOT propose solutions

1. `@Armance` → "quelle architecture pour mon SaaS ?".
2. **Expect**: Armance refuses + redirects to Kim/specialists. No stack proposal, no tables, no roadmap.
3. Same with `@Malik`, `@Kim` → both refuse. Only `@Mona` engages with project content.

---

## Reporting bugs

For each scenario that fails, capture:

- Scenario id (S0–S20).
- Step that broke.
- Exact reply text shown.
- Relevant lines from `.armance/logs/llm_exchanges.jsonl`.
- Sidebar state (active/inactive + counts).
- Then hand off to a fixing agent via `BUG_FIXING_GUIDE.md`.
