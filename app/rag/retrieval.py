from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings
from app.db.repository import repository
from app.infra.llm import EmbeddingClient, RerankClient
from app.infra.milvus import milvus_client


@dataclass
class RetrievedChunk:
    id: str
    kb_id: str | None
    doc_id: str | None
    content: str
    score: float
    channel: str


def _score(query: str, content: str) -> float:
    query_terms = {term.lower() for term in query.split() if term.strip()}
    content_lower = content.lower()
    if not query_terms:
        return 0.0
    hits = sum(1 for term in query_terms if term in content_lower)
    if query and query.lower() in content_lower:
        hits += 2
    return hits / (len(query_terms) + 2)


class RetrievalEngine:
    def __init__(self) -> None:
        self.embedding_client = EmbeddingClient()
        self.rerank_client = RerankClient()

    async def retrieve_async(self, sub_intents: list[dict], top_k: int = 5) -> dict:
        query = " ".join(item["subQuestion"] for item in sub_intents if item.get("kind") == "kb")
        candidates: list[RetrievedChunk] = []
        if query:
            embedding = await self.embedding_client.embed(query)
            vector_rows = []
            if settings.vector_provider == "milvus":
                vector_rows = await milvus_client.search("rag_default_store", embedding, top_k=top_k * 3)
            if not vector_rows:
                vector_rows = repository.search_vectors(embedding, query, top_k=top_k * 3)
            for row in vector_rows:
                metadata = row.get("metadata") or {}
                content = row.get("content") or ""
                candidates.append(
                    RetrievedChunk(
                        id=str(row["id"]),
                        kb_id=metadata.get("kb_id"),
                        doc_id=metadata.get("doc_id"),
                        content=content,
                        score=float(row.get("score") or 0),
                        channel=row.get("channel", "pgvector"),
                    )
                )
        for chunk in repository.list_chunks(limit=300):
            content = chunk.get("content") or ""
            score = _score(query, content)
            if score > 0:
                candidates.append(
                    RetrievedChunk(
                        id=str(chunk["id"]),
                        kb_id=chunk.get("kbId"),
                        doc_id=chunk.get("docId"),
                        content=content,
                        score=score,
                        channel="keyword-fallback",
                    )
                )
        deduped: dict[str, RetrievedChunk] = {}
        for item in sorted(candidates, key=lambda c: c.score, reverse=True):
            key = item.content.strip()
            if key and key not in deduped:
                deduped[key] = item
        chunks = list(deduped.values())
        rerank_order = await self.rerank_client.rerank(query, [chunk.content for chunk in chunks])
        ordered = [chunks[idx] for idx in rerank_order if 0 <= idx < len(chunks)]
        chunks = (ordered or chunks)[:top_k]
        return {
            "chunks": chunks,
            "kbContext": "\n\n".join(f"[{idx + 1}] {chunk.content}" for idx, chunk in enumerate(chunks)),
            "mcpContext": "",
            "hasKb": bool(chunks),
            "hasMcp": False,
        }

    def retrieve(self, sub_intents: list[dict], top_k: int = 5) -> dict:
        import asyncio

        return asyncio.run(self.retrieve_async(sub_intents, top_k))
