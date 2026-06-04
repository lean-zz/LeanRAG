from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Query, UploadFile

from app.core.auth import LoginUser, current_user
from app.core.responses import success
from app.db.repository import repository
from app.infra.messaging import rocketmq

router = APIRouter()


@router.get("/ingestion/pipelines")
async def ingestion_pipelines(current: int = 1, size: int = 10, pageNo: int | None = None, pageSize: int | None = None, user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    return success(repository.list_ingestion_pipelines(pageNo or current, pageSize or size))


@router.post("/ingestion/pipelines")
async def create_pipeline(payload: dict[str, Any], user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    return success(repository.create_ingestion_pipeline(payload, user.user_id))


@router.get("/ingestion/pipelines/{item_id}")
async def get_pipeline(item_id: str, user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    return success(repository.get_ingestion_pipeline(item_id))


@router.put("/ingestion/pipelines/{item_id}")
async def update_pipeline(item_id: str, payload: dict[str, Any], user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    return success(repository.update_ingestion_pipeline(item_id, payload, user.user_id))


@router.delete("/ingestion/pipelines/{item_id}")
async def delete_pipeline(item_id: str, user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    repository.delete_ingestion_pipeline(item_id)
    return success()


@router.get("/ingestion/tasks")
async def ingestion_tasks(current: int = 1, size: int = 10, pageNo: int | None = None, pageSize: int | None = None, status: str | None = None, user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    return success(repository.list_ingestion_tasks(pageNo or current, pageSize or size, status))


@router.post("/ingestion/tasks")
async def create_task(payload: dict[str, Any], user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    task = repository.create_ingestion_task({"status": "pending", **payload}, user.user_id)
    rocketmq.publish("ingestion.task.created", {"taskId": task["id"], "pipelineId": task.get("pipelineId"), "sourceType": task.get("sourceType"), "createdBy": user.user_id})
    return success({"taskId": task["id"], "pipelineId": task.get("pipelineId"), "status": task.get("status"), "chunkCount": 0, "message": None})


@router.post("/ingestion/tasks/upload")
async def upload_task(pipelineId: str | None = Query(None), file: UploadFile | None = File(None), user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    task = repository.create_ingestion_task({"status": "pending", "pipelineId": pipelineId, "sourceType": "file", "sourceFileName": file.filename if file else None}, user.user_id)
    rocketmq.publish("ingestion.task.created", {"taskId": task["id"], "pipelineId": task.get("pipelineId"), "sourceType": "file", "sourceFileName": file.filename if file else None, "createdBy": user.user_id})
    return success({"taskId": task["id"], "pipelineId": task.get("pipelineId"), "status": task.get("status"), "chunkCount": 0, "message": None})


@router.get("/ingestion/tasks/{item_id}")
async def get_task(item_id: str, user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    return success(repository.get_ingestion_task(item_id))


@router.get("/ingestion/tasks/{item_id}/nodes")
async def get_task_nodes(item_id: str, user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    return success(repository.list_ingestion_task_nodes(item_id))
