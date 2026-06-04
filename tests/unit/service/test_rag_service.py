import pytest
from armance.storage.rag_index import RagService
from armance.service.events import LocalEventBus

@pytest.fixture
def tmp_armance(tmp_path):
    armance_root = tmp_path / ".armance"
    armance_root.mkdir()
    return armance_root

@pytest.fixture
def event_bus(tmp_armance):
    return LocalEventBus(tmp_armance / "sessions" / "test-sid")

@pytest.mark.asyncio
async def test_ingest_and_query(tmp_armance, event_bus):
    doc_path = tmp_armance / "test.md"
    doc_path.write_text("Lorem ipsum dolor sit amet, consectetur adipiscing elit.")
    
    rag = RagService(tmp_armance, event_bus)
    chunks_inserted = await rag.ingest(doc_path)
    assert chunks_inserted == 1
    
    results = await rag.query("ipsum dolor", top_k=5)
    assert len(results) == 1
    assert "Lorem ipsum" in results[0].text
    
@pytest.mark.asyncio
async def test_query_excluding(tmp_armance, event_bus):
    doc1 = tmp_armance / "doc1.md"
    doc1.write_text("First document content.")
    
    doc2 = tmp_armance / "doc2.md"
    doc2.write_text("Second document content.")
    
    rag = RagService(tmp_armance, event_bus)
    await rag.ingest(doc1)
    await rag.ingest(doc2)
    
    results = await rag.query_excluding("content", top_k=5, exclude_ids=["doc1.md"])
    assert len(results) == 1
    assert results[0].source == "doc2.md"

def test_legacy_chroma_detection(tmp_armance, event_bus):
    legacy = tmp_armance / "vector"
    legacy.mkdir(parents=True)
    
    rag = RagService(tmp_armance, event_bus)
    assert rag.db_path.exists()
