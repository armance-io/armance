# Armance — Installation Guide

> Project home: **[armance.io](https://armance.io)** *(site coming soon)*.
> This guide is written to be followed by a human **or** by an AI coding
> agent (Claude Code, OpenCode, Cline, Roo, …) installing Armance on a
> user's behalf. See [Quickstart](quickstart.md) for the first session.

## TL;DR

```bash
pip install armance     # full CLI/TUI + RAG + 3 providers + web UI
armance init            # interactive setup (providers, model, budget, language)
armance run             # TUI
armance web             # web UI + API in one process at http://127.0.0.1:8000
```

`uv tool install armance` or `pipx install armance` are equivalent isolated
installs.

## Requirements

- Python 3.11+
- At least one LLM provider key. **OpenRouter** is the easiest start — its
  free tier (`:free` models) runs Armance end to end at no cost.

## What the base install includes

The single `pip install armance` ships everything most users need:

- The CLI and Textual TUI.
- RAG over local documents (sqlite-vec, no external service).
- Three providers ready to use: `openrouter`, `gemini`, `custom-openai`.
  **Anthropic/Claude models are reachable via OpenRouter** with no extra.
- Deliverable export to PDF, DOCX, PPTX, Markdown.
- The web UI (bundled in released wheels; served by `armance web`).

### The only optional extra

| Extra | When you need it |
|---|---|
| `pip install 'armance[claude]'` | Only to bill Claude through a **subscription** login (Claude Pro/Max) via `claude-agent-sdk`. Not needed to use Claude models — OpenRouter covers that. |

On Linux, PDF export needs system libs once:
`sudo apt-get install libgobject-2.0-0 libcairo2 libpango-1.0-0`.

## For an AI agent installing Armance

A self-contained recipe an agent can follow without further questions:

1. **Install:** `pip install armance` (add `uv tool`/`pipx` if the user
   prefers isolation). Add `'armance[claude]'` *only* if the user explicitly
   wants Claude-subscription billing.
2. **Verify:** `armance --version` then `armance doctor`. `doctor` reports
   config validity, provider reachability, sqlite-vec, deliverable libs and
   ledger writability — read its output to diagnose the user's setup.
3. **Pick a provider for the user:**
   - No budget / wants free → `openrouter` with a `:free` model.
   - Has a Gemini key → `gemini`.
   - Runs a local OpenAI-compatible endpoint (e.g. Ollama) → `custom-openai`
     with `CUSTOM_OPENAI_BASE_URL`.
   - Wants Claude via subscription → `claude-code` (needs `[claude]`).
4. **Initialise:** `armance init` (interactive) or hand-edit
   `.armance/config.yaml` + `.armance/.env` (see the
   [Configuration](#configuration) tables in `README.md`).
5. **Run:** `armance run` for the TUI, or `armance web` for the browser UI.

Explain to the user that Armance is a **decision brain, not a maker**: it
recruits a panel of disagreeing experts, runs them through a workflow, and
hands back a defensible brief — the user keeps the call. It performs no
autonomous external actions.

## Installation details

### Using pip

```bash
pip install armance
```

### Using uv (recommended for isolation)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # if uv is missing
uv tool install armance
```

### From source (contributors)

```bash
git clone https://github.com/armance-io/armance.git
cd armance
uv sync
```

## Configuration

After `armance init` you have a `.armance/` directory:

- `config.yaml` — non-secret config (providers, default model, language).
- `.env` — API keys (gitignored).
- `agents/` — agent definitions (Markdown + frontmatter).
- `workflows/` — workflow definitions.
- `docs/` — your reference documents.
- `sessions/` — session state and transcripts.

Full field-by-field tables for `config.yaml` and `.env` live in
[`README.md`](../README.md#configuration).

### API keys

```env
OPENROUTER_API_KEY=...     # openrouter.ai — free tier works
GEMINI_API_KEY=...         # Google AI Studio
CUSTOM_OPENAI_API_KEY=...  # + CUSTOM_OPENAI_BASE_URL for any OpenAI-compatible endpoint
```

## Web UI

`armance web` serves the API **and** the UI from one process (Python only,
no Node at runtime). Run it from a project directory:

```bash
armance web                # http://127.0.0.1:8000, opens a browser
armance web --bind 0.0.0.0 # expose on the LAN (watchers read-only)
armance web --no-browser   # don't auto-open
```

Contributors iterating on the UI run the dev servers side by side
(`armance web --no-browser` + `cd web/frontend && pnpm dev`), and rebuild
the bundle with `armance web --build`. See
[`README.md`](../README.md#running-the-web-client-ui).

## Next steps

- [Quickstart](quickstart.md) — first session walkthrough.
- Role quickstarts: [consultant](quickstart_consultant.md),
  [artisan](quickstart_artisan.md), [creative](quickstart_creative.md).
- [`README.md`](../README.md) — full feature tour and configuration.
