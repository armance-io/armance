# Armance

[![CI](https://github.com/GrIc/Armance/actions/workflows/ci.yml/badge.svg)](https://github.com/GrIc/Armance/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

> Armance is a **brain**, not a **maker**.
> It thinks alongside you — through a small staff of LLM agents that argue,
> stress-test, and synthesise — over your own documents.
> You keep the hands. Armance keeps the head.

---

> **For AI agents reading this file:** start here, then read
> [`roadmap/02_architecture.md`](roadmap/02_architecture.md) for the module
> map and [`CLAUDE.md`](CLAUDE.md) for project conventions.

---

## 1. Why & What

### The problem

Most "AI tools" act as **makers** — they generate code, prose, slides. They
race to a single answer. That is the wrong shape for the hardest moments of
strategic work:

- Framing an ambiguous problem.
- Deciding between two plausible directions.
- Stress-testing a plan before committing to it.
- Synthesising contradictory expert opinions.

In those moments, you do not need a faster typist. You need a **thinking
partner** that pulls multiple competent perspectives, makes them disagree
productively, and forces you to see the angle you would have missed.

### What Armance is

A small, local, file-backed **firm of agents** that lives in `.cortex/` next
to your project:

- **Armance** — host. Frames the project. Routes the room.
- **Malik** — recruiter. Picks specialists *whose personas disagree usefully*.
- **Kim** — operator. Designs and runs the workflow.
- **Mona** — vice-president. Synthesises, challenges, recommends.
- **Serge** — adversarial criticalist. Stress-tests every synthesis, on a
  deliberately different model family for maximum epistemic diversity.

Plus the **specialists** Malik recruits per project (UX researchers,
historians, ops engineers — whatever the brief calls for).

You drop documents, you describe your project, Armance deliberates, you
walk away with a synthesised brief, a slide deck, or a PDF you can defend.

### The brain-vs-hands principle

Armance is intentionally **bad at executing** and **good at deciding**:

| Armance does | Armance does not |
|---|---|
| Frame the problem with the user | Write your codebase |
| Recruit a panel of disagreeing personas | Manage a queue of tasks |
| Run a workflow across that panel | Push to your CI |
| Stress-test the synthesis with Serge | Send the email |
| Produce a defensible decision brief | Be your IDE |

It is the **expert committee on demand** — not a chat app, not a copilot,
not an autonomous agent.

---

## 2. Installation & setup

### Prerequisites

- Python ≥ 3.11
- At least one LLM provider key (OpenRouter recommended; free models work)

### Install

```bash
# Recommended — uv tool (isolated, fast)
uv tool install git+https://github.com/GrIc/Armance.git

# Alternative — pipx
pipx install git+https://github.com/GrIc/Armance.git

# Contributor / dev
git clone https://github.com/GrIc/Armance.git && cd Armance
uv sync && uv pip install -e .
```

Verify: `cortex --version`.

### Initialise a project

```bash
mkdir my-project && cd my-project
cortex init
```

`cortex init` walks you through six choices:

1. **Providers** — `openrouter`, `claude-code`, `gemini`, `custom-openai`.
2. **API keys** for each selected provider (stored in `.cortex/.env`,
   gitignored).
3. **Default provider + model**.
4. **Budget effort** — `free-first`, `low`, `medium`, `high`, `adaptive`.
5. **Interface language** — English / Français / Español / Deutsch / 中文
   / 日本語. *Every meta-agent (Armance, Malik, Kim, Mona, Serge) and every
   recruited specialist replies in this language regardless of how you write
   to them.* Default is auto-detected from `$LANG`.
6. **Embedding model** — Armance queries your configured provider APIs and
   lists the available embedding models so you can pick one for semantic
   document search (RAG). You can skip this step and enable it later via
   `config.yaml`.

The result is a `.cortex/` directory next to your code with the five built-in
system agents (Armance · Malik · Kim · Mona · Serge) pre-installed. Workflows
are created on demand through Kim — no default placeholder is shipped.

### Optional extras

```bash
# PDF deliverables (Linux native libs for WeasyPrint)
sudo apt-get install libgobject-2.0-0 libcairo2 libpango-1.0-0

# claude-code provider (+75 MB)
uv pip install 'cortex[claude]'

# Web UI prerequisites (parked — see roadmap/04_roadmap.md)
uv pip install 'cortex[web]'
```

### Health check

```bash
cortex doctor
```

Reports: config validity, provider reachability, sqlite-vec availability,
deliverable libs, ledger writability.

---

## 3. How it works

### 3.1 The user journey

```
   ┌─────────────────┐
1. │ cortex init     │  pick providers, models, budget, language
   └────────┬────────┘
            │
   ┌────────▼────────┐
2. │ drop docs       │  .cortex/docs/  → auto-indexed on `cortex run`
   └────────┬────────┘
            │
   ┌────────▼────────┐
3. │ cortex run      │  TUI opens; Armance greets in your language
   └────────┬────────┘
            │
   ┌────────▼─────────────────────────────────────┐
4. │ Armance frames the project                    │  asks focused questions,
   │   "What audience? What constraint?"          │  proposes /library index
   │   /library load <file> if needed             │  and /library load,
   │ → /save when context is rich                 │  freezes L0 context
   └────────┬─────────────────────────────────────┘
            │
   ┌────────▼─────────────────────────────────────┐
5. │ Malik recruits specialists                   │  axis of disagreement
   │   "Sarah · data-driven / Julian · empathic   │  per role, plus Serge
   │    / Serge · adversarial-criticalist"         │  always included
   └────────┬─────────────────────────────────────┘
            │
   ┌────────▼─────────────────────────────────────┐
6. │ Kim designs a workflow (S0 → S6 dialogue)  │  3 shapes — short /
   │   tailored step ids + roles via LLM call     │  standard / deep
   │   explicit naming                            │
   └────────┬─────────────────────────────────────┘
            │
   ┌────────▼─────────────────────────────────────┐
7. │ /workflow run <name>                         │  cost estimate first,
   │   parallel deliberation per level            │  HITL checkpoint mid-run,
   │   Mona synthesises, Serge red-teams          │  versioned reports
   └────────┬─────────────────────────────────────┘
            │
   ┌────────▼─────────────────────────────────────┐
8. │ /deliverable pdf|docx|pptx|md                │  .cortex/exports/
   └──────────────────────────────────────────────┘
```

### 3.2 Storage layout — everything is a file

```
.cortex/
  docs/               your documents (PDF, DOCX, MD, TXT)
  vector/             sqlite-vec store + manifest.json (indexed docs) +
                      read.json (persistently loaded docs)
  agents/             one .md per agent (YAML frontmatter + system prompt)
    system-*.md         built-in staff (Armance/Malik/Kim/Mona/Serge)
    <Name>.md           Malik-recruited specialists
  workflows/          *.yaml DAG definitions
  context/            L0_v<N>.md / L1_<role>_v<N>.md / L2_<theme>_v<N>.md
  reports/            versioned <agent>_v<N>.md per step
  sessions/<id>/      state.json + ledger.json + conversation.md
  exports/            generated deliverables
  config.yaml         non-secret config (providers, default model, language)
  .env                provider API keys — gitignored
```

No database is the source of truth. Markdown is. SQLite is used **only** for
vector retrieval.

### 3.3 The four-layer architecture

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

Each layer imports only from layers below it. See
[`roadmap/02_architecture.md`](roadmap/02_architecture.md) for the module
map and dependency rules.

### 3.4 Providers

| Provider | Key env var | Notes |
|---|---|---|
| `openrouter` | `OPENROUTER_API_KEY` | Default. Supports `reasoning`. Many free `:free` models. |
| `claude-code` | uses `claude-agent-sdk` auth | Requires `pip install 'cortex[claude]'`. |
| `gemini` | `GEMINI_API_KEY` | |
| `custom-openai` | `CUSTOM_OPENAI_API_KEY` + `CUSTOM_OPENAI_BASE_URL` | Any OpenAI-compatible endpoint. |

### 3.5 Configuration reference

All non-secret settings live in `.cortex/config.yaml`. API keys live in
`.cortex/.env` (auto-gitignored). Both files are created by `cortex init`
and can be edited by hand at any time — changes take effect on the next
`cortex run`.

#### `.cortex/config.yaml`

| Field | Default | What it does |
|---|---|---|
| `default_provider` | `openrouter` | LLM provider used for all agents unless overridden per-agent. One of `openrouter`, `claude-code`, `gemini`, `custom-openai`. |
| `default_model` | *(model chosen at init)* | Model id for all agents. Agents can override this in their `.md` frontmatter. |
| `budget_effort` | `free-first` | Cost guard for the whole session. `free-first` = only free models; `low` = cheap paid; `medium` / `high` = progressively more expensive; `adaptive` = Armance chooses per step. Changeable live via `/effort`. |
| `budget_cap_usd` | `null` | Hard USD cap per session. `null` = no cap. E.g. `0.50` stops any run that would exceed $0.50. |
| `language` | *(chosen at init)* | Interface language. All agents reply in this language regardless of how you write to them. Values: `en`, `fr`, `es`, `de`, `zh`, `ja`. |
| `embedding_provider` | *(chosen at init)* | Provider used for document embedding (RAG). Leave blank to disable RAG. |
| `embedding_model` | *(chosen at init)* | Embedding model id. Must match `embedding_provider`. Leave blank to disable RAG. |
| `judge_provider` | `openrouter` | Provider used for Mona's synthesis / Serge's stress-test. Defaults to `default_provider`. |
| `judge_model` | `""` | Model id for the judge. Empty = use `default_model`. |
| `judge_reasoning` | `null` | Reasoning effort for the judge (`low`, `medium`, `high`, or `null`). Only used by providers that support extended reasoning. |
| `log_level` | `INFO` | Python logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `prices` | `{}` | Override per-model USD prices (input + output per MTok). Example: `prices: {my-model: {input_per_mtok: 1.0, output_per_mtok: 5.0}}`. |

#### `.cortex/.env`

| Variable | Provider | What it does |
|---|---|---|
| `OPENROUTER_API_KEY` | openrouter | Your OpenRouter API key. Get one at openrouter.ai. |
| `OPENROUTER_BASE_URL` | openrouter | Override the API base URL (default: `https://openrouter.ai/api/v1`). Useful for self-hosted proxies. |
| `GEMINI_API_KEY` | gemini | Your Google Gemini API key (Google AI Studio). |
| `GEMINI_BASE_URL` | gemini | Override Gemini base URL. |
| `CUSTOM_OPENAI_API_KEY` | custom-openai | API key for your custom OpenAI-compatible endpoint. |
| `CUSTOM_OPENAI_BASE_URL` | custom-openai | Base URL for your custom endpoint (e.g. `http://localhost:11434/v1` for Ollama). |
| `CORTEX_JUDGE_REASONING` | all | Override judge reasoning effort at runtime. |

> **Tip:** you can also set any env variable in your shell before running
> `cortex run` — shell values override `.env` values.

### 3.6 TUI commands (the short list)

| Command | Effect |
|---|---|
| `/help`, `/quit` | self-explanatory |
| `/switch <agent>` | route next turn to an agent (or `@Name` inline) |
| `/save` | freeze current project context into L0 |
| `/workflow design <name>` | start Kim's S0 → S6 dialogue |
| `/workflow run <name>` | execute a workflow (cost preflight) |
| `/deliverable pdf\|docx\|pptx\|md` | export the latest synthesis |
| `/report` | persist the last reply as a versioned report |
| `/export claude\|opencode\|cline\|roo\|all` | emit agent docs for another tool |
| `/model`, `/effort` | switch provider/model or reasoning effort |

Everything is **natural-language first**. Slash commands are aliases. You can
type "Malik, recrute deux historiens" — the recruiter intercepts it.

### 3.7 What runs your turn

A typical chat turn calls:

1. **`dispatch_input`** (service/tui_bridge) — routes by `@mention` or
   current agent.
2. The right meta-agent service (`HostAgentService`, `RecruiterAgentService`,
   …) builds its system prompt: agent body + voice overlay (your language)
   + RAG injection (top-k chunks from your docs) + project brief + team
   roster.
3. `call_with_ledger` calls the provider via the chosen `LLMClient` and
   accumulates token usage.
4. The reply is scanned for `[EXECUTE:/save]`, `[EXECUTE:/recruit]`,
   `[EXECUTE:/workflow-design]`, `[EXECUTE:/workflow-run:<name>]`,
   `[EXECUTE:/dismiss-all]`. Matching tags trigger the corresponding side
   effect (write a file, run a DAG, delete agents).
5. The conversation is appended to `.cortex/sessions/<id>/conversation.md`
   and the ledger is persisted.

---

## 4. Tests

```bash
uv run pytest tests/                       # unit + integration (no network)
uv run python scripts/qa_live.py           # live OpenRouter free-model QA
```

`qa_live.py` exercises the full user journey: greeting → context → recruit
→ dismiss → re-recruit → design → run → deliverable → RAG round-trip →
language switch.

---

## 5. Roadmap & vision

See [`roadmap/`](roadmap/):

- [`00_journey.md`](roadmap/00_journey.md) — what got us here.
- [`01_vision.md`](roadmap/01_vision.md) — the brain-vs-hands manifesto.
- [`02_architecture.md`](roadmap/02_architecture.md) — module map &
  dependency rules.
- [`03_assessment_2026-05-14.md`](roadmap/03_assessment_2026-05-14.md) —
  current state audit.
- [`04_roadmap.md`](roadmap/04_roadmap.md) — phased plan, including the
  web port.

---

## 6. License

Apache-2.0.
