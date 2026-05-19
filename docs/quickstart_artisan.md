# Quickstart — Artisan / Tradesperson

Use Armance to generate structured feasibility reports from technical briefs, norms, and client specs.

## Install

One-liner (requires Python ≥ 3.11):

```bash
curl -sSL https://raw.githubusercontent.com/armance-io/armance/main/install.sh | sh
```

Or manually with `pipx` or `uv`:

```bash
pipx install armance-ai          # recommended: isolated env, auto PATH
# or
uv tool install armance-ai
armance --version                # verify
```

## Initialize a project

```bash
mkdir renovation-project && cd renovation-project
armance init
```

Interactive prompts:
- Select providers (e.g. `openrouter`)
- Paste API key (get one at openrouter.ai)
- Pick default model (e.g. `anthropic/claude-sonnet-4-6`)
- Pick judge model (same is fine)

## Drop your documents

```bash
mkdir -p .armance/docs
cp ~/Downloads/client-brief.pdf .armance/docs/
cp ~/norms/NF-C15100.pdf .armance/docs/
cp ~/quotes/supplier-quote.docx .armance/docs/
armance index
# index complete: indexed=3 skipped=0 deleted=0
```

## Run a feasibility brainstorm

```bash
armance run
```

Inside the TUI:

```
> /workflow run brainstorm
Workflow prompt: Is this kitchen renovation feasible for €15k? What are the risks?
[cost estimate] ~$0.31 USD over 4 step invocations
  openrouter: $0.31
Continue? (~$0.31 USD) (Y/n): y

[explore]  working...
[focus]    working...
CHECKPOINT: midpoint
Anything to adjust before synthesis? (blank to skip)
> Client wants to keep existing electrical panel — factor in the constraints
[confirmed] checkpoint midpoint completed
[synthesis] working...
[judge]    done
```

## Generate a client deliverable

```
> /deliverable docx
```

File written to `.armance/exports/brainstorm.docx` — ready to hand to the client.

Or as PDF:

```
> /deliverable pdf
```

## Check system health

```bash
armance doctor
```

## Resume a session next day

```bash
armance run
# Resume latest session? (Y/n): y
```

## Tips for tradespeople

- Drop supplier quotes as PDF or DOCX — Armance reads them as context
- Ask the brainstorm to produce a numbered list of risks and a go/no-go recommendation
- Use `/deliverable pptx` to produce slides for a client presentation
- The judge agent always synthesizes across all viewpoints — you get one clear verdict
