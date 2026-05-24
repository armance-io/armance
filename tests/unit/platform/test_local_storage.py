"""J.1 — LocalFilesystemStorage tests.

Written RED before the implementation exists.  Spec:
issues/features/web-j-platform-abstractions.md § J.1

Acceptance criteria from the spec:
- write_text("a/b.txt", "hi") creates <root>/a/b.txt with that content.
- read_text("a/b.txt") returns "hi".
- exists("a/b.txt") is True; exists("missing") is False.
- list("a/") returns ["a/b.txt"].
- delete("a/b.txt") removes it; subsequent read_text raises.
- Path traversal ("../../etc/passwd") raises ValueError.
"""
from __future__ import annotations

import json
import pytest
from pathlib import Path


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def storage(tmp_path: Path):
    from armance.platform.storage import LocalFilesystemStorage
    return LocalFilesystemStorage(root=tmp_path)


# ---------------------------------------------------------------------------
# write_text / read_text round-trip
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_write_and_read_text(storage) -> None:
    await storage.write_text("a/b.txt", "hi")
    result = await storage.read_text("a/b.txt")
    assert result == "hi"


@pytest.mark.asyncio
async def test_write_text_creates_parent_dirs(storage, tmp_path: Path) -> None:
    await storage.write_text("deep/nested/file.txt", "content")
    assert (tmp_path / "deep" / "nested" / "file.txt").exists()


@pytest.mark.asyncio
async def test_write_and_read_bytes(storage) -> None:
    data = b"\x00\x01\x02\x03"
    await storage.write_bytes("binary/data.bin", data)
    result = await storage.read_bytes("binary/data.bin")
    assert result == data


# ---------------------------------------------------------------------------
# exists
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_exists_true_after_write(storage) -> None:
    await storage.write_text("a/b.txt", "hi")
    assert await storage.exists("a/b.txt") is True


@pytest.mark.asyncio
async def test_exists_false_for_missing(storage) -> None:
    assert await storage.exists("missing/key") is False


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_prefix(storage) -> None:
    await storage.write_text("a/b.txt", "hi")
    result = await storage.list("a/")
    assert result == ["a/b.txt"]


@pytest.mark.asyncio
async def test_list_multiple_files(storage) -> None:
    await storage.write_text("proj/s1/state.json", "{}")
    await storage.write_text("proj/s2/state.json", "{}")
    result = sorted(await storage.list("proj/"))
    assert result == ["proj/s1/state.json", "proj/s2/state.json"]


@pytest.mark.asyncio
async def test_list_empty_prefix(storage) -> None:
    result = await storage.list("nonexistent/")
    assert result == []


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_removes_file(storage) -> None:
    await storage.write_text("a/b.txt", "hi")
    assert await storage.exists("a/b.txt") is True
    await storage.delete("a/b.txt")
    assert await storage.exists("a/b.txt") is False


@pytest.mark.asyncio
async def test_read_after_delete_raises(storage) -> None:
    await storage.write_text("a/b.txt", "hi")
    await storage.delete("a/b.txt")
    with pytest.raises(Exception):
        await storage.read_text("a/b.txt")


@pytest.mark.asyncio
async def test_delete_missing_is_silent(storage) -> None:
    """Deleting a non-existent key must not raise."""
    await storage.delete("does/not/exist.txt")


# ---------------------------------------------------------------------------
# Path traversal guard
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_traversal_raises_on_write_text(storage) -> None:
    with pytest.raises(ValueError):
        await storage.write_text("../../etc/passwd", "evil")


@pytest.mark.asyncio
async def test_traversal_raises_on_read_text(storage) -> None:
    with pytest.raises(ValueError):
        await storage.read_text("../../etc/passwd")


@pytest.mark.asyncio
async def test_traversal_raises_on_write_bytes(storage) -> None:
    with pytest.raises(ValueError):
        await storage.write_bytes("../../etc/passwd", b"evil")


@pytest.mark.asyncio
async def test_traversal_raises_on_read_bytes(storage) -> None:
    with pytest.raises(ValueError):
        await storage.read_bytes("../../etc/passwd")


@pytest.mark.asyncio
async def test_traversal_raises_on_exists(storage) -> None:
    with pytest.raises(ValueError):
        await storage.exists("../../etc/passwd")


@pytest.mark.asyncio
async def test_traversal_raises_on_delete(storage) -> None:
    with pytest.raises(ValueError):
        await storage.delete("../../etc/passwd")


# ---------------------------------------------------------------------------
# read_jsonl
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_read_jsonl_returns_dicts(storage) -> None:
    lines = [{"name": "event.one"}, {"name": "event.two"}]
    content = "\n".join(json.dumps(l) for l in lines) + "\n"
    await storage.write_text("events/log.jsonl", content)
    results = []
    async for item in storage.read_jsonl("events/log.jsonl"):
        results.append(item)
    assert results == lines


@pytest.mark.asyncio
async def test_read_jsonl_skips_empty_lines(storage) -> None:
    content = '{"a": 1}\n\n{"b": 2}\n'
    await storage.write_text("events/log.jsonl", content)
    results = []
    async for item in storage.read_jsonl("events/log.jsonl"):
        results.append(item)
    assert len(results) == 2
