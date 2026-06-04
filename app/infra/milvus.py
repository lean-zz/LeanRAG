from __future__ import annotations

from app.core.config import settings


class MilvusClient:
    def __init__(self) -> None:
        self.uri = settings.milvus_uri
        self._connected = False

    def available(self) -> bool:
        try:
            import pymilvus  # type: ignore  # pragma: no cover

            return True
        except Exception:
            return False

    async def search(self, collection_name: str, embedding: list[float], top_k: int) -> list[dict]:
        if not embedding:
            return []
        try:
            self._connect()
            from pymilvus import Collection, utility  # type: ignore

            if not utility.has_collection(collection_name):
                return []
            collection = Collection(collection_name)
            collection.load()
            hits = collection.search(
                data=[embedding],
                anns_field="embedding",
                param={"metric_type": "COSINE", "params": {"nprobe": 10}},
                limit=top_k,
                output_fields=["content", "metadata", "kb_id", "doc_id"],
            )
            results: list[dict] = []
            for hit in hits[0] if hits else []:
                entity = getattr(hit, "entity", None)
                metadata = self._field(entity, "metadata") or {}
                kb_id = self._field(entity, "kb_id") or metadata.get("kb_id")
                doc_id = self._field(entity, "doc_id") or metadata.get("doc_id")
                results.append(
                    {
                        "id": str(hit.id),
                        "content": self._field(entity, "content") or "",
                        "metadata": {"kb_id": kb_id, "doc_id": doc_id, **metadata},
                        "score": float(getattr(hit, "score", 0) or 0),
                        "channel": "milvus",
                    }
                )
            return results
        except Exception:
            return []

    async def upsert(self, collection_name: str, chunks: list[dict]) -> None:
        rows = [chunk for chunk in chunks if chunk.get("embedding")]
        if not rows:
            return
        try:
            self._connect()
            from pymilvus import Collection, utility  # type: ignore

            if not utility.has_collection(collection_name):
                return
            collection = Collection(collection_name)
            collection.upsert(
                [
                    [row["id"] for row in rows],
                    [row["embedding"] for row in rows],
                    [row.get("content", "") for row in rows],
                    [{"kb_id": row.get("kbId"), "doc_id": row.get("docId"), "chunk_index": row.get("chunkIndex", 0)} for row in rows],
                    [row.get("kbId") for row in rows],
                    [row.get("docId") for row in rows],
                ]
            )
            collection.flush()
        except Exception:
            return None

    def _connect(self) -> None:
        if self._connected:
            return
        from pymilvus import connections  # type: ignore

        connections.connect(uri=self.uri)
        self._connected = True

    def _field(self, entity: object | None, name: str):
        if entity is None:
            return None
        try:
            return entity.get(name)
        except Exception:
            return None


milvus_client = MilvusClient()
