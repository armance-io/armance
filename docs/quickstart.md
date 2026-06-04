# Armance — Quickstart Guide

This guide walks you through the Phase 1 end-to-end use case (P1-UC).

## Prerequisites

- Python 3.11+
- `armance` installed (see [Installation](install.md))

## Step 1: Initialize

```bash
mkdir my-project && cd my-project
armance init
```

Select providers (e.g., openrouter) and configure your default model.

## Step 2: Start Armance

```bash
armance run
```

You'll see the welcome message from `system-context`.

## Step 3: Describe Your Project

Type: "I want to build a custom oak coffee table."

The context agent will:
- Understand your project domain (woodworking, design)
- Suggest poles (woodworking, design)
- Generate 3 agents per pole (audacious, prudent, balanced)

## Step 4: Switch to a Specialist

Type: `/switch woodworking-lina`

Now you're chatting with a woodworking specialist.

## Step 5: Ask a Question

Type: "Compare 3 joinery options for the apron-to-leg connection."

The agent will provide a detailed response.

## Step 6: Save Context

Type: `/save`

This freezes the conversation as L0 v1 in `.armance/context/`.

## Step 7: Quit and Resume

Type: `/quit`

Run `armance run` again. You'll be prompted to resume the latest session.

Select "Yes" and you'll see:
- Your previous context summary
- The current agent
- Accumulated token budget

## What You've Built

By completing this walkthrough, you've:
- Created a project with Armance
- Built shared context (L0)
- Used multiple agents for different domains
- Saved and resumed sessions
- Tracked token usage and costs

## Next Steps

- Try the end-to-end [scenarios](../SCENARIOS.md) for more detail
- Launch the web UI with `armance web` (see [install guide](install.md#web-ui))
- Add more documents to `.armance/docs/` for RAG context
