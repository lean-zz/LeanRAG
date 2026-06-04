from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.core.auth import LoginUser, current_user, optional_user
from app.core.responses import success
from app.db.repository import repository
from app.rag.pipeline import stop_task, stream_chat

router = APIRouter()


@router.get("/rag/v3/chat")
async def chat(question: str, conversationId: str | None = None, deepThinking: bool = False, user: LoginUser = Depends(optional_user)) -> StreamingResponse:
    return StreamingResponse(stream_chat(question, conversationId, user.user_id, deepThinking), media_type="text/event-stream;charset=UTF-8")


@router.post("/rag/v3/stop")
async def stop(taskId: str = Query(...)) -> dict[str, Any]:
    stop_task(taskId)
    return success()


@router.get("/conversations")
async def conversations(user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    return success(repository.list_conversations(user.user_id))


@router.put("/conversations/{conversation_id}")
async def update_conversation(conversation_id: str, payload: dict[str, Any], user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    repository.update_conversation(conversation_id, user.user_id, payload)
    return success()


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    repository.delete_conversation(conversation_id, user.user_id)
    return success()


@router.get("/conversations/{conversation_id}/messages")
async def conversation_messages(conversation_id: str, user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    return success(repository.list_messages(conversation_id, user.user_id))


@router.post("/conversations/messages/{message_id}/feedback")
async def feedback(message_id: str, payload: dict[str, Any], user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    repository.create_message_feedback(message_id, user.user_id, payload)
    return success()
