from __future__ import annotations

from pathlib import Path

from armance.config import Config
from armance.core.models.agent import Agent
from armance.service.agents.recruiter_agent import RecruiterAgentService


def test_malik_recruit_saves_boost_fields(tmp_path: Path) -> None:
    # Set up RecruiterAgentService
    malik_agent = Agent(
        name="system-hr",
        role="recruiter",
        persona="recruiter",
        provider="openrouter",
        model="openai/gpt-4o-mini",
    )
    cfg = Config()
    hr = RecruiterAgentService(agent=malik_agent, armance_root=tmp_path, config=cfg)

    yaml_text = """
agents:
  - name: "Theodore"
    persona: "positivist"
    role: "historian"
    description: "Voix claire et construite"
    provider: "openrouter"
    model: "anthropic/claude-3.5-sonnet"
    boost_provider: "openrouter"
    boost_model: "anthropic/claude-opus-4-5"
"""
    agents_dir = tmp_path / "agents"
    created, names = hr.recruit_agents(yaml_text, "historian", agents_dir)

    assert len(created) == 1
    assert "Theodore" in names

    # Load agent from disk and assert boost fields are preserved
    agent_path = agents_dir / "Theodore.md"
    assert agent_path.exists()

    loaded = Agent.load(agent_path)
    assert loaded.boost_provider == "openrouter"
    assert loaded.boost_model == "anthropic/claude-opus-4-5"  # normalised!
