import asyncio
from armance.core.models.agent import Agent
from armance.service.tui_bridge import META_AGENTS
from armance import paths

for slug, first_name, _role in META_AGENTS:
    path = paths.global_agents_dir() / f"{slug}.md"
    print(f"Checking {path}")
    if path.exists():
        try:
            agent = Agent.load(path)
            print(f"Loaded {agent.name}")
        except Exception as e:
            print(f"Error loading {path}: {e}")
    else:
        print(f"Not found: {path}")
