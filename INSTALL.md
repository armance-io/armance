# Installing Armance

> The fastest path to a working Armance on **Windows, macOS, or Linux** —
> by hand or by handing this file to an AI coding agent.
>
> **Agent prompt that just works:** *"Install Armance for me from the
> repo `armance-io/armance` by following its `INSTALL.md`."* An agent
> (Claude Code, Cursor, Cowork, …) can read this file and run every step
> below unattended.

---

## TL;DR — the one command

```bash
pip install armance
```

Then:

```bash
armance --version          # confirm it installed
armance doctor             # check config, providers, sqlite-vec, deliverables
```

That single install gives you the **full CLI + TUI**, RAG over your
documents, **all four LLM providers**, DOCX / PPTX / Markdown
deliverables, the **web UI**, and the **environmental-footprint** tracking
(CO₂e + water per prompt). The only opt-in extra is **PDF export** (needs
native libraries) — see [PDF export](#optional-pdf-export).

---

## 1. Prerequisites

| Requirement | Why | Check |
|---|---|---|
| **Python ≥ 3.11** | runtime | `python --version` (or `python3 --version`) |
| **One LLM provider key** | Armance calls an LLM | see [Get a key](#3-get-a-provider-key) |
| Node + pnpm | **only** for a git checkout that must build the web UI | `node -v`, `pnpm -v` |

> **OpenRouter is the easiest start** — its free tier runs Armance
> end-to-end with **no spend**.

### Installing Python (if you don't have 3.11+)

- **Windows** — download from [python.org/downloads](https://www.python.org/downloads/);
  tick *"Add python.exe to PATH"* in the installer.
- **macOS** — `brew install python@3.12` (or python.org installer).
- **Linux** — `sudo apt install python3 python3-pip` (Debian/Ubuntu) or your
  distro's equivalent; most distros already ship 3.11+.

---

## 2. Install Armance

Pick **one** method.

### A. pip (recommended — from PyPI)

```bash
pip install armance
```

> **Want the V2 web UI + footprint tracking now?** Those ship in the
> **beta** line. PyPI's current *stable* is `0.1.0`; pip skips
> pre-releases by default, so to get the latest beta use:
> ```bash
> pip install --pre armance
> ```

### B. Isolated tool install (keeps Armance off your global site-packages)

```bash
uv tool install armance     # if you have uv
# or
pipx install armance        # if you have pipx
```

Both put a global `armance` command on your `PATH` and work identically to
the pip install.

### C. From git (latest dev — CLI only, UI must be built)

```bash
pip install "git+https://github.com/armance-io/armance.git"
```

> A git install ships the CLI but **not** the prebuilt web UI — the bundle
> is a build artifact, not tracked in git. To get the UI from a git
> install, clone the repo and run `armance web --build` once (needs Node +
> pnpm), or use a PyPI release wheel where the UI is already bundled.

### Verify (all methods)

```bash
armance --version
armance doctor
```

`armance doctor` reports config, provider reachability, sqlite-vec, the
deliverable toolchain, and the ledger — a green run means you're ready.

---

## 3. Get a provider key

Armance needs **at least one** of these. You set them during `armance init`
(next section); they live in `.armance/.env` (gitignored).

| Provider | Key env var | Where to get it | Notes |
|---|---|---|---|
| **OpenRouter** | `OPENROUTER_API_KEY` | [openrouter.ai](https://openrouter.ai) | **Easiest.** Many `:free` models — zero spend to start. |
| **Claude (subscription)** | bundled `claude-code` SDK auth | Claude Pro/Max plan | No extra to install; subscription = effectively free per use. |
| **Gemini** | `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com) | |
| **Custom OpenAI-compatible** | `CUSTOM_OPENAI_API_KEY` + `CUSTOM_OPENAI_BASE_URL` | your endpoint (e.g. Ollama `http://localhost:11434/v1`) | Any OpenAI-compatible API. |

---

## 4. First project (quickstart)

```bash
mkdir my-project && cd my-project
armance init        # interactive: providers, model, budget, language, CO₂ zone
```

`armance init` walks you through:

1. **Providers** — multi-select from the four above.
2. **API keys** — stored in `.armance/.env`.
3. **Default provider + model**.
4. **Budget effort** — `free-first` / `low` / `medium` / `high` / `adaptive`
   / `optimised` (greenest-model-first carbon routing).
5. **Interface language** — EN / FR / ES / DE / ZH / JA (auto-detected from
   `$LANG`). Every agent replies in this language.
6. **Embedding model** — for RAG; can be skipped and set later.
7. **Electricity zone** — for the CO₂ footprint estimate (e.g. `FRA`, `WOR`).

Then drop documents into `.armance/docs/` and start:

```bash
armance run         # opens the TUI
# or
armance web         # opens the web UI in your browser
```

---

## 5. The web UI

```bash
armance web         # serves API + UI at http://127.0.0.1:8000, opens a browser
```

One command runs **both** the API and the UI in a single process — no Node,
no second server (for a PyPI install). It backgrounds by default; stop it
with `armance web --stop`.

### Security: it asks for a passcode

> **Availability:** the web access-control gate described here is on the
> `feat/web-security-gate` branch and lands in a forthcoming beta. On
> older releases `armance web` runs without a passcode — bind it to
> localhost only until you're on a build that includes the gate.

When you run `armance web`, the interface is **access-controlled** so that
nobody else on your machine or LAN can read your sessions:

- If you set no password, Armance **auto-generates a token** at boot and
  prints a ready-to-click URL:

  ```
  [SECURITY] Web interface access token: <token>
  [SECURITY] Access the UI via: http://127.0.0.1:8000/?token=<token>
  ```

  Click that URL and you're logged in (the token is stripped from the
  address bar automatically).

- To set a **persistent password** instead, put `web.password` in
  `.armance/config.yaml`, or export `ARMANCE_WEB_PASSWORD`. A configured
  password is never shown in any URL.

> Exposing the UI to your LAN? Use `armance web --bind 0.0.0.0`. The
> passcode gate protects every data route; for the public internet, put it
> behind an HTTPS reverse proxy (Nginx / Caddy).

---

## Optional: PDF export

Every export format works out of the box **except PDF**. PDF uses
WeasyPrint, which needs native libraries pip cannot install — so it is
opt-in:

```bash
pip install "armance[pdf]"
```

Then install the native libs for your OS:

- **Linux:** `sudo apt-get install libgobject-2.0-0 libcairo2 libpango-1.0-0`
- **macOS:** `brew install pango` (often already present)
- **Windows:** install the GTK runtime — see the
  [WeasyPrint install guide](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#installation).

DOCX / PPTX / Markdown need none of this. If WeasyPrint is missing,
`armance` simply skips PDF with a clear message — it never crashes.

---

## Letting an agent install it for you

This file is written so an AI coding agent can do the whole job. A working
prompt:

> *"Install Armance from `github.com/armance-io/armance`. Read its
> `INSTALL.md` and follow it: check my Python is ≥ 3.11, run
> `pip install armance`, verify with `armance --version` and
> `armance doctor`, then create a project folder and run `armance init`.
> Ask me for an OpenRouter API key when needed."*

The agent should:

1. Verify Python ≥ 3.11 (`python --version`).
2. Run `pip install armance` (or `uv tool install armance` / `pipx install armance`).
3. Verify with `armance --version` and `armance doctor`.
4. `mkdir` a project, `cd` into it, run `armance init` (it will need your
   provider key — OpenRouter is the easy default).
5. Start with `armance web` (or `armance run` for the terminal UI).

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `armance: command not found` after `pip install` | The script dir isn't on `PATH`. Use `python -m armance …`, or prefer `pipx`/`uv tool install` which manage `PATH`. |
| *"no bundled UI found — running API only"* | You used a git/editable install. Run `armance web --build` from a repo **clone**, or install a PyPI release wheel. |
| `armance web` says the port is in use / already running | Only one web instance per folder. `armance web --stop`, then retry. |
| PDF export does nothing | Install `armance[pdf]` + the native libs above. DOCX/PPTX/MD always work. |
| Provider call fails | Re-run `armance doctor`; check the key in `.armance/.env` and that the provider is reachable. |

---

## Contributor / dev setup

```bash
git clone https://github.com/armance-io/armance.git
cd armance
uv sync
uv run armance web --build      # builds the UI bundle once, then serves
```

> An editable install lives in the project's `.venv` and is **not** on your
> `PATH` — run the CLI with `uv run armance …`. See
> [`web/DEVELOPMENT.md`](web/DEVELOPMENT.md) for the full dev loop.
</content>
</invoke>
