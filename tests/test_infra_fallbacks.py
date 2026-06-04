from __future__ import annotations

import pytest

from app.infra.milvus import milvus_client
from app.infra.object_storage import object_storage


def test_rustfs_unavailable_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(object_storage, "_client", None)
    assert object_storage.put_bytes("ragent", "test/doc.txt", b"hello", "text/plain") is None


@pytest.mark.asyncio
async def test_milvus_unavailable_returns_empty_results(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(milvus_client, "_connected", False)
    monkeypatch.setattr(milvus_client, "uri", "http://127.0.0.1:1")
    results = await milvus_client.search("missing_collection", [0.1, 0.2, 0.3], 3)
    assert results == []
