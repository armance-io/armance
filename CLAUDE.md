# Armance — Project Instructions for AI Agents

Armance = sovereign, contradictory, honest thinking partner. **Brain, not
maker** — the edge is a panel *built to disagree* (Serge on a different model
family), dated RAG + claims ledger, and a non-fabricated CO₂e/water footprint;
not the multi-agent pattern itself (commoditised). Sovereign by doctrine:
single-user, local-first, no SaaS. Read
[`roadmap/01_vision.md`](roadmap/01_vision.md) first.

Standalone Python CLI. Markdown is the source of truth. No DB for primary
state (sqlite-vec only for RAG retrieval). Four providers: `openrouter`,
`claude-code`, `gemini`, `custom-openai`.

## Where things live

| Topic | File |
|---|---|
| User-facing intro | [`README.md`](README.md) |
| Engineering onboarding (senior devs) | [`ONBOARDING.md`](ONBOARDING.md) |
| Manual test scenarios (V1 convergence) | [`SCENARIOS.md`](SCENARIOS.md) |
| Rules for fixing agents | [`BUG_FIXING_GUIDE.md`](BUG_FIXING_GUIDE.md) |
| Vision & invariants | [`roadmap/01_vision.md`](roadmap/01_vision.md) |
| Architecture & module map | [`roadmap/02_architecture.md`](roadmap/02_architecture.md) |
| Web Backend (FastAPI routes) | `src/armance/web/backend/routes/` |
| Web Frontend (Next.js components) | `web/frontend/src/components/` |
| Web dev loop (build web_dist, test locally) | [`web/DEVELOPMENT.md`](web/DEVELOPMENT.md) |
| How to launch the web UI | [`README.md` → Web Client](README.md#running-the-web-client-ui) |

## Code conventions

- Python ≥ 3.11. `from __future__ import annotations` at the top of every module.
- Type hints everywhere. `asyncio` for parallelism. No blocking I/O on the hot path.
- `logging` module. No `print` debug.
- **File size limits**: Python files must be ≤ 300 LOC. React component files must be ≤ 250 LOC.
- Open exceptions (split queued — P1.6+):
  `cli.py` (~1560), `service/agents/host_agent.py` (~1160), `service/handlers.py` (~1150), `service/agents/recruiter_agent.py` (~1070), `service/chat_handlers/malik.py` (~820), `core/models/context.py` (~760), `client/tui/screens/main.py` (~670), `service/agents/agent_lifecycle_service.py` (~550), `client/tui/widgets/sidebar.py` (~550), `core/models/workflow.py` (~520), `service/llm_service.py` (~510), `service/workflow_runs.py` (~470). ~14 more legacy files sit at 300-450 LOC and are tolerated as-is. The limit applies strictly to NEW files; refactor before adding to any file listed here.
  React: ~20 legacy components exceed 250 LOC (worst: `admin/ConfigForm.tsx` ~714) — same rule: new components stay small, split before growing a listed one.
- `uv` for Python deps, `pnpm` for frontend deps. Conventional commits (signed off with `git commit -s`).
- Tests: `pytest` + `pytest-asyncio` + `respx` (httpx) + `monkeypatch` (claude-agent-sdk). No real network. React components unit tested via `vitest` + `@testing-library/react`. E2E tested via Playwright.

## Layering — non-negotiable

```
client  →  transport  →  service  →  core
```

Lower layers never import from upper layers. Lint: `grep -rn
"from armance.client" src/armance/{core,service}` must return empty.

## Provider matrix

| Provider | API key env var | Reasoning support | Notes |
|---|---|---|---|
| `openrouter` | `OPENROUTER_API_KEY` | yes (`reasoning` field) | many free `:free` models |
| `claude-code` | `claude-agent-sdk` auth | no | bundled by default (no extra) |
| `gemini` | `GEMINI_API_KEY` | no | |
| `custom-openai` | `CUSTOM_OPENAI_API_KEY` + `CUSTOM_OPENAI_BASE_URL` | model-dependent | OpenAI-compatible |

## Side effects

Armance agents trigger side effects via **`[EXECUTE:/<command>]`** tags
appearing in their LLM reply. Tags are scrubbed against a **per-role
allow-list** (`service/agent_sandbox.py`) before interception — Armance
cannot recruit, Kim cannot save L0, specialists have no tools.

Current tags:
- Armance: `/save`, `/library-index`, `/library-load:<file>`,
  `/library-unload:<file>`, `/library-unindex:<file>`, `/library-status`
- Malik: `/recruit`, `/dismiss-all[:<name>]`, `/agent-swap:<name> <provider/model> [<provider/model>]`, `/library-status`
- Kim: `/workflow-design`, `/workflow-run:<name>`, `/library-status`
- Mona: `/save-deliverable:<basename>`, `/load-run:<wf>:<run_id>`, `/library-status`
- Specialist: `/load-run:<wf>:<run_id>` (compare past positions only)

Legacy aliases (`/ingest-docs`, `/load:X`, `/forget:X`, `/rag-status`)
still resolve through the dispatcher. Never add an implicit code path;
the tag must be present.

## Caveman protocols

`scripts/protocols/{ultra,lite,full}.txt` prepend a compression directive
to the system prompt. Worker agents get `ultra`; user-facing agents get
`lite` or `none`. The caller selects.

## Multilingual interface

`config.language` ∈ {`en`, `fr`, `es`, `de`, `zh`, `ja`}. A short *voice
overlay* (see `src/armance/service/agents/_voice_overlay.py`) is appended
to every system prompt so all agents reply in the chosen language. Set at
`armance init`; auto-detected from `$LANG` by default.

## Tests & QA

### CLI / Core Tests
```bash
uv run pytest tests/                 # offline suite (~1400 tests)
uv run python scripts/qa_live.py     # live OpenRouter free-model journey
bash scripts/check_invariants.sh     # layer + lifecycle invariants (43 checks)
```

### Web Backend Tests
The backend ships inside the package at `src/armance/web/backend/`. Run its
suite from the `web/` directory (web deps ship in core — no extra needed):
```bash
cd web && uv run pytest ../src/armance/web/backend/tests/   # offline routes suite (~230)
```

### Web Frontend Tests
Run from the `web/frontend/` directory:
```bash
pnpm run typecheck                   # compile check
pnpm run lint                        # lint check
pnpm test                            # unit tests (vitest)
pnpm playwright test                 # E2E tests (playwright)
```

`qa_live.py` exercises CLI sections: greeting → context → recruit → dismiss → re-recruit → Kim chat → design dialogue → run → RAG round-trip → language switch → workflow tailoring differentiation.

## TUI commands

`/help` `/quit` `/switch <agent>` `/model` `/effort` `/save`
`/workflow design|run|list|compare|rerun <name> [<run1> <run2>] [--override-step <id>=<file>] [--from-step <id>]`
`/task <domain> <prompt>` `/report` `/judge @file …`
`/deliverable pdf|docx|pptx|md` `/export claude|opencode|cline|roo|all`
`/agent` `/role`
`/library status|scan|index|unindex|load|unload`
`/feedback-loop <run-id>` `/iterate-from <run-id>`.

Every slash command has at least one NL alias. NL first; slash for power
users. The `/library` command is the single entry point for both the
searchable library (indexed slips / *feuillets* in FR) and the read set
(full-text docs loaded into every agent's context).

## When in doubt

1. Read [`ONBOARDING.md`](ONBOARDING.md) — single-file ramp covering the
   turn flow, library state, multi-provider matrix, and "where to look
   first" table.
2. Read [`roadmap/02_architecture.md`](roadmap/02_architecture.md) — module
   map.
3. Ask the maintainer for guidance on current priorities and the active
   work surface.
