from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from app.core.ids import new_id


def now_text() -> str:
    return datetime.now(UTC).replace(tzinfo=None).isoformat(timespec="seconds")


class MemoryStore:
    def __init__(self) -> None:
        self.users: dict[str, dict[str, Any]] = {}
        self.conversations: dict[str, dict[str, Any]] = {}
        self.messages: dict[str, list[dict[str, Any]]] = {}
        self.knowledge_bases: dict[str, dict[str, Any]] = {}
        self.documents: dict[str, dict[str, Any]] = {}
        self.chunks: dict[str, dict[str, Any]] = {}
        self.sample_questions: dict[str, dict[str, Any]] = {}
        self.intent_nodes: dict[str, dict[str, Any]] = {}
        self.mappings: dict[str, dict[str, Any]] = {}
        self.feedbacks: dict[str, dict[str, Any]] = {}
        self.vectors: dict[str, dict[str, Any]] = {}
        self.pipelines: dict[str, dict[str, Any]] = {}
        self.tasks: dict[str, dict[str, Any]] = {}
        self.ingestion_task_nodes: dict[str, list[dict[str, Any]]] = {}
        self.document_chunk_logs: dict[str, list[dict[str, Any]]] = {}
        self.traces: dict[str, dict[str, Any]] = {}
        self.trace_nodes: dict[str, list[dict[str, Any]]] = {}
        self.conversation_summaries: dict[str, dict[str, Any]] = {}
        self._seed()

    def _seed(self) -> None:
        admin_id = "1"
        self.users[admin_id] = {
            "id": admin_id,
            "username": "admin",
            "password": "admin",
            "role": "admin",
            "avatar": None,
            "createTime": now_text(),
            "updateTime": now_text(),
        }
        qid = new_id()
        self.sample_questions[qid] = {
            "id": qid,
            "title": "Ragent",
            "description": "默认示例问题",
            "question": "Ragent AI 可以做什么？",
            "createTime": now_text(),
            "updateTime": now_text(),
        }

    def list_values(self, name: str) -> list[dict[str, Any]]:
        return [deepcopy(item) for item in getattr(self, name).values()]

    def get(self, name: str, item_id: str) -> dict[str, Any] | None:
        item = getattr(self, name).get(item_id)
        return deepcopy(item) if item else None

    def create(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        item_id = str(payload.get("id") or new_id())
        item = {"id": item_id, **payload, "createTime": now_text(), "updateTime": now_text()}
        getattr(self, name)[item_id] = item
        return deepcopy(item)

    def update(self, name: str, item_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        collection = getattr(self, name)
        item = collection.setdefault(item_id, {"id": item_id, "createTime": now_text()})
        item.update({k: v for k, v in payload.items() if v is not None})
        item["updateTime"] = now_text()
        return deepcopy(item)

    def delete(self, name: str, item_id: str) -> None:
        getattr(self, name).pop(item_id, None)


store = MemoryStore()
