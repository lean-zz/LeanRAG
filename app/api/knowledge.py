from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.core.auth import LoginUser, current_user
from app.core.ids import new_id
from app.core.responses import page, success
from app.db.repository import repository
from app.knowledge.ingestion import KnowledgeIngestionService

router = APIRouter()
ingestion_service = KnowledgeIngestionService()


@router.get("/knowledge-base/chunk-strategies")
async def chunk_strategies(user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    return success([
        {"value": "recursive", "label": "递归切分", "defaultConfig": {"chunkSize": 800, "chunkOverlap": 120}},
        {"value": "paragraph", "label": "段落切分", "defaultConfig": {"chunkSize": 1000, "chunkOverlap": 100}},
    ])


@router.get("/knowledge-base")
async def knowledge_bases(current: int = 1, size: int = 10, name: str | None = None, user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    records = repository.list_knowledge_bases()
    if name:
        records = [r for r in records if name in r.get("name", "")]
    return success(page(records, current, size))


@router.post("/knowledge-base")
async def create_knowledge_base(payload: dict[str, Any], user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    item = repository.create_knowledge_base({"name": payload.get("name"), "embeddingModel": payload.get("embeddingModel", "qwen-emb-8b"), "collectionName": payload.get("collectionName") or f"kb_{new_id()}", "createdBy": user.user_id})
    return success(item["id"])


@router.get("/knowledge-base/{kb_id}")
async def get_knowledge_base(kb_id: str, user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    return success(repository.get_knowledge_base(kb_id))


@router.put("/knowledge-base/{kb_id}")
async def update_knowledge_base(kb_id: str, payload: dict[str, Any], user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    repository.update_knowledge_base(kb_id, payload)
    return success()


@router.delete("/knowledge-base/{kb_id}")
async def delete_knowledge_base(kb_id: str, user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    repository.delete_knowledge_base(kb_id)
    return success()


@router.post("/knowledge-base/{kb_id}/docs/upload")
async def upload_document(
    kb_id: str,
    sourceType: str = Form("file"),
    file: UploadFile | None = File(None),
    sourceLocation: str | None = Form(None),
    scheduleEnabled: bool | None = Form(None),
    scheduleCron: str | None = Form(None),
    processMode: str = Form("chunk"),
    chunkStrategy: str | None = Form(None),
    chunkConfig: str | None = Form(None),
    pipelineId: str | None = Form(None),
    user: LoginUser = Depends(current_user),
) -> dict[str, Any]:
    if sourceType == "url" and sourceLocation:
        doc = await ingestion_service.ingest_url(kb_id, sourceLocation, user.user_id)
    else:
        raw = await file.read() if file else b""
        filename = file.filename if file else sourceLocation or "document.txt"
        file_type = filename.rsplit(".", 1)[-1] if "." in filename else "txt"
        doc = await ingestion_service.ingest_upload(kb_id, filename, raw, file_type, len(raw), user.user_id)
        doc.update({"scheduleEnabled": scheduleEnabled, "scheduleCron": scheduleCron, "processMode": processMode, "chunkStrategy": chunkStrategy, "chunkConfig": chunkConfig, "pipelineId": pipelineId})
    return success(doc)


@router.get("/knowledge-base/{kb_id}/docs")
async def documents(kb_id: str, current: int = 1, size: int = 10, status: str | None = None, keyword: str | None = None, user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    return success(repository.list_documents(kb_id, current, size, status, keyword))


@router.get("/knowledge-base/docs/search")
async def search_documents(keyword: str, limit: int = 8, user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    return success(repository.search_documents(keyword, limit))


@router.get("/knowledge-base/docs/{doc_id}")
async def get_document(doc_id: str, user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    return success(repository.get_document(doc_id))


@router.put("/knowledge-base/docs/{doc_id}")
async def update_document(doc_id: str, payload: dict[str, Any], user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    repository.update_document(doc_id, payload)
    return success()


@router.post("/knowledge-base/docs/{doc_id}/chunk")
async def chunk_document(doc_id: str, user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    repository.chunk_document(doc_id, user.user_id)
    return success()


@router.delete("/knowledge-base/docs/{doc_id}")
async def delete_document(doc_id: str, user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    repository.delete_document(doc_id)
    return success()


@router.get("/knowledge-base/docs/{doc_id}/chunks")
async def chunks(doc_id: str, current: int = 1, size: int = 10, enabled: int | None = None, user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    return success(repository.list_document_chunks(doc_id, current, size, enabled))


@router.post("/knowledge-base/docs/{doc_id}/chunks")
async def create_chunk(doc_id: str, payload: dict[str, Any], user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    return success(repository.create_chunk(doc_id, payload, user.user_id))


@router.put("/knowledge-base/docs/{doc_id}/chunks/{chunk_id}")
async def update_chunk(doc_id: str, chunk_id: str, payload: dict[str, Any], user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    repository.update_chunk(chunk_id, payload)
    return success()


@router.delete("/knowledge-base/docs/{doc_id}/chunks/{chunk_id}")
async def delete_chunk(doc_id: str, chunk_id: str, user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    repository.delete_chunk(chunk_id)
    return success()


@router.get("/knowledge-base/docs/{doc_id}/preview")
async def preview_document(doc_id: str, user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    return success(repository.preview_document(doc_id))


@router.get("/knowledge-base/docs/{doc_id}/chunk-logs")
async def chunk_logs(doc_id: str, current: int = 1, size: int = 10, user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    return success(repository.list_document_chunk_logs(doc_id, current, size))
