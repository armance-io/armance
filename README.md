<div align="center">

# Armance 👒

**A brain you consult when the choice matters.**

Not a copilot. Not an autonomous agent. A small firm of LLM experts that **debates, stress-tests, and synthesises** — over your own documents — so you can make a decision you can defend.

[![CI](https://github.com/armance-io/armance/actions/workflows/ci.yml/badge.svg)](https://github.com/armance-io/armance/actions/workflows/ci.yml)
[![License: AGPL v3](https://img.shields.io/badge/license-AGPL--3.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![DCO](https://img.shields.io/badge/DCO-required-orange.svg)](CONTRIBUTING.md#developer-certificate-of-origin-dco)

[Install](#install) · [Quickstart](#quickstart) · [How it works](#how-it-works) · [Contributing](CONTRIBUTING.md) · [Vision](roadmap/01_vision.md) · [Architecture](roadmap/02_architecture.md)

</div>

---

> **For AI agents reading this file:** start here, then read
> [`roadmap/02_architecture.md`](roadmap/02_architecture.md) for the module map
> and [`CLAUDE.md`](CLAUDE.md) for project conventions.

---

## Why Armance

Most "AI tools" are **makers** — they race to a single answer, then ask you to ship it. That is the wrong shape for the hardest moments of strategic work:

- Framing an ambiguous problem.
- Deciding between two plausible directions.
- Stress-testing a plan before committing.
- Synthesising contradictory expert opinions.

In those moments you do not need a faster typist. You need a **thinking partner** that pulls multiple competent perspectives, makes them disagree productively, and forces you to see the angle you would have missed.

Armance is that partner. It runs locally, reads your documents, recruits a panel of specialists with conflicting personas, runs them through a workflow, and hands you a defensible brief. You keep the call.

### The brain-vs-hands principle

| Armance does | Armance does **not** |
|---|---|
| Frame the problem with you | Write your codebase |
| Recruit a panel of disagreeing personas | Manage a queue of tasks |
| Run a workflow across that panel | Push to your CI |
| Stress-test the synthesis | Send the email |
| Produce a defensible decision brief | Be your IDE |

---

## Meet the staff

Five permanent meta-agents live in every Armance project. They never recruit themselves; they coordinate the specialists Armance brings in for your specific brief.

| | Role | Voice |
|---|---|---|
| **Armance** | Host — frames the project, routes the room | French refinement. Systematic *vouvoiement*. |
| **Malik**   | Recruiter — picks specialists whose personas disagree usefully | Quiet force, slow tempo, Gainsbourgian nonchalance. |
| **Kim**     | Operator — designs and runs the workflow | Direct, technical, square. Numbered lists, no padding. |
| **Mona**    | VP — synthesises, challenges, recommends | Cash and direct. Changes a room's centre of gravity in two sentences. |
| **Serge**   | Adversarial criticalist — stress-tests every synthesis | The cynical senior French engineer. *« \*soupir\* »* before every critique. |

Plus the **specialists** Malik recruits per project (UX researchers, historians, ops engineers — whatever the brief calls for), each with a generated 200-word persona prompt.

---

## Install

Project home: **[armance.io](https://armance.io)** *(site coming soon)*.
For the full, OS-by-OS guide (and a copy-paste prompt to let an AI agent
install it for you), see **[`INSTALL.md`](INSTALL.md)**.

### Prerequisites

- Python ≥ 3.11
- At least one LLM provider key. **OpenRouter is the easiest start** — its
  free tier runs Armance end to end with no spend.

### The one command

```bash
pip install armance
```

That's it. The base install gives you the full CLI/TUI, RAG, **all four
providers** (OpenRouter, `claude-code` subscription, Gemini, custom
OpenAI-compatible), DOCX / PPTX / Markdown deliverables, and the **web
UI** — no extras to choose. (PDF export is the one optional extra — see
below — because it needs native libraries pip can't install on its own.)

> Prefer an isolated tool install? `uv tool install armance` or
> `pipx install armance` work identically.
>
> **Installing from git** (`pip install git+https://github.com/armance-io/armance.git`)
> ships the CLI but **not** the prebuilt web UI — the bundle is a build
> artifact, not tracked in git. From a git install, run `armance web --build`
> once (needs Node + pnpm) to generate it, or use a release wheel from PyPI
> where the UI is already bundled.

Verify:

```bash
armance --version
armance doctor      # config, provider reachability, sqlite-vec, deliverables, ledger
```

> **Reaching Claude models:** two ways, both on the base install. Through
> **OpenRouter** (set `OPENROUTER_API_KEY`), or through a Claude Pro/Max
> *subscription* via the bundled `claude-code` provider (Anthropic's
> `claude-agent-sdk` ships in the package — no extra to install).

#### Optional extra: PDF export

Every export format works out of the box **except PDF**. PDF uses
WeasyPrint, which depends on native libraries (GTK / Pango / Cairo) that
pip cannot install — so it is opt-in:

```bash
pip install 'armance[pdf]'
```

Then install the native libs for your OS:

- **Linux:** `sudo apt-get install libgobject-2.0-0 libcairo2 libpango-1.0-0`
- **macOS:** `brew install pango` (usually already present)
- **Windows:** install the GTK runtime — see the
  [WeasyPrint install guide](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#installation).

DOCX / PPTX / Markdown exports need none of this. If WeasyPrint is
missing, `armance` simply skips PDF with a clear message — it never
crashes.

### Contributor / dev setup

```bash
git clone https://github.com/armance-io/armance.git
cd armance
uv sync
```

> An editable install lives in the project's `.venv` — it is **not** put on
> your `PATH`. Run the CLI with **`uv run armance …`** (or activate the venv:
> `source .venv/bin/activate`). A separate `uv tool install` / `pipx install`
> is what puts a global `armance` on `PATH`; don't confuse the two.

The web UI is a build artifact and is **not** in git, so a fresh clone has no
bundle yet. Build it once (needs Node + pnpm), then run:

```bash
uv run armance web --build          # builds the UI bundle, then serves it
# subsequent runs (bundle already built):
uv run armance web
```

See [`web/DEVELOPMENT.md`](web/DEVELOPMENT.md) for the full dev loop
(hot-reload vs bundled, tests).

---

## Running the web client (UI)

Armance V2 ships a Belle Époque web UI (Next.js 16 + React 19) on top of a
FastAPI server. **One command runs both the API and the UI in a single
process** — no Node, no second server:

```bash
armance web                 # serves API + UI at http://127.0.0.1:8000, opens a browser
```

By default the server runs **in the background**: the command waits until the
server answers, opens a browser, prints the URL + pid, and returns `0`. Logs go
to the server's log file (not the terminal). Stop it with `armance stop` (or
`armance web --stop`) — **from any folder**. Use `--foreground` to block
instead (Ctrl+C stops it; logs stream to the terminal) — handy for dev.

There is **one server for all projects**: `armance web` is not folder-contextual.
Wherever you run it, it serves the global launcher (the projects list) and you
pick a project from the UI. The server is homed in the global config dir
(`~/.config/armance` on Linux) with a lock file recording the running instance;
a second `armance web` is refused until you stop the first (stale locks from a
crashed server are detected and cleared automatically). `armance stop` finds
that global server from anywhere; if none is running it falls back to a legacy
per-folder server in the current directory.

Options:

| Flag | Effect |
|---|---|
| `--port 8000` | port (default `8000`) |
| `--bind 0.0.0.0` | expose on the LAN (read-only for watchers; only the first client may write) |
| `--no-browser` | don't auto-open a browser |
| `--foreground` | block in the terminal (Ctrl+C stops; logs stream to stdout) instead of backgrounding |
| `--stop` | stop THE server, from any folder (aliases: `armance stop`, `armance web stop`) |
| `--build` | (repo checkout only) rebuild the UI bundle before serving — needs Node + pnpm |

**Where the UI comes from:**

| Install method | Ships the UI? | How to get the UI |
|---|---|---|
| `pip install armance` (PyPI release) | ✅ bundled | nothing — `armance web` just works |
| `git clone` + editable / `uv tool install git+…` | ❌ artifact, not in git | run `armance web --build` once from a **checkout** (the tool install has no frontend sources — clone the repo) |

If you see *“no bundled UI found — running API only”*, the bundle hasn't been
built for this install. Use a release wheel, or `armance web --build` from a
clone.

### Frontend dev mode (hot reload)

For live iteration on the UI, run the two dev servers side by side (no bundle
needed):

```bash
uv run armance web --no-browser              # API on :8000
cd web/frontend && pnpm install && pnpm dev  # UI on :3000, proxies /api → :8000
```

---

## Quickstart

```bash
mkdir my-project && cd my-project
armance init        # interactive — providers, default model, budget, language
armance run         # opens the TUI
```

`armance init` walks through:

1. **Providers** — `openrouter`, `claude-code`, `gemini`, `custom-openai` (multi-select).
2. **API keys** — stored in `.armance/.env` (gitignored).
3. **Default provider + model**.
4. **Budget effort** — `free-first` / `low` / `medium` / `high` / `adaptive`.
5. **Interface language** — EN / FR / ES / DE / ZH / JA. *Every agent — staff and specialists — replies in this language.* Auto-detected from `$LANG`.
6. **Embedding model** — discovered from your configured provider's API; can be skipped and configured later.
7. **Rerank model** (optional) — a cross-encoder re-orders RAG results after vector recall. Its provider may differ from the embedding provider (only `custom-openai` and `openrouter`-via-proxy can serve it); skip to keep plain vector order.

Drop documents into `.armance/docs/` and run `armance run`. Armance greets you, frames the project, recruits a team, designs a workflow, runs it, and exports a deliverable.

---

## How it works

### Environmental Footprint

The environmental footprint of LLM usage is estimated using [EcoLogits](https://github.com/genai-impact/ecologits) (Life Cycle Assessment, ISO 14044), computed entirely offline so no data leaves your machine. For each response, the footprint combines the use phase (GPU energy deduced from generated tokens and latency, multiplied by the data center's PUE) and the embodied impact of hardware manufacturing, amortized over its lifespan. The energy is then converted into gCO₂e via the carbon intensity of the zone's electrical grid, and into milliliters of water via the WUE (water-usage effectiveness) of that facility.

### The user journey

```
                 ┌─────────────────┐
              1. │  armance init   │  pick providers, models, budget, language
                 └────────┬────────┘
                          │
                 ┌────────▼────────┐
              2. │   drop docs     │  .armance/docs/  → auto-indexed on `armance run`
                 └────────┬────────┘
                          │
                 ┌────────▼────────┐
              3. │   armance run   │  TUI opens; Armance greets in your language
                 └────────┬────────┘
                          │
                 ┌────────▼─────────────────────────────────────┐
              4. │  Armance frames the project                  │  asks focused questions,
                 │    "What audience? What constraint?"         │  proposes /library index
                 │    /library load <file> if needed            │  and /library load,
                 │  → /save when context is rich                │  freezes L0 context
                 └────────┬─────────────────────────────────────┘
                          │
                 ┌────────▼─────────────────────────────────────┐
              5. │  Malik recruits specialists                  │  axis of disagreement
                 │    "Sarah · data-driven / Julian · empathic" │  per role; rich
                 │    each with a 200-word persona              │  persona generation
                 └────────┬─────────────────────────────────────┘
                          │
                 ┌────────▼─────────────────────────────────────┐
              6. │  Kim designs a workflow                      │  3 strategies —
                 │    NL dialogue, narrow scope, tailored steps │  rapide / équilibrée /
                 │    interactive ↔ autonomous run mode         │  approfondie
                 └────────┬─────────────────────────────────────┘
                          │
                 ┌────────▼─────────────────────────────────────┐
              7. │  /workflow run <name>                        │  pre-run health-check,
                 │    parallel deliberation per DAG level       │  HITL checkpoints
                 │    Mona synthesises, Serge red-teams         │  (autonomous = Mona
                 │                                              │   proxies for the CEO),
                 │                                              │  versioned manifest
                 │                                              │  with per-step tokens
                 │                                              │  and duration
                 └────────┬─────────────────────────────────────┘
                          │
                 ┌────────▼─────────────────────────────────────┐
              8. │  /deliverable pdf | docx | pptx | md         │  .armance/exports/
                 └──────────────────────────────────────────────┘
```

### Deliberation restitution — the process, not just the output

A run hands you more than a synthesis: it shows you *how the room got there*.
Every run directory carries, alongside the synthesis:

- **`arguments.json` / `sources.json`** — the **argument ledger**. Mona tags
  each argument the panel **retained** vs **rejected**, with who proposed it,
  who rejected it and *why*, and the source it leaned on. The web UI renders
  this as two columns (retained / rejected); rejected arguments are struck
  through with their rejection reason, sources are click-to-jump chips.
- **`assumptions.md`** — in **autonomous** mode, every hypothesis Mona made on
  the absent user's behalf, plus the `HYPOTHESIS:` / `QUESTION:` markers the
  specialists raised under the strict no-hallucination policy. Surfaced in the
  UI's hypothesis list so an autonomous run's guesses are never silent.
- **`trace.md`** — the human-readable agent trace (arguments kept, dropped,
  adopted from a peer, Serge's objections and how they were addressed).

Two guarantees make this trustworthy:

- **Interactive (HITL) run — no hallucination.** Each specialist runs under a
  strict anti-hallucination policy: when it lacks a fact it must emit
  `QUESTION:` / `HYPOTHESIS:` rather than invent. Agents work with what they have.
- **Autonomous run — Mona's hypotheses are identifiable.** Mona breaks ties on
  the user's behalf, but every decision is marked `**Hypothèse (Mona) :**` and
  logged to the assumption ledger; on a critical/high-risk call she refuses to
  guess and escalates back to the user (`[ASK_USER]`). Each checkpoint records
  **who** answered — the user, or Mona.

### Storage layout — everything is a file

```
.armance/
  docs/               your documents (PDF, DOCX, MD, TXT)
  vector/             sqlite-vec store + manifest.json + read.json
  agents/             one .md per agent (YAML frontmatter + system prompt)
    system-*.md         built-in staff (Armance / Malik / Kim / Mona / Serge)
    <Name>.md           Malik-recruited specialists, with rich personas
  workflows/          *.yaml DAG definitions
  context/            L0_v<N>.md / L1_<role>_v<N>.md / L2_<theme>_v<N>.md
  reports/            versioned <agent>_v<N>.md per step
  sessions/<id>/      state.json + ledger.json + conversation.md
  exports/<wf>/run-<ts>/  per-run manifest + per-step outputs + synthesis
                      + trace.md, assumptions.md, arguments.json, sources.json
  config.yaml         non-secret config (providers, default model, language)
  .env                provider API keys — gitignored
```

Markdown is the source of truth. SQLite is used **only** for vector retrieval.

### Four-layer architecture

```
┌────────────────────────────────────────────────────┐
│ client     TUI (Textual) — and future web client   │
├────────────────────────────────────────────────────┤
│ transport  DTOs + event bus — wire-format only     │
├────────────────────────────────────────────────────┤
│ service    orchestration, agents, workflows, RAG   │
├────────────────────────────────────────────────────┤
│ core       pure models + protocols, no I/O         │
└────────────────────────────────────────────────────┘
```

Each layer imports only from layers below. Enforced by [`import-linter`](https://github.com/seddonym/import-linter). See [`roadmap/02_architecture.md`](roadmap/02_architecture.md) for the module map.

### Providers

| Provider | Key env var | Notes |
|---|---|---|
| `openrouter`   | `OPENROUTER_API_KEY` | Default. Live model discovery. Many `:free` models. Supports reasoning effort. |
| `claude-code`  | uses `claude-agent-sdk` auth | Bundled by default (no extra). Subscription = effectively free for the user. Native web search via WebSearch tool. |
| `gemini`       | `GEMINI_API_KEY` | Live discovery via `/v1beta/models`. Native Google Search grounding. |
| `custom-openai`| `CUSTOM_OPENAI_API_KEY` + `CUSTOM_OPENAI_BASE_URL` | Any OpenAI-compatible endpoint. |

Models are discovered live; pricing tiers, web-search capability, reasoning
support, and context window are read from each provider's API. The one
exception is the `claude-code` **subscription** path: it authenticates through
the `claude-agent-sdk` and has no `ANTHROPIC_API_KEY`, so the live
`/v1/models` call can't run — those users get a small curated catalogue of the
latest Claude models. Set `ANTHROPIC_API_KEY` to enable full live discovery
(including per-model context windows) for `claude-code` too. The curated list
is a fallback, never a hardcoded catalogue presented as live.

### Configuration

All non-secret settings live in `.armance/config.yaml`. API keys live in `.armance/.env`. Both are created by `armance init` and can be edited by hand — changes take effect on the next `armance run`.

#### `.armance/config.yaml`

| Field | Default | What it does |
|---|---|---|
| `default_provider` | `openrouter` | LLM provider used for all agents unless overridden per-agent. |
| `default_model` | *(chosen at init)* | Model id for all agents. Per-agent override via the agent's `.md` frontmatter. |
| `budget_effort` | `free-first` | Cost guard. `free-first` keeps effectively-free models (OpenRouter `:free`, Claude subscription) regardless of nominal tier. Changeable live via `/effort`. |
| `budget_cap_usd` | `null` | Hard USD cap per session. `null` = no cap. |
| `language` | *(chosen at init)* | `en` / `fr` / `es` / `de` / `zh` / `ja`. All agents reply in this language. |
| `embedding_provider` | *(chosen at init)* | Provider used for RAG. Leave blank to disable. |
| `embedding_model` | *(chosen at init)* | Embedding model id. Must match `embedding_provider`. |
| `rerank_provider` | `""` | Provider serving the rerank endpoint (`openrouter` via a Cohere-style proxy on `OPENROUTER_BASE_URL`, or `custom-openai`). May differ from `embedding_provider`. Blank = no reranking. |
| `rerank_model` | `""` | Cross-encoder model id (e.g. `bge-reranker-v2-m3`). Blank = vector order only. |
| `rerank_candidate_k` | `20` | Vector-recall candidates fed to the reranker (stage 1). |
| `rerank_keep_n` | `5` | Chunks kept after reranking (stage 2). Rerank failures degrade silently to vector order. |
| `log_level` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `prices` | `{}` | Override per-model USD prices. Example: `prices: {my-model: {input_per_mtok: 1.0, output_per_mtok: 5.0}}`. |

*Le modèle de Mona = `default_model` ; ajustez-le par agent via Malik si besoin.*

#### `.armance/.env`

| Variable | Provider | Notes |
|---|---|---|
| `OPENROUTER_API_KEY` | openrouter | Get one at openrouter.ai. |
| `OPENROUTER_BASE_URL` | openrouter | Override base URL (default: `https://openrouter.ai/api/v1`). |
| `GEMINI_API_KEY` | gemini | Google AI Studio. |
| `GEMINI_BASE_URL` | gemini | Override base URL. |
| `ANTHROPIC_API_KEY` | claude-code | Used for live model discovery via `/v1/models`. |
| `CUSTOM_OPENAI_API_KEY` | custom-openai | Custom endpoint API key. |
| `CUSTOM_OPENAI_BASE_URL` | custom-openai | e.g. `http://localhost:11434/v1` for Ollama. |

Shell values override `.env` values.

### TUI commands (short list)

| Command | Effect |
|---|---|
| `/help`, `/quit` | self-explanatory |
| `/switch <agent>` | route next turn to an agent (or `@Name` inline) |
| `/save` | freeze current project context into L0 |
| `/workflow design <name>` | start Kim's workflow design dialogue |
| `/workflow run <name>` | execute a workflow (interactive or autonomous) |
| `/deliverable pdf\|docx\|pptx\|md` | export the latest synthesis |
| `/report` | persist the last reply as a versioned report |
| `/export claude\|opencode\|cline\|roo\|all` | emit agent docs for another tool |
| `/model`, `/effort` | switch provider/model or reasoning effort |

Everything is **natural-language first**. Slash commands are aliases. *"Malik, recrute deux historiens"* — the recruiter intercepts it.

### What runs your turn

1. **`dispatch_input`** (service/tui_bridge) — routes by `@mention` or current agent.
2. The right meta-agent chat handler builds its system prompt: persona + voice overlay (your language) + RAG injection + project brief + team roster.
3. `call_with_ledger` calls the provider via the chosen `LLMClient` and accumulates token usage.
4. The reply is scanned for `[EXECUTE:/save]`, `[EXECUTE:/recruit]`, `[EXECUTE:/workflow-design]`, `[EXECUTE:/workflow-run:<name>:<mode>]`, `[EXECUTE:/dismiss-all]`. Tags trigger the corresponding side effect.
5. The conversation is appended to `.armance/sessions/<id>/conversation.md` and the ledger is persisted.

---

## Tests

```bash
uv run pytest tests/                                       # core: unit + integration (no network)
bash scripts/check_invariants.sh                           # layer + lifecycle invariants
uv run python scripts/qa_live.py                           # live OpenRouter free-model QA

# Web backend (ships in the package):
cd web && uv run pytest ../src/armance/web/backend/tests/

# Web frontend:
cd web/frontend && pnpm typecheck && pnpm lint && pnpm test && pnpm e2e
```

`qa_live.py` exercises the full user journey: greeting → context → recruit → dismiss → re-recruit → design → run → deliverable → RAG round-trip → language switch.

---

## Roadmap & vision

See [`roadmap/`](roadmap/):

- [`01_vision.md`](roadmap/01_vision.md) — the brain-vs-hands manifesto.
- [`02_architecture.md`](roadmap/02_architecture.md) — module map & dependency rules.

Phased planning and per-issue specs are tracked privately by the
maintainer.

---

## License

**AGPL-3.0-or-later.** Copyright © 2026 Guillaume Richard.

The strong copyleft license is intentional. If you run a modified Armance as a network service, you must publish your modifications. Commercial dual-licensing is available — contact `guillaume@richard-pro.fr`.

See [`LICENSE`](LICENSE) for the full text.
