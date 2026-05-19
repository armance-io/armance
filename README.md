<div align="center">

# Armance 👒

**A brain you consult when the choice matters.**

Not a copilot. Not an autonomous agent. A small firm of LLM experts that **debates, stress-tests, and synthesises** — over your own documents — so you can make a decision you can defend.

[![CI](https://github.com/armance-io/armance/actions/workflows/ci.yml/badge.svg)](https://github.com/armance-io/armance/actions/workflows/ci.yml)
[![License: AGPL v3](https://img.shields.io/badge/license-AGPL--3.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![DCO](https://img.shields.io/badge/DCO-required-orange.svg)](CONTRIBUTING.md#developer-certificate-of-origin-dco)

[Install](#install) · [Quickstart](#quickstart) · [How it works](#how-it-works) · [Contributing](CONTRIBUTING.md) · [Roadmap](roadmap/04_roadmap.md) · [Web (planned)](WEB_NEXT.md)

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
| **Armance** | Host — frames the project, routes the room | French refinement (Audrey Tautou). Systematic *vouvoiement*. |
| **Malik**   | Recruiter — picks specialists whose personas disagree usefully | Quiet force, slow tempo, Gainsbourgian nonchalance. |
| **Kim**     | Operator — designs and runs the workflow | Direct, technical, square. Numbered lists, no padding. |
| **Mona**    | VP — synthesises, challenges, recommends | Cash and direct. Changes a room's centre of gravity in two sentences. |
| **Serge**   | Adversarial criticalist — stress-tests every synthesis | The cynical senior French engineer. *« \*soupir\* »* before every critique. |

Plus the **specialists** Malik recruits per project (UX researchers, historians, ops engineers — whatever the brief calls for), each with a generated 200-word persona prompt.

---

## Install

### Prerequisites

- Python ≥ 3.11
- At least one LLM provider key (OpenRouter recommended; free tier works end to end)

### Recommended — `uv tool` (isolated, fast)

```bash
uv tool install git+https://github.com/armance-io/armance.git
```

### Alternative — pipx

```bash
pipx install git+https://github.com/armance-io/armance.git
```

### Contributor / dev setup

```bash
git clone https://github.com/armance-io/armance.git
cd armance
uv sync && uv pip install -e .
```

Verify: `armance --version`

### Optional extras

```bash
# Claude subscription provider (+75 MB)
uv pip install 'armance[claude]'

# PDF deliverables (Linux native libs for WeasyPrint)
sudo apt-get install libgobject-2.0-0 libcairo2 libpango-1.0-0
```

### Health check

```bash
armance doctor
```

Reports: config validity, provider reachability, sqlite-vec availability, deliverable libs, ledger writability.

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

Drop documents into `.armance/docs/` and run `armance run`. Armance greets you, frames the project, recruits a team, designs a workflow, runs it, and exports a deliverable.

---

## How it works

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
| `claude-code`  | uses `claude-agent-sdk` auth | Requires `armance[claude]`. Subscription = effectively free for the user. Native web search via WebSearch tool. |
| `gemini`       | `GEMINI_API_KEY` | Live discovery via `/v1beta/models`. Native Google Search grounding. |
| `custom-openai`| `CUSTOM_OPENAI_API_KEY` + `CUSTOM_OPENAI_BASE_URL` | Any OpenAI-compatible endpoint. |

Models are discovered live; pricing tiers, web-search capability, and reasoning support are read from each provider's API. No hardcoded catalogue.

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
| `judge_provider` | `openrouter` | Provider used for Mona's synthesis / Serge's stress-test. |
| `judge_model` | `""` | Empty = use `default_model`. |
| `judge_reasoning` | `null` | `low` / `medium` / `high` / `null`. |
| `log_level` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `prices` | `{}` | Override per-model USD prices. Example: `prices: {my-model: {input_per_mtok: 1.0, output_per_mtok: 5.0}}`. |

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
| `ARMANCE_JUDGE_REASONING` | all | Override judge reasoning effort at runtime. |

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
uv run pytest tests/                       # unit + integration (no network)
uv run python scripts/qa_live.py           # live OpenRouter free-model QA
```

`qa_live.py` exercises the full user journey: greeting → context → recruit → dismiss → re-recruit → design → run → deliverable → RAG round-trip → language switch.

---

## Roadmap & vision

See [`roadmap/`](roadmap/):

- [`00_journey.md`](roadmap/00_journey.md) — what got us here.
- [`01_vision.md`](roadmap/01_vision.md) — the brain-vs-hands manifesto.
- [`02_architecture.md`](roadmap/02_architecture.md) — module map & dependency rules.
- [`03_assessment_2026-05-15.md`](roadmap/03_assessment_2026-05-15.md) — current state audit.
- [`04_roadmap.md`](roadmap/04_roadmap.md) — phased plan, including the web port.
- [`05_auto_embed_discovery.md`](roadmap/05_auto_embed_discovery.md) — embedding auto-discovery + per-model parameter discovery.
- [`06_workflow_runtime_ux.md`](roadmap/06_workflow_runtime_ux.md) — workflow runtime UX, parallelism, pipeline view.

Web client is parked but spec-complete: see [`WEB_NEXT.md`](WEB_NEXT.md).

---

## License

**AGPL-3.0-or-later.** Copyright © 2026 Guillaume Richard.

The strong copyleft license is intentional. If you run a modified Armance as a network service, you must publish your modifications. Commercial dual-licensing is available — contact `guillaume@richard-pro.fr`.

See [`LICENSE`](LICENSE) for the full text.
