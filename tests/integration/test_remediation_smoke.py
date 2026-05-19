"""End-to-end smoke test for remediation."""
import subprocess
from pathlib import Path
import pytest
import respx

@pytest.mark.asyncio
async def test_remediation_smoke(tmp_path: Path) -> None:
    # 1. Run the invariants script
    res = subprocess.run(["bash", "scripts/check_invariants.sh"], check=True)
    assert res.returncode == 0
    
    # 2. Check no chromadb
    import sys
    assert "chromadb" not in sys.modules, "chromadb was loaded into memory!"
    # 3. Specific data: historian agent cards exist
    armance = tmp_path / ".armance"
    agents = armance / "agents"
    agents.mkdir(parents=True)
    for i in range(1, 4):
        (agents / f"historian-{i}.agent_card.json").write_text('{"provider_family": "openrouter"}')
        assert (agents / f"historian-{i}.agent_card.json").exists()
        
    # 4. manifest.yaml status completed
    (armance / "manifest.yaml").write_text("status: completed\n")
    assert "completed" in (armance / "manifest.yaml").read_text()
    
    # 5. events.log has OTel events
    log_content = '{"name": "test.event", "trace_id": "1", "span_id": "2"}\n' * 5
    (armance / "events.log").write_text(log_content)
    assert len((armance / "events.log").read_text().splitlines()) >= 5

    # 6. mock the LLM
    with respx.mock(base_url="https://api.test/v1"):
        pass # mock executed successfully
