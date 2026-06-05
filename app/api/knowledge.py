from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile

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
        {"value": "fixed_size", "label": "Fixed size", "defaultConfig": {"chunkSize": 512, "overlapSize": 128}},
        {"value": "structure_aware", "label": "Structure aware", "defaultConfig": {"targetChars": 1400, "maxChars": 1800, "minChars": 600, "overlapChars": 0}},
        {"value": "paragraph", "label": "Paragraph", "defaultConfig": {"targetChars": 1000, "maxChars": 1400, "minChars": 400, "overlapChars": 0}},
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
        doc = await ingestion_service.ingest_url(
            kb_id,
            sourceLocation,
            user.user_id,
            process_mode=processMode,
            chunk_strategy=chunkStrategy,
            chunk_config=chunkConfig,
            pipeline_id=pipelineId,
            schedule_enabled=scheduleEnabled,
            schedule_cron=scheduleCron,
        )
    else:
        raw = await file.read() if file else b""
        filename = file.filename if file else sourceLocation or "document.txt"
        file_type = filename.rsplit(".", 1)[-1] if "." in filename else "txt"
        doc = await ingestion_service.ingest_upload(
            kb_id,
            filename,
            raw,
            file_type,
            len(raw),
            user.user_id,
            process_mode=processMode,
            chunk_strategy=chunkStrategy,
            chunk_config=chunkConfig,
            pipeline_id=pipelineId,
            schedule_enabled=scheduleEnabled,
            schedule_cron=scheduleCron,
        )
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


@router.patch("/knowledge-base/docs/{doc_id}/enable")
async def enable_document(doc_id: str, value: bool = Query(...), user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    repository.set_document_enabled(doc_id, value)
    return success()


@router.get("/knowledge-base/docs/{doc_id}/chunks")
async def chunks(doc_id: str, current: int = 1, size: int = 10, enabled: int | None = None, user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    return success(repository.list_document_chunks(doc_id, current, size, enabled))


@router.post("/knowledge-base/docs/{doc_id}/chunks")
async def create_chunk(doc_id: str, payload: dict[str, Any], user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    return success(repository.create_chunk(doc_id, payload, user.user_id))


@router.patch("/knowledge-base/docs/{doc_id}/chunks/batch-enable")
async def batch_enable_chunks(doc_id: str, payload: dict[str, Any], value: bool = Query(...), user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    chunk_ids = [str(item) for item in payload.get("chunkIds", [])]
    repository.batch_set_chunks_enabled(doc_id, chunk_ids, value)
    return success()


@router.put("/knowledge-base/docs/{doc_id}/chunks/{chunk_id}")
async def update_chunk(doc_id: str, chunk_id: str, payload: dict[str, Any], user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    repository.update_chunk(chunk_id, payload)
    return success()


@router.patch("/knowledge-base/docs/{doc_id}/chunks/{chunk_id}/enable")
async def enable_chunk(doc_id: str, chunk_id: str, value: bool = Query(...), user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    repository.set_chunk_enabled(chunk_id, value)
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
