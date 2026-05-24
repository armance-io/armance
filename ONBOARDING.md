# Armance — Engineering Onboarding

> Audience: senior engineers joining the codebase. **Read this once**, then keep
> [`roadmap/02_architecture.md`](roadmap/02_architecture.md) and
> [`CLAUDE.md`](CLAUDE.md) bookmarked for day-to-day reference.
>
> **Looking for something to work on?** Every open user story and known
> bug is indexed in [`ISSUES.md`](ISSUES.md). Each entry has its own
> self-contained file under `issues/features/` or `issues/bugs/` with
> symptom, cause, fix sketch and acceptance criteria.

---

## 1. What this is, in one paragraph

Armance is a single-binary Python CLI that runs a **small staff of LLM agents**
who argue, stress-test, and synthesise over the user's own documents.
The product is a Textual TUI; everything else (config, agents, conversations,
RAG library, reports) lives under `.armance/` as plain Markdown / YAML / SQLite.
There is **no service to deploy and no central database** — Armance runs from a
single repo on the user's machine.

The four permanent agents are:

| First name | Role | Built-in file |
|---|---|---|
| **Armance** | Host. Frames the project, gates routing. | `system-context.md` |
| **Malik** | Recruiter. Creates specialist agents. | `system-hr.md` |
| **Kim** | Operator. Designs and runs workflows. | `system-orchestrator.md` |
| **Mona** | Vice-president. Judges and challenges synthesis. | `system-judge.md` |

Plus **Serge** (`system-challenger.md`), an adversarial criticalist Malik must
recruit on every plan. Specialists Malik hires are project-specific.

---

## 2. 90-second tour of the code

### 2.1 Layering (hard rule)

```
client      → transport → service → core
(Textual TUI)  (DTOs)      (orchestration)  (pure models + protocols)
```

Lower layers know nothing of upper layers. Enforced by
`scripts/check_invariants.sh` in CI. If you need to break this rule, you are
doing something wrong — open an issue first.

### 2.2 Module map (`src/armance/`)

```
cli.py              Entrypoints: init / run / index / doctor / workflow
config.py           Config + ProviderConfig + ensure_armance_tree
core/
  models/             Agent, Task, Workflow, Context (L0/L1/L2), Claim,
                      Conversation, Turn, Tokens
  protocols/          LLM + Notifier ABCs
providers/
  openrouter.py       OpenAI-compatible httpx client (reasoning support)
  claude_code.py      claude-agent-sdk adapter
  gemini.py           Google REST client
  custom_openai.py    BYO OpenAI-compatible endpoint
  model_discovery.py  Live OpenRouter tier catalogue + curated subscription
                      catalogues (claude-code, gemini) + REASONING_SUPPORT
service/
  handlers.py         Slash-command dispatch + chat routing
  workflow_hooks.py   Cross-family validation + Serge consensus auto-invoke
                      (called by core.execute_workflow pre/post hooks)
  skills/             design_workflow, feedback_loop, iterate_from, set_l*
  agents/
    host_agent.py       Armance (and reused for Kim + Malik chat shells)
    recruiter_agent.py  Malik (multi-provider recruitment, persona validation)
    judge_agent.py      Mona
    challenger_agent.py Serge
    specialist_runner.py Per-specialist run (L0+L1+L2+RAG+read-doc inject)
    _rag_inject.py      Meta-agent RAG injection helper
    _voice_overlay.py   Language overlay appended to every system prompt
  context_service.py  L0/L1/L2 read+write, manifest, RAG enrichment
  cost.py             Pre-flight workflow cost estimation
  session.py          Session state, ledger, conversation persistence
  llm_service.py      LLMClient factory + TokenLedger + length continuation
  checkpoint.py       Human-in-the-loop checkpoint contract
storage/
  rag_index.py        RagService (sqlite-vec) + context_with_rag helper
  ingestion.py        sync_docs (md/pdf/docx/txt → chunks, embeds)
  library_state.py    'read' set tracking (session + persistent)
  rag_status.py       Library status report (indexed/orphans/chunks)
  paths.py            Canonical .armance/ file paths
  filesystem.py       Atomic writes, lockfiles
transport/
  dto.py              Public DTOs (Conversation, Workflow, Step, Event)
  events.py / local.py In-process event bus
client/
  tui/                Textual app — chat, sidebar, claims, workflow view
nls_catalogues/
  en.yaml / fr.yaml   Translation catalogues (single source of truth for
                      all user-facing strings outside agent prompts)
protocols/            Caveman protocol prompts (ultra/lite/full)
templates/            WeasyPrint stylesheet
```

