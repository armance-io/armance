# Quickstart — Consultant

Get from install to a PPTX deliverable in under 10 minutes.

## Install

```bash
uv tool install armance-ai          # or: pipx install armance-ai
armance --version                   # verify install
```

## Initialize a project

```bash
mkdir client-alpha && cd client-alpha
armance init
```

Interactive prompts:
- Select providers (e.g. `openrouter`)
- Paste API key
- Pick default model (e.g. `anthropic/claude-opus-4-7`)
- Pick judge model (same or different)

## Drop your documents

```bash
mkdir -p .armance/docs
cp ~/Downloads/client-brief.pdf .armance/docs/
cp ~/notes/meeting-2026-04.txt .armance/docs/
armance index
# index complete: indexed=2 skipped=0 deleted=0
```

## Run a brainstorm

```bash
armance run
```

Inside the TUI:

```
> /workflow run brainstorm
Workflow prompt: What are the 3 highest-leverage recommendations for Project Alpha?
[cost estimate] ~$0.38 USD over 4 step invocations
  openrouter: $0.38
Continue? (~$0.38 USD) (Y/n): y

[explore]  working...
[focus]    working...
CHECKPOINT: midpoint
Anything to adjust before synthesis? (blank to skip)
> Focus on Q3 budget constraints — client cut 20%
[confirmed] checkpoint midpoint completed
[synthesis] working...
[judge]    done
```

## Generate deliverable

```
> /deliverable pptx
```

File written to `.armance/exports/brainstorm.pptx`.

```bash
/quit
ls .armance/exports/          # brainstorm.pptx
libreoffice .armance/exports/brainstorm.pptx
```

## Resume a session next day

```bash
armance run
# Resume latest session? (Y/n): y
> /workflow run brainstorm --enrich <session-id-from-yesterday>
```

## Check system health

```bash
armance doctor
```
