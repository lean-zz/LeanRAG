from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request

from app.core.auth import LoginUser, current_user
from app.core.responses import success
from app.db.repository import repository
from app.infra.llm import model_health

router = APIRouter()


@router.get("/rag/sample-questions")
async def public_sample_questions() -> dict[str, Any]:
    return success(repository.list_sample_questions())


@router.get("/sample-questions")
async def sample_questions(current: int = 1, size: int = 10, title: str | None = None, user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    return success(repository.list_sample_questions(current, size, title))


@router.post("/sample-questions")
async def create_sample_question(payload: dict[str, Any], user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    return success(repository.create_sample_question(payload))


@router.get("/sample-questions/{item_id}")
async def get_sample_question(item_id: str, user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    return success(repository.get_sample_question(item_id))


@router.put("/sample-questions/{item_id}")
async def update_sample_question(item_id: str, payload: dict[str, Any], user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    repository.update_sample_question(item_id, payload)
    return success()


@router.delete("/sample-questions/{item_id}")
async def delete_sample_question(item_id: str, user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    repository.delete_sample_question(item_id)
    return success()


@router.get("/mappings")
async def mappings(current: int = 1, size: int = 10, keyword: str | None = None, user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    return success(repository.list_mappings(current, size, keyword))


@router.post("/mappings")
async def create_mapping(payload: dict[str, Any], user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    return success(repository.create_mapping(payload))


@router.get("/mappings/{item_id}")
async def get_mapping(item_id: str, user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    return success(repository.get_mapping(item_id))


@router.put("/mappings/{item_id}")
async def update_mapping(item_id: str, payload: dict[str, Any], user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    repository.update_mapping(item_id, payload)
    return success()


@router.delete("/mappings/{item_id}")
async def delete_mapping(item_id: str, user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    repository.delete_mapping(item_id)
    return success()


@router.get("/intent-tree/trees")
async def intent_trees(user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    return success(repository.list_intent_nodes())


@router.post("/intent-tree")
async def create_intent(payload: dict[str, Any], user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    return success(repository.create_intent_node(payload))


@router.put("/intent-tree/{item_id}")
async def update_intent(item_id: str, payload: dict[str, Any], user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    repository.update_intent_node(item_id, payload)
    return success()


@router.delete("/intent-tree/{item_id}")
async def delete_intent(item_id: str, user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    repository.delete_intent_node(item_id)
    return success()


@router.post("/intent-tree/batch/enable")
@router.post("/intent-tree/batch/disable")
@router.post("/intent-tree/batch/delete")
async def intent_batch(request: Request, payload: dict[str, Any], user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    ids = payload.get("ids") or payload.get("idList") or payload.get("nodeIds") or []
    action = request.url.path.rsplit("/", 1)[-1]
    repository.batch_intent_nodes([str(item) for item in ids], action)
    return success()


@router.get("/rag/settings")
async def rag_settings(user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    return success({"vectorType": "pg", "defaultCollectionName": "rag_default_store", "dimension": 1536, "queryRewriteEnabled": True, "memorySummaryEnabled": True, "modelHealthPath": "/rag/model-health", "mcpServers": [{"name": "default", "url": "http://localhost:9099"}]})


@router.get("/rag/model-health")
async def rag_model_health(user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    return success(await model_health())


@router.get("/rag/traces/runs")
async def trace_runs(current: int = 1, size: int = 10, user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    return success(repository.list_trace_runs(current, size))


@router.get("/rag/traces/runs/{trace_id}")
async def trace_detail(trace_id: str, user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    return success(repository.get_trace_run(trace_id) or {"traceId": trace_id, "question": None, "status": "unknown"})


@router.get("/rag/traces/runs/{trace_id}/nodes")
async def trace_run_nodes(trace_id: str, user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    return success(repository.list_trace_nodes(trace_id))


@router.get("/rag/eval")
async def rag_eval(user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    return success({"enabled": True, "status": "ready"})