### 2.3 The big files you'll touch first

| File | LOC | Why it's big | Plan |
|---|---|---|---|
| `service/agents/host_agent.py` | ~1080 | Armance dialogue + intent detection + state | Extract intent/state helpers when you touch it |
| `service/agents/recruiter_agent.py` | ~930 | Malik recruitment + persona validation | Split queued |
| `cli.py` | ~880 | Entry points (init/run/index/doctor/workflow) | Split into `cli/*.py` per command — queued |
| `service/handlers.py` | ~750 | Slash-command dispatcher + workflow run orchestration | Library/save/role/task/mona ops already extracted; chat shells next |
| `service/agents/host_agent.py` | ~990 | Armance dialogue + intent detection + state | Extract intent/state helpers when you touch it |

Other modules respect the ~300-line target.

---

## 3. The data on disk (`.armance/`)

Everything Armance persists is plain text. **Markdown is the source of truth.**

```
docs/                user-dropped documents (PDF, DOCX, MD, TXT)
agents/
  system-*.md          five built-in staff agents (Armance/Malik/Kim/Mona/Serge)
  <Name>.md            Malik-recruited specialists
  builtin/             seed copies (read-only)
workflows/           *.yaml DAGs (user-created via Kim; no default ships)
exports/<workflow>/  versioned runs — run-<YYYYMMDD-HHMMSS>/{step-*.md,
                     synthesis.md, trace.md, manifest.json}
                     + workflow-level runs.json index
context/             L0_v<N>.md / L1_<role>_v<N>.md / L2_<theme>_v<N>.md
                     + manifest.json
reports/             <agent>_v<N>.md per workflow step
sessions/<id>/       state.json, ledger.json, conversation.md
vector/              sqlite-vec index + manifest.json (indexed docs) +
                     read.json (persistently loaded docs)
exports/             generated deliverables (.pptx / .docx / .pdf / .md)
config.yaml          non-secret config
.env                 provider API keys (gitignored)
```

