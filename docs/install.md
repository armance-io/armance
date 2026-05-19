# Armance — Installation Guide

## Quick Start

```bash
# Install via uv
uv tool install armance

# Or via pip
pip install armance

# Initialize a new project
armance init

# Run Armance
armance run
```

## Requirements

- Python 3.11+
- uv (recommended) or pip

## Installation

### Using uv (recommended)

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install armance
uv tool install armance
```

### Using pip

```bash
pip install armance
```

### From source

```bash
git clone https://github.com/your-org/armance.git
cd armance
uv sync
uv run armance --help
```

## Configuration

After running `armance init`, you'll have a `.armance/` directory with:

- `config.yaml` — Provider and model configuration
- `.env` — API keys (gitignored)
- `agents/` — Agent definitions
- `workflows/` — Workflow definitions
- `docs/` — Project documents
- `sessions/` — Session state and transcripts

### API Keys

API keys are stored in `.armance/.env`:

```env
OPENROUTER_API_KEY=your_key_here
GEMINI_API_KEY=your_key_here
```

## First Run

1. Run `armance init` in your project directory
2. Select providers and configure models
3. Run `armance run` to start the TUI
4. Type your project description to begin

## Next Steps

- See the [Quickstart Guide](quickstart.md) for a step-by-step walkthrough
- Check out the [Scenarios](spec/13_scenarios.md) for end-to-end examples
- Read the [Specification](spec/README.md) for technical details
