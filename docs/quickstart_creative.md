# Quickstart — Creative (Author / Screenwriter)

Use Armance to run a structured critique panel on your manuscript or outline.

## Install

```bash
uv tool install armance-ai
armance --version
```

## Initialize

```bash
mkdir my-novel && cd my-novel
armance init
# Select providers: openrouter
# Model: anthropic/claude-sonnet-4-6
```

## Drop your manuscript

```bash
mkdir -p .armance/docs
cp ~/writing/chapter-draft.md .armance/docs/
cp ~/writing/outline.pdf .armance/docs/
armance index
```

## Run a critique brainstorm

```bash
armance run
```

Inside the TUI:

```
> /workflow run brainstorm
Workflow prompt: Critique the pacing and character arc in chapter 3 — is the protagonist's decision believable?
[cost estimate] ~$0.22 USD
Continue? (Y/n): y

[explore]  working...
[focus]    working...
CHECKPOINT: midpoint
Anything to refocus? (blank to skip)
> Emphasize the subplot with the sister — I think it's underdeveloped
[synthesis] working...
[judge]    done
```

## Read the synthesis

```
> /judge @judge/judge_v1.md
```

## Export notes as Markdown

```
> /deliverable md
```

File in `.armance/exports/brainstorm.md` — paste into your writing app.

## Talk to one agent

```
> /switch balanced
> What would you cut from chapter 3 to tighten the pacing by 20%?
```

## Iterate

Each session is saved. Return tomorrow:

```bash
armance run
# Resume latest session? (Y/n): y
```
