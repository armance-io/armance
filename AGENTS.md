# Agent instructions

Armance is a sovereign, contradictory, honest thinking partner: a panel of LLM agents that deliberate over the user's
documents, on the user's machine. A standalone Python package (CLI, Textual TUI, local web UI), Markdown files as the
source of truth. Read [sdd/product.md](sdd/product.md) first, then [sdd/architecture.md](sdd/architecture.md).

## Where things live

| Topic | Home |
|---|---|
| Why, for whom, invariants, non-goals | [sdd/product.md](sdd/product.md) |
| System, layers, a turn, where state lives | [sdd/architecture.md](sdd/architecture.md) |
| Decisions, with what was rejected | [sdd/decisions.md](sdd/decisions.md) |
| Order of the work | [sdd/roadmap.md](sdd/roadmap.md) |
| Open bugs and ideas | `sdd/issues/<slug>.md` |
| What a module must do, linked to its tests | `sdd/modules/<module>.md` |
| User docs: install, quickstarts | [README.md](README.md), [INSTALL.md](INSTALL.md), [docs/](docs/) |
| Human contributors: DCO, licence, releases | [CONTRIBUTING.md](CONTRIBUTING.md) |
| Web dev loop | [web/DEVELOPMENT.md](web/DEVELOPMENT.md) |

## Project rules

- Layers: `client -> transport -> service -> core`, lower never imports upper. `core` never imports `providers`
  either: clients register through `core.protocols.llm.register_client`.
- Side effects only through `[EXECUTE:/<command>]` tags in an agent's reply, scrubbed against the per-role allowlist
  `_ROLE_TAG_ALLOWLIST` in `service/agent_sandbox.py`. A new tag goes into that allowlist, or the scrubber silently
  drops it. Never trigger an action by matching text.
- Only Mona and the specialists engage with project content: Armance frames, Malik recruits, Kim orchestrates.
- The service layer never prompts the human directly (no `input()`, no `questionary`): it goes through
  `ctx.checkpoint_handler`.
- One workflow engine, `core.models.workflow.execute_workflow`; safety nets are hooks in `service/workflow_hooks.py`.
  Runs are versioned and written only by `service/workflow_runs.py`. No default workflow ships: the user designs them
  with Kim.
- Every user-facing string goes through `armance.nls.t("key")`, with the key in all six catalogues
  (`src/armance/nls_catalogues/{en,fr,es,de,zh,ja}.yaml`); the web uses `t("key")` with
  `web/frontend/src/locales/<lang>/common.json`. Logs and exceptions stay in English.
- No hard-coded values that vary per user: embedding dimensions are probed, model ids come from the config, prices
  from `service/cost.py`, paths from `armance.storage.paths`.
- Domain presets are pure data (`src/armance/assets/presets/<name>/`): the engine never branches on a domain.
- The claude-code provider stays hermetic (`setting_sources=[]` in `providers/claude_utils.py`): the host's Claude
  Code plugins and hooks must not reach Armance agents.
- Python 3.11 or later, `from __future__ import annotations` at the top of every module, type hints, `asyncio` for
  parallel work, no blocking I/O on the hot path, `logging` and never `print` for debug.
- A new Python file stays within 300 lines, a new React component within 250. An older file over the limit is split
  before it grows ([split-big-files](sdd/issues/split-big-files.md)).
- No `try/except: pass`: log with `logger.exception`, or handle the specific error.

These public surfaces change only after asking the maintainer: `service.tui_bridge.dispatch_input`, the
`service.checkpoint` types, `core.protocols.llm.LLMClient`, `service.agent_sandbox.scrub_reply`, the
`service.workflow_runs` functions, slash command names and the tag list.

The tags each role may emit are listed in `_ROLE_TAG_ALLOWLIST` (`service/agent_sandbox.py`), the one
reference; the legacy aliases `/ingest-docs`, `/load`, `/forget` and `/rag-status` still resolve.

## Commands

| Check | Command |
|---|---|
| Core tests (offline) | `uv run pytest tests/ -q --tb=short` |
| Web backend tests | `cd web && uv run pytest ../src/armance/web/backend/tests/ -q --tb=short` |
| Lint | `uv run ruff check src/ tests/ scripts/` |
| Layers and invariants | `bash scripts/check_invariants.sh` |
| Frontend | `cd web/frontend && pnpm typecheck && pnpm lint && pnpm test && pnpm e2e` |
| Live journey (needs `OPENROUTER_API_KEY`) | `uv run python scripts/qa_live.py` |
| Preset bench (live, needs quota) | `uv run python scripts/bench_presets.py <preset> [--smoke]` |

Tests never touch the network: `respx` for httpx, `monkeypatch` for the claude-agent-sdk. Two traps: never GET an SSE
route through `ASGITransport` (it buffers forever), test at the session seam instead; e2e tests select by
`data-testid`, never by label, since a missing i18n key renders as the raw key.

## Commits

- Conventional Commits, the scope is the top-level module: `fix(library): ...`, `feat(malik): ...`.
- Every commit is signed off (`git commit -s`, DCO, checked in CI) and signed (SSH or GPG,
  `git config commit.gpgsign true`).
- One pull request, one logical change. Merge with a merge commit, never a squash.
