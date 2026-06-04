from __future__ import annotations

from fastapi import APIRouter

from app.api import admin, auth_users, chat, ingestion, knowledge, rag_admin

api_router = APIRouter()
api_router.include_router(auth_users.router)
api_router.include_router(chat.router)
api_router.include_router(knowledge.router)
api_router.include_router(ingestion.router)
api_router.include_router(rag_admin.router)
api_router.include_router(admin.router)

