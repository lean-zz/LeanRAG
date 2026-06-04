from __future__ import annotations

import hashlib
from typing import Any

import httpx

from app.core.config import settings
from app.core.ids import new_id
from app.db.repository import repository
from app.infra.llm import EmbeddingClient
from app.infra.milvus import milvus_client
from app.infra.object_storage import object_storage
from app.ingestion.pipeline import split_text


class KnowledgeIngestionService:
    def __init__(self) -> None:
        self.embedding_client = EmbeddingClient()

    async def ingest_upload(
        self,
        kb_id: str,
        doc_name: str,
        content: bytes,
        file_type: str,
        file_size: int | None,
        created_by: str,
        source_location: str | None = None,
        chunk_size: int = 800,
        overlap: int = 120,
    ) -> dict[str, Any]:
        text = self._decode(content)
        doc_id = new_id()
        object_key = f"knowledge/{kb_id}/{doc_id}/{doc_name}"
        file_url = object_storage.put_bytes(settings.object_storage_bucket, object_key, content, self._content_type(file_type))
        chunks: list[dict[str, Any]] = []
        for index, chunk_text in enumerate(split_text(text, chunk_size=chunk_size, overlap=overlap)):
            if not chunk_text.strip():
                continue
            chunk_id = new_id()
            embedding = await self.embedding_client.embed(chunk_text)
            chunks.append(
                {
                    "id": chunk_id,
                    "kbId": kb_id,
                    "docId": doc_id,
                    "chunkIndex": index,
                    "content": chunk_text,
                    "contentHash": hashlib.sha256(chunk_text.encode("utf-8")).hexdigest(),
                    "charCount": len(chunk_text),
                    "tokenCount": max(1, len(chunk_text) // 4),
                    "enabled": 1,
                    "createdBy": created_by,
                    "embedding": embedding,
                }
            )
        document = {
            "id": doc_id,
            "kbId": kb_id,
            "docName": doc_name,
            "sourceType": "url" if source_location else "file",
            "sourceLocation": source_location,
            "fileUrl": file_url or source_location or "",
            "fileType": file_type,
            "fileSize": file_size,
            "status": "completed" if chunks else "failed",
            "chunkCount": len(chunks),
            "createdBy": created_by,
        }
        doc = repository.create_document_with_chunks(document, chunks)
        collection_name = self._collection_name(kb_id)
        repository.upsert_vectors(collection_name, doc_id, chunks)
        if settings.vector_provider == "milvus":
            await milvus_client.upsert(collection_name, chunks)
        doc["chunkCount"] = len(chunks)
        doc["status"] = document["status"]
        return doc

    async def ingest_url(self, kb_id: str, url: str, created_by: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
            response = await client.get(url)
            response.raise_for_status()
            content = response.content
        doc_name = url.rstrip("/").rsplit("/", 1)[-1] or "remote-document"
        return await self.ingest_upload(kb_id, doc_name, content, "txt", len(content), created_by, source_location=url)

    def _decode(self, content: bytes) -> str:
        for encoding in ("utf-8", "gb18030", "latin-1"):
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue
        return content.decode("utf-8", errors="ignore")

    def _collection_name(self, kb_id: str) -> str:
        for kb in repository.list_knowledge_bases():
            if kb.get("id") == kb_id:
                return kb.get("collectionName") or f"kb_{kb_id}"
        return f"kb_{kb_id}"

    def _content_type(self, file_type: str) -> str:
        return {
            "txt": "text/plain",
            "md": "text/markdown",
            "json": "application/json",
            "pdf": "application/pdf",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }.get(file_type.lower().lstrip("."), "application/octet-stream")