Side rule: **never write to a .armance/ directory you didn't create or update via
an existing storage/* helper**. The shape is part of the public contract with
the user.

---

## 4. How a turn flows (the path you will debug most often)

For the canonical class/module map + NL→tool sequence diagrams + the
exhaustive tag table, see
[`roadmap/02_architecture.md`](roadmap/02_architecture.md#core-architecture-frozen--class--module-map).
Quick textual walk:

```
User types in TUI input bar
    │
    ▼
client/tui/screens/main.py
    │  _handle_input(text)
    ▼
service/tui_bridge.dispatch_input(text, ctx)
    │  - if slash → service/handlers.HANDLERS[name]
    │  - if NL switch ("@Malik, …") → resolve_meta_agent + recurse
    │  - else → _cmd_chat
    ▼
service/handlers._cmd_chat
    │  routes to one of:
    │    _cmd_context_chat        (Armance)
    │    _cmd_hr_chat             (Malik)
    │    _cmd_orchestrator_chat   (Kim)
    │    streaming specialist chat (Malik-recruited agents)
    ▼
service/agents/<host|recruiter|operator>_agent.py
    │  builds system prompt (caveman + role + voice overlay + docs section
    │  + project brief + team roster + RAG injection + loaded-doc raw)
    │  calls service/llm_service.call_with_ledger
    ▼
LLM reply → intercept [EXECUTE:/...] tags → side effects
```

### Side effects are always tag-driven

Agents trigger side effects by emitting `[EXECUTE:/<command>]` in their reply.
The intercept layer (in `host_agent.dialogue` and `handlers._cmd_*_chat`)
removes the tag and runs the corresponding Python. Tags in production:

| Tag | Effect |
|---|---|
| `[EXECUTE:/save]` | Freeze the project brief to `context/L0_v<N>.md` |
| `[EXECUTE:/recruit]` | Malik creates specialists from the YAML she appended |
| `[EXECUTE:/dismiss-all]` | Wipe all specialist agents |
| `[EXECUTE:/workflow-design]` | Kim hands off to the design dialogue |
| `[EXECUTE:/workflow-run:<name>]` | Run a workflow |
| `[EXECUTE:/library-index]` | Run `sync_docs` (chunk + embed all new/changed docs) |
| `[EXECUTE:/library-load:<file>]` | Mark a doc "read" — full text injected into every agent's context |
| `[EXECUTE:/library-unload:<file>]` | Drop from the read set |
| `[EXECUTE:/library-unindex:<file>]` | Drop from the searchable library |
| `[EXECUTE:/library-status]` | Inject a factual library status report |

Legacy tags (`/load:X`, `/forget:X`, `/ingest-docs`, `/rag-status`) are still
aliased to the new `/library-*` ones until the migration window closes. **Do
not introduce a new side-effect path that is not tag-triggered.**

---

## 5. Library = two distinct states

This trips up everyone the first time:

- **Indexed** = the doc has been chunked into "slips" (`feuillets` in the FR
  UI) and embedded into `vector/sqlite-vec.db`. The team can retrieve passages
  by semantic search, but **no agent has read the doc**.
- **Read / loaded** = the doc's full text is injected into every agent's system
  prompt for this session. Persistent read (`vector/read.json`) survives
  restarts; session read is per-session only.

User-facing vocabulary (English):
- *library* (not "database", "RAG", "embeddings")
- *slip* / *index* / *indexed* (not "chunk", "embed")
- *load* / *read* (not "inject", "force-load")

Same applies in French (*bibliothèque*, *feuillet*, *indexer*, *charger*).
The translation source of truth is `src/armance/nls_catalogues/{en,fr}.yaml`.

---

## 6. Providers and the multi-provider recruitment story

Armance talks to four provider types:

| Provider | Auth | Reasoning effort | Notes |
|---|---|---|---|
| `openrouter` | `OPENROUTER_API_KEY` | Yes (OpenAI-style `reasoning` field) | Many free `:free` models |
| `claude-code` | `claude-agent-sdk` SDK auth | No | Subscription; family-tiered cost proxy |
| `gemini` | `GEMINI_API_KEY` | No | Free tier on flash-lite |
| `custom-openai` | `CUSTOM_OPENAI_API_KEY` + `CUSTOM_OPENAI_BASE_URL` | Model-dependent | Any OpenAI-compatible endpoint |

Each agent is **fully specified by a `(provider, model, reasoning?)` triplet**
in its Markdown frontmatter. Malik is encouraged to mix providers across an
agent panel — e.g. a Claude Opus on the synthesiser, an OpenRouter free model
on the critic, a Gemini Flash on a fast brainstormer.

Reasoning effort (`reasoning: low|medium|high`) is gated by
`providers/model_discovery.REASONING_SUPPORT`. Only OpenRouter `openai/o1`,
`openai/o3`, and `deepseek/r1` families support it today. Malik **must not**
propose `reasoning:` on a pair that is not in this set.

---

## 7. RAG path (when you debug retrieval issues)

```
.armance/docs/<file> (PDF/DOCX/MD/TXT)
    │
    │  /library index  or  [EXECUTE:/library-index]
    ▼
storage/ingestion.sync_docs(armance_root, config)
    │  - chunk text (tiktoken cl100k_base, 512 tok max, 64 tok overlap)
    │  - embed via cfg.embedding_provider / cfg.embedding_model
    │  - upsert into sqlite-vec
    │  - write vector/manifest.json (sha → seen)
    ▼
At query time:
service/agents/_rag_inject.inject_rag_section
    │  - top-k retrieval on the user's last turn
    │  - returns a "## Retrieved from .armance/docs/" section
    ▼
Appended to the agent system prompt
```

**Boot does NOT auto-ingest.** Earlier versions did and silently fell back to
zero-vector ingestion when no embedding client was configured, which polluted
the manifest and made Armance hallucinate "already indexed" docs. Ingestion
is now strictly user-consented through Armance's `[EXECUTE:/library-index]`
tag or the `/library index` slash command.

If `cfg.embedding_provider` is set but the client fails to initialise,
`sync_docs` returns `{"error": "embed_init_failed"}` and Armance surfaces a
clear error — no silent fallback.

---

## 8. Workflows

One engine: `core.models.workflow.execute_workflow`. Loads YAML from
`.armance/workflows/*.yaml`, runs steps in topological levels via
`asyncio.gather`. Supports `human_checkpoint` steps that pause via
`ctx.checkpoint_handler`. Safety nets (cross-family **soft warning** +
Serge consensus auto-invoke) plug in through the optional `pre_run_hook` /
`post_run_hook` callables — implementations live in
`service.workflow_hooks`. The rich `WorkflowEngine` was deleted as
dead code in the 2026-05-16 cycle (zero non-test consumers).

Kim walks a **strict 4-phase protocol** when designing a workflow:
1. Goal question only. 2. Shape (🟢/🟡/🔴) + roles + mapping to existing
roster + per-role I/O + aggregation. 3. On confirm, emit
`[EXECUTE:/workflow-design]` → `DesignWorkflowSkill` (S0→S6 dialogue).
4. Run → Mona handoff for synthesis.

Every `/workflow run` mints a versioned dir in
`.armance/exports/<workflow>/run-<YYYYMMDD-HHMMSS>/` with `step-*.md`,
`synthesis.md`, `manifest.json`. **Never overwritten.** Index in
`<workflow>/runs.json`. Tools: `/workflow list <name>` to list,
`/workflow compare <name> <r1> <r2>` to queue both into Mona's context
and switch to him for the diff.

---

## 9. Per-role agent sandbox

`service/agent_sandbox.py` is the single source of truth for what each
agent role can do. `_ROLE_TAG_ALLOWLIST` maps each role to its allowed
`[EXECUTE:/...]` tags. `scrub_reply(reply, agent_role=...)` runs three
defense layers on every LLM reply:

1. `strip_hallucinated_tool_calls()` — drops `<tool_call>...</tool_call>`.
2. `truncate_repeated_garbage()` — cuts 4+ consecutive 30-char repeats.
3. `strip_unauthorised_execute_tags()` — drops tags outside the role's list.

The boundary that matters most: **only Mona engages with project
content**. Armance frames, Malik recruits, Kim orchestrates. Their
prompts explicitly refuse to propose stacks / roadmaps / answers.
Specialists also produce content (workflow steps) but have only
`/load-run` as a tool.

---

## 10. The five rules to keep CI green

1. **`from __future__ import annotations`** at the top of every module.
2. **No `print` for debug.** Use `logging`.
3. **No imports from upper layers** in `core/` or `service/`. Lint:
   `scripts/check_invariants.sh`.
4. **Files ≤ ~300 lines.** `handlers.py` is the open exception (split
   queued).
5. **Tests use `pytest` + `pytest-asyncio` + `respx` (httpx) + `monkeypatch`.
   No real network.** The CI matrix runs Python 3.11 and 3.12.

```bash
uv run pytest tests/ -q                  # offline suite (~900 tests, <15 s)
uv run python scripts/qa_live.py         # live OpenRouter free-model journey
uv run ruff check src/                   # lint
bash scripts/check_invariants.sh         # layer + legacy hygiene
```

---

## 11. Things that will surprise you

- **`.armance/agents/*.md` is the agent.** The frontmatter is the contract;
  the body is the system prompt. Malik writes these files; the rest of the
  service just loads them.
- **Side effects are LLM-triggered, not Python-triggered.** If you see a
  tempting "I'll just call this directly", stop — add an `[EXECUTE:/...]`
  tag and an intercept.
- **`ctx.session.metadata` is the catch-all session bag.** It survives
  TUI restarts (persisted in `sessions/<id>/state.json`). Host agent state
  flows through it via `set_state` / `get_state` — keep mutations in the
  agent service, not in handlers.
- **NLS keys live in two YAMLs.** Every user-facing string MUST resolve
  through `armance.nls.t("<key>")`. Logs and internal exceptions stay in
  English — the catalogues are user-facing only.
- **Caveman protocols** (`protocols/caveman_{ultra,lite,full}.txt`) are
  applied per agent by `Agent.effective_system_prompt(caveman_level=...)`.
  Worker specialists get `ultra`; user-facing meta agents get `none` or
  `lite`. The caller decides.

---

## 12. Where to look first when…

| Symptom | Start here |
|---|---|
| TUI doesn't render | `client/tui/screens/main.py` + `widgets/` |
| Slash command misbehaving | `service/handlers.py` (search `_cmd_<name>`) + `service/tui_bridge.py` |
| Wrong agent answers | `service/agents/<role>_agent.py` + that agent's `.md` |
| RAG returns nothing | `storage/ingestion.py` (indexing) + `storage/rag_index.py` (query) + `service/agents/_rag_inject.py` |
| Wrong vocabulary in UI | `nls_catalogues/{en,fr}.yaml` |
| Provider auth failure | `providers/<name>.py` + `cli.py` doctor command |
| Cost estimate off | `service/cost.py` + `providers/model_discovery.py` |
| Workflow execution stuck | `core/models/workflow.py::execute_workflow` (single engine) + `service/workflow_hooks.py` (cross-family + Serge consensus hooks) |

---

## 13. Macro roadmap

See [`roadmap/04_roadmap.md`](roadmap/04_roadmap.md) for the phase-level
plan. See [`ISSUES.md`](ISSUES.md) for the per-issue breakdown — each
roadmap phase that has a detailed spec links there.

Current priorities (high level):

- **P1.1** Unify the two workflow engines.
- **P1.2** Split `service/handlers.py` (~750 LOC) — library/save/role/task/mona
  ops already extracted; the workflow-run orchestrator and chat-shell
  dispatch remain.
- **P2** Web client (FastAPI + Next.js bridge to the same service layer)
  — start at [`issues/features/web-layer-stories.md`](issues/features/web-layer-stories.md)
  for the overview, then pick one of the six epic files (A spine, B viewer,
  C deliberation, D pipeline, E onboarding, F finish) — each carries its
  own TDD task list and acceptance criteria.
- **P3** Plugin system for custom agent skills.

The architecture has already been validated to handle a web layer without
changes to `core/` and `service/` — that's why the transport DTOs exist.

---

## 14. Glossary

- **Slip / feuillet** — one chunk in the RAG index after a doc is split.
- **Indexed** — present in the library index (searchable).
- **Loaded / read** — full text injected into the team's working memory.
- **Brief / project brief** — the L0 frozen project context.
- **L1 / L2** — per-role / per-theme additional context layers.
- **Specialist** — a Malik-recruited project-specific agent.
- **Staff** — the four permanent meta-agents (Armance, Malik, Kim, Mona)
  plus Serge.
- **Caveman protocol** — ultra-compressed prompting overlay used to reduce
  token cost on worker agents.

---

## 15. Conventions for new code

- One PR = one logical change. Small commits encouraged.
- Conventional Commits format. Scope is the top-level module: `feat(library)`,
  `fix(malik)`, `refactor(workflow-engine)`.
- New slash command? Add at least one natural-language alias.
- New side effect? Add an `[EXECUTE:/...]` tag.
- New user-facing string? It goes in both `en.yaml` and `fr.yaml`. Log
  messages stay English.
- New agent skill? Subclass the existing skill pattern in
  `service/agents/*.py` and register in `handlers.HANDLERS`.

Welcome aboard.
