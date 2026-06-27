from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import json

from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.ids import new_id
from app.core.responses import page
from app.db.models import Conversation, KnowledgeBase, KnowledgeChunk, KnowledgeDocument, Message, User
from app.db.session import SessionLocal, engine
from app.services.store import now_text, store


def db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("select 1"))
        return True
    except SQLAlchemyError:
        return False
    except Exception:
        return False


class Repository:
    def __init__(self) -> None:
        self._db_enabled: bool | None = None

    @property
    def db_enabled(self) -> bool:
        if self._db_enabled is None:
            self._db_enabled = db_available()
        return self._db_enabled

    def _with_fallback(self, action: Callable[[], Any], fallback: Callable[[], Any]) -> Any:
        if not self.db_enabled:
            return fallback()
        try:
            return action()
        except Exception:
            self._db_enabled = False
            return fallback()

    def find_user_by_credentials(self, username: str | None, password: str | None) -> dict[str, Any] | None:
        def db_action() -> dict[str, Any] | None:
            with SessionLocal() as session:
                row = session.execute(
                    select(User).where(User.username == username, User.password == password, User.deleted == 0)
                ).scalar_one_or_none()
                if row is None:
                    return None
                return {"id": row.id, "username": row.username, "password": row.password, "role": row.role, "avatar": row.avatar}

        def fallback() -> dict[str, Any] | None:
            return next((u for u in store.users.values() if u["username"] == username and u["password"] == password), None)

        return self._with_fallback(db_action, fallback)

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        def db_action() -> dict[str, Any] | None:
            with SessionLocal() as session:
                row = session.execute(select(User).where(User.id == user_id, User.deleted == 0)).scalar_one_or_none()
                if row is None:
                    return None
                return {"id": row.id, "username": row.username, "role": row.role, "avatar": row.avatar}

        return self._with_fallback(db_action, lambda: store.get("users", user_id))

    def list_users(self, current: int = 1, size: int = 10, username: str | None = None) -> dict[str, Any]:
        def db_action() -> dict[str, Any]:
            where = "deleted = 0"
            params: dict[str, Any] = {"limit": size, "offset": max(current - 1, 0) * size}
            if username:
                where += " AND username ILIKE :username"
                params["username"] = f"%{username}%"
            with engine.connect() as conn:
                total = conn.execute(text(f"SELECT count(*) FROM t_user WHERE {where}"), params).scalar() or 0
                rows = conn.execute(
                    text(f"SELECT id, username, role, avatar, create_time, update_time FROM t_user WHERE {where} ORDER BY create_time DESC LIMIT :limit OFFSET :offset"),
                    params,
                ).mappings()
                records = [
                    {
                        "id": r["id"],
                        "username": r["username"],
                        "role": r["role"],
                        "avatar": r["avatar"],
                        "createTime": str(r["create_time"]) if r["create_time"] else None,
                        "updateTime": str(r["update_time"]) if r["update_time"] else None,
                    }
                    for r in rows
                ]
                return {"records": records, "total": total, "size": size, "current": current, "pages": (total + size - 1) // size if size else 0}

        def fallback() -> dict[str, Any]:
            records = store.list_values("users")
            if username:
                records = [r for r in records if username in r.get("username", "")]
            for record in records:
                record.pop("password", None)
            return page(records, current, size)

        return self._with_fallback(db_action, fallback)

    def create_user(self, payload: dict[str, Any]) -> str:
        item_id = str(payload.get("id") or new_id())

        def fallback() -> str:
            item = store.create("users", {"id": item_id, "username": payload.get("username"), "password": payload.get("password", "123456"), "role": payload.get("role", "user"), "avatar": payload.get("avatar")})
            return str(item["id"])

        def db_action() -> str:
            with SessionLocal() as session:
                session.add(User(id=item_id, username=payload.get("username"), password=payload.get("password", "123456"), role=payload.get("role", "user"), avatar=payload.get("avatar"), deleted=0))
                session.commit()
            fallback()
            return item_id

        return self._with_fallback(db_action, fallback)

    def update_user(self, item_id: str, payload: dict[str, Any]) -> None:
        allowed = {k: v for k, v in {"username": payload.get("username"), "role": payload.get("role"), "avatar": payload.get("avatar"), "password": payload.get("password")}.items() if v is not None}

        def fallback() -> None:
            store.update("users", item_id, allowed)

        def db_action() -> None:
            if not allowed:
                return
            assignments = ", ".join(f"{key} = :{key}" for key in allowed)
            with engine.begin() as conn:
                conn.execute(text(f"UPDATE t_user SET {assignments}, update_time = now() WHERE id = :id AND deleted = 0"), {"id": item_id, **allowed})
            fallback()

        self._with_fallback(db_action, fallback)

    def delete_user(self, item_id: str) -> None:
        def fallback() -> None:
            store.delete("users", item_id)

        def db_action() -> None:
            with engine.begin() as conn:
                conn.execute(text("UPDATE t_user SET deleted = 1, update_time = now() WHERE id = :id"), {"id": item_id})
            fallback()

        self._with_fallback(db_action, fallback)

    def change_password(self, user_id: str, password: str | None) -> None:
        if not password:
            return
        self.update_user(user_id, {"password": password})

    def list_conversations(self, user_id: str) -> list[dict[str, Any]]:
        def db_action() -> list[dict[str, Any]]:
            with SessionLocal() as session:
                rows = session.execute(select(Conversation).where(Conversation.user_id == user_id, Conversation.deleted == 0)).scalars()
                return [
                    {"id": r.id, "conversationId": r.conversation_id, "userId": r.user_id, "title": r.title, "lastTime": str(r.last_time) if r.last_time else None}
                    for r in rows
                ]

        return self._with_fallback(db_action, lambda: [r for r in store.list_values("conversations") if r.get("userId") == user_id])

    def list_messages(self, conversation_id: str, user_id: str) -> list[dict[str, Any]]:
        def db_action() -> list[dict[str, Any]]:
            with SessionLocal() as session:
                rows = session.execute(
                    select(Message).where(Message.conversation_id == conversation_id, Message.user_id == user_id, Message.deleted == 0)
                ).scalars()
                return [
                    {
                        "id": r.id,
                        "conversationId": r.conversation_id,
                        "userId": r.user_id,
                        "role": r.role,
                        "content": r.content,
                        "thinkingContent": r.thinking_content,
                        "thinkingDuration": r.thinking_duration,
                    }
                    for r in rows
                ]

        return self._with_fallback(db_action, lambda: store.messages.get(conversation_id, []))

    def ensure_conversation(self, conversation_id: str, user_id: str, title: str) -> None:
        def fallback() -> None:
            store.conversations.setdefault(
                conversation_id,
                {"id": conversation_id, "conversationId": conversation_id, "userId": user_id, "title": title, "lastTime": now_text(), "createTime": now_text(), "updateTime": now_text()},
            )

        def db_action() -> None:
            with SessionLocal() as session:
                existing = session.execute(
                    select(Conversation).where(Conversation.conversation_id == conversation_id, Conversation.user_id == user_id)
                ).scalar_one_or_none()
                now = datetime.now(UTC).replace(tzinfo=None)
                if existing is None:
                    session.add(Conversation(id=conversation_id, conversation_id=conversation_id, user_id=user_id, title=title, last_time=now, deleted=0))
                else:
                    existing.last_time = now
                    if not existing.title:
                        existing.title = title
                session.commit()
            fallback()

        self._with_fallback(db_action, fallback)

    def append_message(self, conversation_id: str, user_id: str, role: str, content: str, message_id: str, thinking: str | None = None, thinking_duration: int | None = None) -> None:
        def fallback() -> None:
            store.messages.setdefault(conversation_id, []).append(
                {"id": message_id, "conversationId": conversation_id, "userId": user_id, "role": role, "content": content, "thinkingContent": thinking, "thinkingDuration": thinking_duration, "createTime": now_text()}
            )

        def db_action() -> None:
            with SessionLocal() as session:
                session.add(
                    Message(
                        id=message_id,
                        conversation_id=conversation_id,
                        user_id=user_id,
                        role=role,
                        content=content,
                        thinking_content=thinking,
                        thinking_duration=thinking_duration,
                        deleted=0,
                    )
                )
                session.commit()
            fallback()

        self._with_fallback(db_action, fallback)

    def update_conversation(self, conversation_id: str, user_id: str, payload: dict[str, Any]) -> None:
        title = payload.get("title")

        def fallback() -> None:
            store.update("conversations", conversation_id, {"title": title, "userId": user_id})

        def db_action() -> None:
            if title is not None:
                with engine.begin() as conn:
                    conn.execute(text("UPDATE t_conversation SET title = :title, last_time = now() WHERE conversation_id = :conversation_id AND user_id = :user_id AND deleted = 0"), {"title": title, "conversation_id": conversation_id, "user_id": user_id})
            fallback()

        self._with_fallback(db_action, fallback)

    def latest_conversation_summary(self, conversation_id: str, user_id: str) -> dict[str, Any] | None:
        key = f"{conversation_id}:{user_id}"

        def fallback() -> dict[str, Any] | None:
            return store.conversation_summaries.get(key)

        def db_action() -> dict[str, Any] | None:
            with engine.connect() as conn:
                row = conn.execute(
                    text(
                        "SELECT id, conversation_id, user_id, last_message_id, content "
                        "FROM t_conversation_summary "
                        "WHERE conversation_id = :conversation_id AND user_id = :user_id AND deleted = 0 "
                        "ORDER BY create_time DESC LIMIT 1"
                    ),
                    {"conversation_id": conversation_id, "user_id": user_id},
                ).mappings().first()
                return dict(row) if row else None

        return self._with_fallback(db_action, fallback)

    def upsert_conversation_summary(self, conversation_id: str, user_id: str, content: str, last_message_id: str) -> None:
        key = f"{conversation_id}:{user_id}"
        item_id = new_id()

        def fallback() -> None:
            store.conversation_summaries[key] = {
                "id": item_id,
                "conversationId": conversation_id,
                "userId": user_id,
                "lastMessageId": last_message_id,
                "content": content,
                "updateTime": now_text(),
            }

        def db_action() -> None:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO t_conversation_summary (id, conversation_id, user_id, last_message_id, content, create_time, update_time, deleted) "
                        "VALUES (:id, :conversation_id, :user_id, :last_message_id, :content, now(), now(), 0)"
                    ),
                    {"id": item_id, "conversation_id": conversation_id, "user_id": user_id, "last_message_id": last_message_id, "content": content},
                )
            fallback()

        self._with_fallback(db_action, fallback)

    def delete_conversation(self, conversation_id: str, user_id: str) -> None:
        def fallback() -> None:
            store.delete("conversations", conversation_id)
            store.messages.pop(conversation_id, None)

        def db_action() -> None:
            with engine.begin() as conn:
                conn.execute(text("UPDATE t_conversation SET deleted = 1 WHERE conversation_id = :conversation_id AND user_id = :user_id"), {"conversation_id": conversation_id, "user_id": user_id})
                conn.execute(text("UPDATE t_message SET deleted = 1 WHERE conversation_id = :conversation_id AND user_id = :user_id"), {"conversation_id": conversation_id, "user_id": user_id})
            fallback()

        self._with_fallback(db_action, fallback)

    def create_message_feedback(self, message_id: str, user_id: str, payload: dict[str, Any]) -> str:
        item_id = str(payload.get("id") or new_id())

        def fallback() -> str:
            feedback = store.create(
                "feedbacks",
                {
                    "id": item_id,
                    "messageId": message_id,
                    "userId": user_id,
                    "feedbackType": str(payload.get("vote") or payload.get("feedbackType") or ""),
                    "content": payload.get("content"),
                },
            )
            return str(feedback["id"])

        def db_action() -> str:
            with engine.begin() as conn:
                conn.execute(
                    text("INSERT INTO t_message_feedback (id, message_id, user_id, feedback_type, content, create_time, update_time, deleted) VALUES (:id, :message_id, :user_id, :feedback_type, :content, now(), now(), 0)"),
                    {"id": item_id, "message_id": message_id, "user_id": user_id, "feedback_type": str(payload.get("vote") or payload.get("feedbackType") or ""), "content": payload.get("content")},
                )
            fallback()
            return item_id

        return self._with_fallback(db_action, fallback)

    def list_chunks(self, limit: int = 200) -> list[dict[str, Any]]:
        def db_action() -> list[dict[str, Any]]:
            with SessionLocal() as session:
                rows = session.execute(select(KnowledgeChunk).where(KnowledgeChunk.deleted == 0).limit(limit)).scalars()
                return [{"id": r.id, "kbId": r.kb_id, "docId": r.doc_id, "content": r.content, "enabled": r.enabled} for r in rows]

        return self._with_fallback(db_action, lambda: store.list_values("chunks")[:limit])

    def search_vectors(self, query_embedding: list[float], query: str, top_k: int = 5) -> list[dict[str, Any]]:
        vector_literal = "[" + ",".join(str(float(x)) for x in query_embedding) + "]"

        def db_action() -> list[dict[str, Any]]:
            with engine.connect() as conn:
                rows = conn.execute(
                    text(
                        "SELECT id, content, metadata, 1 - (embedding <=> CAST(:embedding AS vector)) AS score "
                        "FROM t_knowledge_vector ORDER BY embedding <=> CAST(:embedding AS vector) LIMIT :limit"
                    ),
                    {"embedding": vector_literal, "limit": top_k},
                ).mappings()
                return [{"id": r["id"], "content": r["content"], "metadata": r["metadata"], "score": float(r["score"] or 0), "channel": "pgvector"} for r in rows]

        def fallback() -> list[dict[str, Any]]:
            rows = []
            for vector in store.vectors.values():
                embedding = vector.get("embedding") or []
                score = self._cosine(query_embedding, embedding) if embedding else 0.0
                content = vector.get("content") or ""
                if query and query.lower() in content.lower():
                    score += 0.05
                rows.append({**vector, "score": score, "channel": "memory-vector"})
            rows.sort(key=lambda item: item.get("score", 0), reverse=True)
            return rows[:top_k]

        return self._with_fallback(db_action, fallback)

    def create_knowledge_base(self, payload: dict[str, Any]) -> dict[str, Any]:
        item_id = str(payload.get("id") or new_id())

        def fallback() -> dict[str, Any]:
            return store.create("knowledge_bases", {"id": item_id, **payload})

        def db_action() -> dict[str, Any]:
            with SessionLocal() as session:
                row = KnowledgeBase(
                    id=item_id,
                    name=payload["name"],
                    embedding_model=payload.get("embeddingModel", "qwen-emb-8b"),
                    collection_name=payload.get("collectionName") or f"kb_{item_id}",
                    created_by=payload.get("createdBy", "0"),
                    deleted=0,
                )
                session.add(row)
                session.commit()
                result = {"id": row.id, "name": row.name, "embeddingModel": row.embedding_model, "collectionName": row.collection_name, "createdBy": row.created_by}
            store.knowledge_bases[result["id"]] = result
            return result

        return self._with_fallback(db_action, fallback)

    def create_document_with_chunks(self, document: dict[str, Any], chunks: list[dict[str, Any]]) -> dict[str, Any]:
        def fallback() -> dict[str, Any]:
            doc = store.create("documents", document)
            for chunk in chunks:
                store.create("chunks", chunk)
            return doc

        def db_action() -> dict[str, Any]:
            with SessionLocal() as session:
                doc = KnowledgeDocument(
                    id=document["id"],
                    kb_id=document["kbId"],
                    doc_name=document["docName"],
                    file_url=document.get("fileUrl", ""),
                    file_type=document.get("fileType", "txt"),
                    file_size=document.get("fileSize"),
                    status=document.get("status", "completed"),
                    chunk_config=document.get("chunkConfig"),
                    deleted=0,
                )
                session.add(doc)
                for chunk in chunks:
                    session.add(
                        KnowledgeChunk(
                            id=chunk["id"],
                            kb_id=chunk["kbId"],
                            doc_id=chunk["docId"],
                            chunk_index=chunk.get("chunkIndex", 0),
                            content=chunk["content"],
                            token_count=chunk.get("tokenCount"),
                            enabled=chunk.get("enabled", 1),
                            deleted=0,
                        )
                    )
                session.commit()
            return fallback()

        return self._with_fallback(db_action, fallback)

    def upsert_vectors(self, collection_name: str, doc_id: str, chunks: list[dict[str, Any]]) -> None:
        def fallback() -> None:
            for chunk in chunks:
                embedding = chunk.get("embedding") or []
                if not embedding:
                    continue
                metadata = {"collection_name": collection_name, "doc_id": doc_id, "chunk_index": chunk.get("chunkIndex", 0), "kb_id": chunk.get("kbId")}
                store.vectors[str(chunk["id"])] = {
                    "id": str(chunk["id"]),
                    "content": chunk.get("content", ""),
                    "metadata": metadata,
                    "embedding": embedding,
                    "updateTime": now_text(),
                }

        def db_action() -> None:
            with engine.begin() as conn:
                for chunk in chunks:
                    embedding = chunk.get("embedding") or []
                    if not embedding:
                        continue
                    metadata = {"collection_name": collection_name, "doc_id": doc_id, "chunk_index": chunk.get("chunkIndex", 0), "kb_id": chunk.get("kbId")}
                    vector_literal = "[" + ",".join(str(float(x)) for x in embedding) + "]"
                    conn.execute(
                        text(
                            "INSERT INTO t_knowledge_vector (id, content, metadata, embedding) "
                            "VALUES (:id, :content, CAST(:metadata AS jsonb), CAST(:embedding AS vector)) "
                            "ON CONFLICT (id) DO UPDATE SET content = EXCLUDED.content, metadata = EXCLUDED.metadata, embedding = EXCLUDED.embedding"
                        ),
                        {"id": chunk["id"], "content": chunk["content"], "metadata": json.dumps(metadata, ensure_ascii=False), "embedding": vector_literal},
                    )

        self._with_fallback(db_action, fallback)

    def record_trace(
        self,
        trace_id: str,
        question: str,
        conversation_id: str,
        task_id: str,
        user_id: str,
        nodes: list[dict[str, Any]],
        evidence: list[dict[str, Any]] | None = None,
        decisions: list[dict[str, Any]] | None = None,
        guardrail: dict[str, Any] | None = None,
        variant: str | None = None,
        message_id: str | None = None,
        latency_ms: int | None = None,
    ) -> None:
        evidence = evidence or []
        decisions = decisions or []
        guardrail = guardrail or {"action": "allow", "reason": "none"}
        guardrail_summary = guardrail.get("summary") or f"{guardrail.get('action', 'allow')}:{guardrail.get('reason', 'none')}"

        def fallback() -> None:
            store.traces[trace_id] = {
                "id": trace_id,
                "traceId": trace_id,
                "question": question,
                "traceName": question[:128],
                "conversationId": conversation_id,
                "taskId": task_id,
                "userId": user_id,
                "status": "completed",
                "mode": "rag",
                "variant": variant or "baseline",
                "latencyMs": latency_ms,
                "durationMs": latency_ms,
                "guardrailSummary": guardrail_summary,
                "createTime": now_text(),
            }
            store.trace_nodes[trace_id] = nodes
            store.trace_evidence[trace_id] = [{**item, "traceId": trace_id, "messageId": message_id} for item in evidence]
            store.trace_decisions[trace_id] = [{**item, "traceId": trace_id, "messageId": message_id, "guardrailSummary": guardrail_summary} for item in decisions]

        def db_action() -> None:
            now = datetime.now(UTC).replace(tzinfo=None)
            extra = {
                "question": question,
                "mode": "rag",
                "variant": variant or "baseline",
                "guardrailSummary": guardrail_summary,
                "guardrail": guardrail,
                "evidence": evidence,
                "evidenceCount": len(evidence),
                "decision": decisions[0] if decisions else None,
            }
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO t_rag_trace_run (id, trace_id, trace_name, entry_method, conversation_id, task_id, user_id, status, start_time, end_time, duration_ms, extra_data) "
                        "VALUES (:id, :trace_id, :trace_name, :entry_method, :conversation_id, :task_id, :user_id, 'COMPLETED', :start_time, :end_time, 0, :extra_data) "
                        "ON CONFLICT (trace_id) DO UPDATE SET status = EXCLUDED.status, end_time = EXCLUDED.end_time, extra_data = EXCLUDED.extra_data"
                    ),
                    {"id": trace_id, "trace_id": trace_id, "trace_name": question[:128], "entry_method": "rag/v3/chat", "conversation_id": conversation_id, "task_id": task_id, "user_id": user_id, "start_time": now, "end_time": now, "extra_data": json.dumps(extra, ensure_ascii=False)},
                )
                for node in nodes:
                    node_id = str(node.get("nodeId") or node.get("id") or new_id())
                    conn.execute(
                        text(
                            "INSERT INTO t_rag_trace_node (id, trace_id, node_id, node_type, node_name, status, start_time, end_time, duration_ms, extra_data) "
                            "VALUES (:id, :trace_id, :node_id, :node_type, :node_name, :status, :start_time, :end_time, 0, :extra_data) "
                            "ON CONFLICT (trace_id, node_id) DO UPDATE SET status = EXCLUDED.status, end_time = EXCLUDED.end_time, extra_data = EXCLUDED.extra_data"
                        ),
                        {"id": str(node.get("id") or new_id()), "trace_id": trace_id, "node_id": node_id, "node_type": node.get("nodeType"), "node_name": node.get("nodeName"), "status": node.get("status", "completed").upper(), "start_time": now, "end_time": now, "extra_data": json.dumps(node, ensure_ascii=False)},
                    )
            fallback()

        self._with_fallback(db_action, fallback)

    def list_trace_runs(self, current: int = 1, size: int = 10) -> dict[str, Any]:
        def db_action() -> dict[str, Any]:
            offset = max(current - 1, 0) * size
            with engine.connect() as conn:
                total = conn.execute(text("SELECT count(*) FROM t_rag_trace_run WHERE deleted = 0")).scalar() or 0
                rows = conn.execute(
                    text("SELECT trace_id, trace_name, conversation_id, task_id, user_id, status, start_time, end_time, duration_ms, extra_data FROM t_rag_trace_run WHERE deleted = 0 ORDER BY create_time DESC LIMIT :limit OFFSET :offset"),
                    {"limit": size, "offset": offset},
                ).mappings()
                records = []
                for r in rows:
                    extra = self._json_obj(r["extra_data"])
                    records.append(
                        {
                            "traceId": r["trace_id"],
                            "question": r["trace_name"],
                            "traceName": r["trace_name"],
                            "conversationId": r["conversation_id"],
                            "taskId": r["task_id"],
                            "userId": r["user_id"],
                            "status": r["status"],
                            "startTime": str(r["start_time"]) if r["start_time"] else None,
                            "endTime": str(r["end_time"]) if r["end_time"] else None,
                            "durationMs": r["duration_ms"],
                            "latencyMs": extra.get("latencyMs") or r["duration_ms"],
                            "variant": extra.get("variant"),
                            "guardrailSummary": extra.get("guardrailSummary"),
                            "mode": extra.get("mode"),
                        }
                    )
                return {"records": records, "total": total, "size": size, "current": current, "pages": (total + size - 1) // size if size else 0}

        from app.core.responses import page

        return self._with_fallback(db_action, lambda: page(store.list_values("traces"), current, size))

    def get_trace_run(self, trace_id: str) -> dict[str, Any] | None:
        def db_action() -> dict[str, Any] | None:
            with engine.connect() as conn:
                row = conn.execute(text("SELECT trace_id, trace_name, conversation_id, task_id, user_id, status, extra_data FROM t_rag_trace_run WHERE trace_id = :trace_id AND deleted = 0"), {"trace_id": trace_id}).mappings().first()
                if row is None:
                    return None
                extra = self._json_obj(row["extra_data"])
                return {"traceId": row["trace_id"], "question": row["trace_name"], "traceName": row["trace_name"], "conversationId": row["conversation_id"], "taskId": row["task_id"], "userId": row["user_id"], "status": row["status"], "variant": extra.get("variant"), "guardrailSummary": extra.get("guardrailSummary"), "mode": extra.get("mode"), "extraData": row["extra_data"]}

        return self._with_fallback(db_action, lambda: store.get("traces", trace_id))

    def list_trace_nodes(self, trace_id: str) -> list[dict[str, Any]]:
        def db_action() -> list[dict[str, Any]]:
            with engine.connect() as conn:
                rows = conn.execute(text("SELECT id, node_id, parent_node_id, depth, node_type, node_name, status, duration_ms, extra_data FROM t_rag_trace_node WHERE trace_id = :trace_id AND deleted = 0 ORDER BY create_time ASC"), {"trace_id": trace_id}).mappings()
                return [{"id": r["id"], "nodeId": r["node_id"], "parentNodeId": r["parent_node_id"], "depth": r["depth"], "nodeType": r["node_type"], "nodeName": r["node_name"], "status": r["status"], "durationMs": r["duration_ms"], "extraData": r["extra_data"]} for r in rows]

        return self._with_fallback(db_action, lambda: store.trace_nodes.get(trace_id, []))

    def list_trace_evidence(self, trace_id: str) -> list[dict[str, Any]]:
        def db_action() -> list[dict[str, Any]]:
            run = self.get_trace_run(trace_id) or {}
            extra = self._json_obj(run.get("extraData"))
            evidence = extra.get("evidence") or []
            return evidence if isinstance(evidence, list) else []

        return self._with_fallback(db_action, lambda: store.trace_evidence.get(trace_id, []))

    def list_trace_decisions(self, trace_id: str) -> list[dict[str, Any]]:
        def db_action() -> list[dict[str, Any]]:
            run = self.get_trace_run(trace_id) or {}
            extra = self._json_obj(run.get("extraData"))
            decision = extra.get("decision")
            return [decision] if isinstance(decision, dict) else []

        return self._with_fallback(db_action, lambda: store.trace_decisions.get(trace_id, []))

    def create_eval_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        run_id = str(payload.get("id") or new_id())

        def fallback() -> dict[str, Any]:
            run = {"id": run_id, **payload, "createTime": payload.get("createTime") or now_text()}
            store.eval_runs[run_id] = run
            return run

        return self._with_fallback(lambda: fallback(), fallback)

    def list_eval_runs(self, current: int = 1, size: int = 10) -> dict[str, Any]:
        records = sorted(store.list_values("eval_runs"), key=lambda item: item.get("createTime", ""), reverse=True)
        return page(records, current, size)

    def upsert_experiment_assignment(self, assignment: dict[str, Any]) -> dict[str, Any]:
        item_id = str(assignment.get("id") or new_id())

        def fallback() -> dict[str, Any]:
            store.experiment_assignments[item_id] = {"id": item_id, **assignment}
            return store.experiment_assignments[item_id]

        return self._with_fallback(lambda: fallback(), fallback)

    def experiment_summary(self) -> dict[str, Any]:
        traces = store.list_values("traces")
        assignments = store.list_values("experiment_assignments")
        variant_counts: dict[str, int] = {}
        for trace in traces:
            variant = str(trace.get("variant") or "baseline")
            variant_counts[variant] = variant_counts.get(variant, 0) + 1
        for assignment in assignments:
            variant = str(assignment.get("variant") or "baseline")
            variant_counts.setdefault(variant, 0)
        return {
            "experimentId": "reliability-v1",
            "variants": [{"variant": variant, "traceCount": count} for variant, count in sorted(variant_counts.items())],
            "assignmentCount": len(assignments),
        }

    def list_knowledge_bases(self) -> list[dict[str, Any]]:
        def db_action() -> list[dict[str, Any]]:
            with engine.connect() as conn:
                rows = conn.execute(
                    text(
                        "SELECT kb.id, kb.name, kb.embedding_model, kb.collection_name, kb.created_by, "
                        "(SELECT count(*) FROM t_knowledge_document d WHERE d.kb_id = kb.id AND d.deleted = 0) AS document_count "
                        "FROM t_knowledge_base kb WHERE kb.deleted = 0 ORDER BY kb.create_time DESC"
                    )
                ).mappings()
                return [{"id": r["id"], "name": r["name"], "embeddingModel": r["embedding_model"], "collectionName": r["collection_name"], "createdBy": r["created_by"], "documentCount": r["document_count"]} for r in rows]

        return self._with_fallback(db_action, lambda: store.list_values("knowledge_bases"))

    def get_knowledge_base(self, kb_id: str) -> dict[str, Any] | None:
        return self._with_fallback(lambda: self._fetch_one("SELECT id, name, embedding_model AS \"embeddingModel\", collection_name AS \"collectionName\", created_by AS \"createdBy\" FROM t_knowledge_base WHERE id = :id AND deleted = 0", {"id": kb_id}), lambda: store.get("knowledge_bases", kb_id))

    def update_knowledge_base(self, kb_id: str, payload: dict[str, Any]) -> None:
        self._update_table("t_knowledge_base", kb_id, {"name": payload.get("name"), "embedding_model": payload.get("embeddingModel"), "collection_name": payload.get("collectionName")}, lambda: store.update("knowledge_bases", kb_id, payload))

    def delete_knowledge_base(self, kb_id: str) -> None:
        self._soft_delete("t_knowledge_base", kb_id, lambda: store.delete("knowledge_bases", kb_id))

    def list_documents(self, kb_id: str, current: int = 1, size: int = 10, status: str | None = None, keyword: str | None = None) -> dict[str, Any]:
        def db_action() -> dict[str, Any]:
            where = "kb_id = :kb_id AND deleted = 0"
            params: dict[str, Any] = {"kb_id": kb_id, "limit": size, "offset": max(current - 1, 0) * size}
            if status:
                where += " AND status = :status"
                params["status"] = status
            if keyword:
                where += " AND doc_name ILIKE :keyword"
                params["keyword"] = f"%{keyword}%"
            with engine.connect() as conn:
                total = conn.execute(text(f"SELECT count(*) FROM t_knowledge_document WHERE {where}"), params).scalar() or 0
                rows = conn.execute(text(f"SELECT id, kb_id, doc_name, file_url, file_type, file_size, status, create_time, update_time FROM t_knowledge_document WHERE {where} ORDER BY create_time DESC LIMIT :limit OFFSET :offset"), params).mappings()
                records = [
                    {"id": r["id"], "kbId": r["kb_id"], "docName": r["doc_name"], "fileUrl": r["file_url"], "fileType": r["file_type"], "fileSize": r["file_size"], "status": r["status"], "createTime": str(r["create_time"]) if r["create_time"] else None, "updateTime": str(r["update_time"]) if r["update_time"] else None}
                    for r in rows
                ]
                return {"records": records, "total": total, "size": size, "current": current, "pages": (total + size - 1) // size if size else 0}

        def fallback() -> dict[str, Any]:
            records = [d for d in store.list_values("documents") if d.get("kbId") == kb_id]
            if status:
                records = [d for d in records if d.get("status") == status]
            if keyword:
                records = [d for d in records if keyword in d.get("docName", "")]
            return page(records, current, size)

        return self._with_fallback(db_action, fallback)

    def search_documents(self, keyword: str, limit: int = 8) -> list[dict[str, Any]]:
        def db_action() -> list[dict[str, Any]]:
            with engine.connect() as conn:
                rows = conn.execute(
                    text(
                        "SELECT d.id, d.kb_id, d.doc_name, kb.name AS kb_name FROM t_knowledge_document d "
                        "LEFT JOIN t_knowledge_base kb ON kb.id = d.kb_id AND kb.deleted = 0 "
                        "WHERE d.deleted = 0 AND d.doc_name ILIKE :keyword ORDER BY d.create_time DESC LIMIT :limit"
                    ),
                    {"keyword": f"%{keyword}%", "limit": limit},
                ).mappings()
                return [{"id": r["id"], "kbId": r["kb_id"], "docName": r["doc_name"], "kbName": r["kb_name"]} for r in rows]

        def fallback() -> list[dict[str, Any]]:
            records = []
            for doc in store.documents.values():
                if keyword in doc.get("docName", ""):
                    kb = store.knowledge_bases.get(doc.get("kbId"), {})
                    records.append({"id": doc["id"], "kbId": doc.get("kbId"), "docName": doc.get("docName"), "kbName": kb.get("name")})
            return records[:limit]

        return self._with_fallback(db_action, fallback)

    def get_document(self, doc_id: str) -> dict[str, Any] | None:
        return self._with_fallback(lambda: self._fetch_one("SELECT id, kb_id AS \"kbId\", doc_name AS \"docName\", file_url AS \"fileUrl\", file_type AS \"fileType\", file_size AS \"fileSize\", status FROM t_knowledge_document WHERE id = :id AND deleted = 0", {"id": doc_id}), lambda: store.get("documents", doc_id))

    def update_document(self, doc_id: str, payload: dict[str, Any]) -> None:
        self._update_table("t_knowledge_document", doc_id, {"doc_name": payload.get("docName"), "file_url": payload.get("fileUrl"), "status": payload.get("status"), "chunk_config": payload.get("chunkConfig")}, lambda: store.update("documents", doc_id, payload))

    def set_document_enabled(self, doc_id: str, enabled: bool) -> None:
        value = 1 if enabled else 0
        self._update_table("t_knowledge_document", doc_id, {"enabled": value}, lambda: store.update("documents", doc_id, {"enabled": value}))

    def delete_document(self, doc_id: str) -> None:
        self._soft_delete("t_knowledge_document", doc_id, lambda: store.delete("documents", doc_id))

    def list_document_chunks(self, doc_id: str, current: int = 1, size: int = 10, enabled: int | None = None) -> dict[str, Any]:
        def db_action() -> dict[str, Any]:
            where = "doc_id = :doc_id AND deleted = 0"
            params: dict[str, Any] = {"doc_id": doc_id, "limit": size, "offset": max(current - 1, 0) * size}
            if enabled is not None:
                where += " AND enabled = :enabled"
                params["enabled"] = enabled
            with engine.connect() as conn:
                total = conn.execute(text(f"SELECT count(*) FROM t_knowledge_chunk WHERE {where}"), params).scalar() or 0
                rows = conn.execute(text(f"SELECT id, kb_id, doc_id, chunk_index, content, token_count, enabled FROM t_knowledge_chunk WHERE {where} ORDER BY chunk_index ASC LIMIT :limit OFFSET :offset"), params).mappings()
                records = [{"id": r["id"], "kbId": r["kb_id"], "docId": r["doc_id"], "chunkIndex": r["chunk_index"], "content": r["content"], "tokenCount": r["token_count"], "enabled": r["enabled"]} for r in rows]
                return {"records": records, "total": total, "size": size, "current": current, "pages": (total + size - 1) // size if size else 0}

        def fallback() -> dict[str, Any]:
            records = [c for c in store.list_values("chunks") if c.get("docId") == doc_id]
            if enabled is not None:
                records = [c for c in records if c.get("enabled") == enabled]
            return page(records, current, size)

        return self._with_fallback(db_action, fallback)

    def create_chunk(self, doc_id: str, payload: dict[str, Any], user_id: str) -> dict[str, Any]:
        item_id = str(payload.get("id") or new_id())

        def fallback() -> dict[str, Any]:
            doc = store.documents.get(doc_id, {})
            return store.create("chunks", {"id": item_id, "kbId": doc.get("kbId"), "docId": doc_id, **payload, "createdBy": user_id})

        def db_action() -> dict[str, Any]:
            doc = self.get_document(doc_id) or {}
            with engine.begin() as conn:
                conn.execute(
                    text("INSERT INTO t_knowledge_chunk (id, kb_id, doc_id, chunk_index, content, token_count, enabled, create_time, update_time, deleted) VALUES (:id, :kb_id, :doc_id, :chunk_index, :content, :token_count, :enabled, now(), now(), 0)"),
                    {"id": item_id, "kb_id": doc.get("kbId"), "doc_id": doc_id, "chunk_index": payload.get("chunkIndex", 0), "content": payload.get("content", ""), "token_count": payload.get("tokenCount"), "enabled": payload.get("enabled", 1)},
                )
            return fallback()

        return self._with_fallback(db_action, fallback)

    def update_chunk(self, chunk_id: str, payload: dict[str, Any]) -> None:
        self._update_table("t_knowledge_chunk", chunk_id, {"content": payload.get("content"), "token_count": payload.get("tokenCount"), "enabled": payload.get("enabled")}, lambda: store.update("chunks", chunk_id, payload))

    def set_chunk_enabled(self, chunk_id: str, enabled: bool) -> None:
        value = 1 if enabled else 0
        self.update_chunk(chunk_id, {"enabled": value})

    def batch_set_chunks_enabled(self, doc_id: str, chunk_ids: list[str], enabled: bool) -> None:
        value = 1 if enabled else 0

        def fallback() -> None:
            target_ids = {str(item) for item in chunk_ids}
            for chunk_id, chunk in store.chunks.items():
                if chunk.get("docId") == doc_id and (not target_ids or chunk_id in target_ids):
                    chunk["enabled"] = value
                    chunk["updateTime"] = now_text()

        def db_action() -> None:
            with engine.begin() as conn:
                if chunk_ids:
                    conn.execute(
                        text("UPDATE t_knowledge_chunk SET enabled = :enabled, update_time = now() WHERE doc_id = :doc_id AND id = ANY(:ids) AND deleted = 0"),
                        {"enabled": value, "doc_id": doc_id, "ids": [str(item) for item in chunk_ids]},
                    )
                else:
                    conn.execute(
                        text("UPDATE t_knowledge_chunk SET enabled = :enabled, update_time = now() WHERE doc_id = :doc_id AND deleted = 0"),
                        {"enabled": value, "doc_id": doc_id},
                    )
            fallback()

        self._with_fallback(db_action, fallback)

    def delete_chunk(self, chunk_id: str) -> None:
        self._soft_delete("t_knowledge_chunk", chunk_id, lambda: store.delete("chunks", chunk_id))

    def chunk_document(self, doc_id: str, user_id: str) -> None:
        doc = self.get_document(doc_id)
        if not doc:
            return
        if self.list_document_chunks(doc_id, 1, 1)["total"] == 0:
            self.create_chunk(doc_id, {"chunkIndex": 0, "content": doc.get("docName", ""), "enabled": 1}, user_id)
        self.update_document(doc_id, {"status": "completed"})
        self.record_document_chunk_log(doc_id, {"status": "completed", "processMode": doc.get("processMode", "chunk"), "chunkStrategy": doc.get("chunkStrategy"), "chunkCount": 1, "message": "Document chunking completed"})

    def preview_document(self, doc_id: str) -> str:
        doc = self.get_document(doc_id) or {}
        return f"# {doc.get('docName', 'Document')}\n\nPython backend preview placeholder."

    def list_document_chunk_logs(self, doc_id: str, current: int = 1, size: int = 10) -> dict[str, Any]:
        return page(store.document_chunk_logs.get(doc_id, []), current, size)

    def record_document_chunk_log(self, doc_id: str, payload: dict[str, Any]) -> None:
        store.document_chunk_logs.setdefault(doc_id, []).append(
            {
                "id": str(payload.get("id") or new_id()),
                "docId": doc_id,
                "status": payload.get("status", "completed"),
                "processMode": payload.get("processMode", "chunk"),
                "chunkStrategy": payload.get("chunkStrategy"),
                "chunkConfig": payload.get("chunkConfig"),
                "pipelineId": payload.get("pipelineId"),
                "pipelineName": payload.get("pipelineName"),
                "chunkCount": payload.get("chunkCount", 0),
                "message": payload.get("message"),
                "createTime": now_text(),
            }
        )

    def list_sample_questions(self, current: int | None = None, size: int | None = None, title: str | None = None) -> dict[str, Any] | list[dict[str, Any]]:
        def db_action() -> dict[str, Any] | list[dict[str, Any]]:
            where = "deleted = 0"
            params: dict[str, Any] = {}
            if title:
                where += " AND title ILIKE :title"
                params["title"] = f"%{title}%"
            with engine.connect() as conn:
                if current is None or size is None:
                    rows = conn.execute(text(f"SELECT id, title, description, question, enabled FROM t_sample_question WHERE {where} ORDER BY create_time DESC"), params).mappings()
                    return [dict(r) for r in rows]
                params.update({"limit": size, "offset": max(current - 1, 0) * size})
                total = conn.execute(text(f"SELECT count(*) FROM t_sample_question WHERE {where}"), params).scalar() or 0
                rows = conn.execute(text(f"SELECT id, title, description, question, enabled, create_time, update_time FROM t_sample_question WHERE {where} ORDER BY create_time DESC LIMIT :limit OFFSET :offset"), params).mappings()
                records = [{**dict(r), "createTime": str(r["create_time"]) if r["create_time"] else None, "updateTime": str(r["update_time"]) if r["update_time"] else None} for r in rows]
                return {"records": records, "total": total, "size": size, "current": current, "pages": (total + size - 1) // size if size else 0}

        def fallback() -> dict[str, Any] | list[dict[str, Any]]:
            records = store.list_values("sample_questions")
            if title:
                records = [r for r in records if title in (r.get("title") or "")]
            return page(records, current, size) if current is not None and size is not None else records

        return self._with_fallback(db_action, fallback)

    def get_sample_question(self, item_id: str) -> dict[str, Any] | None:
        return self._with_fallback(
            lambda: self._fetch_one("SELECT id, title, description, question, enabled FROM t_sample_question WHERE id = :id AND deleted = 0", {"id": item_id}),
            lambda: store.get("sample_questions", item_id),
        )

    def create_sample_question(self, payload: dict[str, Any]) -> str:
        item_id = str(payload.get("id") or new_id())

        def fallback() -> str:
            return str(store.create("sample_questions", {"id": item_id, **payload})["id"])

        def db_action() -> str:
            with engine.begin() as conn:
                conn.execute(
                    text("INSERT INTO t_sample_question (id, title, description, question, enabled, create_time, update_time, deleted) VALUES (:id, :title, :description, :question, :enabled, now(), now(), 0)"),
                    {"id": item_id, "title": payload.get("title"), "description": payload.get("description"), "question": payload.get("question"), "enabled": int(payload.get("enabled", 1))},
                )
            fallback()
            return item_id

        return self._with_fallback(db_action, fallback)

    def update_sample_question(self, item_id: str, payload: dict[str, Any]) -> None:
        self._update_table("t_sample_question", item_id, {"title": payload.get("title"), "description": payload.get("description"), "question": payload.get("question"), "enabled": payload.get("enabled")}, lambda: store.update("sample_questions", item_id, payload))

    def delete_sample_question(self, item_id: str) -> None:
        self._soft_delete("t_sample_question", item_id, lambda: store.delete("sample_questions", item_id))

    def list_mappings(self, current: int = 1, size: int = 10, keyword: str | None = None) -> dict[str, Any]:
        def db_action() -> dict[str, Any]:
            where = "deleted = 0"
            params: dict[str, Any] = {"limit": size, "offset": max(current - 1, 0) * size}
            if keyword:
                where += " AND (source_term ILIKE :keyword OR target_term ILIKE :keyword OR domain ILIKE :keyword)"
                params["keyword"] = f"%{keyword}%"
            with engine.connect() as conn:
                total = conn.execute(text(f"SELECT count(*) FROM t_query_term_mapping WHERE {where}"), params).scalar() or 0
                rows = conn.execute(text(f"SELECT id, domain, source_term, target_term, match_type, priority, enabled, remark FROM t_query_term_mapping WHERE {where} ORDER BY priority DESC, create_time DESC LIMIT :limit OFFSET :offset"), params).mappings()
                records = [
                    {
                        "id": r["id"],
                        "domain": r["domain"],
                        "sourceTerm": r["source_term"],
                        "targetTerm": r["target_term"],
                        "matchType": r["match_type"],
                        "priority": r["priority"],
                        "enabled": r["enabled"],
                        "remark": r["remark"],
                    }
                    for r in rows
                ]
                return {"records": records, "total": total, "size": size, "current": current, "pages": (total + size - 1) // size if size else 0}

        def fallback() -> dict[str, Any]:
            records = [m for m in store.list_values("mappings") if m.get("type") != "feedback"]
            if keyword:
                records = [m for m in records if keyword in str(m)]
            return page(records, current, size)

        return self._with_fallback(db_action, fallback)

    def get_mapping(self, item_id: str) -> dict[str, Any] | None:
        return self._with_fallback(lambda: self._fetch_one("SELECT id, domain, source_term AS \"sourceTerm\", target_term AS \"targetTerm\", match_type AS \"matchType\", priority, enabled, remark FROM t_query_term_mapping WHERE id = :id AND deleted = 0", {"id": item_id}), lambda: store.get("mappings", item_id))

    def create_mapping(self, payload: dict[str, Any]) -> str:
        item_id = str(payload.get("id") or new_id())

        def fallback() -> str:
            return str(store.create("mappings", {"id": item_id, **payload})["id"])

        def db_action() -> str:
            with engine.begin() as conn:
                conn.execute(
                    text("INSERT INTO t_query_term_mapping (id, domain, source_term, target_term, match_type, priority, enabled, remark, create_time, update_time, deleted) VALUES (:id, :domain, :source_term, :target_term, :match_type, :priority, :enabled, :remark, now(), now(), 0)"),
                    {"id": item_id, "domain": payload.get("domain"), "source_term": payload.get("sourceTerm") or payload.get("source_term"), "target_term": payload.get("targetTerm") or payload.get("target_term"), "match_type": payload.get("matchType") or payload.get("match_type"), "priority": payload.get("priority", 0), "enabled": int(payload.get("enabled", 1)), "remark": payload.get("remark")},
                )
            fallback()
            return item_id

        return self._with_fallback(db_action, fallback)

    def update_mapping(self, item_id: str, payload: dict[str, Any]) -> None:
        values = {"domain": payload.get("domain"), "source_term": payload.get("sourceTerm") or payload.get("source_term"), "target_term": payload.get("targetTerm") or payload.get("target_term"), "match_type": payload.get("matchType") or payload.get("match_type"), "priority": payload.get("priority"), "enabled": payload.get("enabled"), "remark": payload.get("remark")}
        self._update_table("t_query_term_mapping", item_id, values, lambda: store.update("mappings", item_id, payload))

    def delete_mapping(self, item_id: str) -> None:
        self._soft_delete("t_query_term_mapping", item_id, lambda: store.delete("mappings", item_id))

    def list_intent_nodes(self) -> list[dict[str, Any]]:
        def db_action() -> list[dict[str, Any]]:
            with engine.connect() as conn:
                rows = conn.execute(
                    text("SELECT id, kb_id, intent_code, name, level, parent_code, description, examples, collection_name, top_k, mcp_tool_id, kind, prompt_snippet, prompt_template, param_prompt_template, sort_order, enabled FROM t_intent_node WHERE deleted = 0 ORDER BY sort_order ASC, create_time ASC")
                ).mappings()
                return [
                    {
                        "id": r["id"],
                        "kbId": r["kb_id"],
                        "intentCode": r["intent_code"],
                        "name": r["name"],
                        "level": r["level"],
                        "parentCode": r["parent_code"],
                        "description": r["description"],
                        "examples": r["examples"],
                        "collectionName": r["collection_name"],
                        "topK": r["top_k"],
                        "mcpToolId": r["mcp_tool_id"],
                        "kind": r["kind"],
                        "promptSnippet": r["prompt_snippet"],
                        "promptTemplate": r["prompt_template"],
                        "paramPromptTemplate": r["param_prompt_template"],
                        "sortOrder": r["sort_order"],
                        "enabled": r["enabled"],
                    }
                    for r in rows
                ]

        return self._with_fallback(db_action, lambda: store.list_values("intent_nodes"))

    def create_intent_node(self, payload: dict[str, Any]) -> str:
        item_id = str(payload.get("id") or new_id())

        def fallback() -> str:
            return str(store.create("intent_nodes", {"id": item_id, **payload})["id"])

        def db_action() -> str:
            values = self._intent_values(item_id, payload)
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO t_intent_node (id, kb_id, intent_code, name, level, parent_code, description, examples, collection_name, top_k, mcp_tool_id, kind, prompt_snippet, prompt_template, param_prompt_template, sort_order, enabled, create_time, update_time, deleted) "
                        "VALUES (:id, :kb_id, :intent_code, :name, :level, :parent_code, :description, :examples, :collection_name, :top_k, :mcp_tool_id, :kind, :prompt_snippet, :prompt_template, :param_prompt_template, :sort_order, :enabled, now(), now(), 0)"
                    ),
                    values,
                )
            fallback()
            return item_id

        return self._with_fallback(db_action, fallback)

    def update_intent_node(self, item_id: str, payload: dict[str, Any]) -> None:
        values = self._intent_values(item_id, payload)
        values.pop("id", None)
        self._update_table("t_intent_node", item_id, values, lambda: store.update("intent_nodes", item_id, payload))

    def delete_intent_node(self, item_id: str) -> None:
        self._soft_delete("t_intent_node", item_id, lambda: store.delete("intent_nodes", item_id))

    def batch_intent_nodes(self, ids: list[str], action: str) -> None:
        def fallback() -> None:
            for item_id in ids:
                if action == "delete":
                    store.delete("intent_nodes", item_id)
                else:
                    store.update("intent_nodes", item_id, {"enabled": 1 if action == "enable" else 0})

        def db_action() -> None:
            if not ids:
                return
            with engine.begin() as conn:
                if action == "delete":
                    conn.execute(text("UPDATE t_intent_node SET deleted = 1, update_time = now() WHERE id = ANY(:ids)"), {"ids": ids})
                else:
                    conn.execute(text("UPDATE t_intent_node SET enabled = :enabled, update_time = now() WHERE id = ANY(:ids)"), {"ids": ids, "enabled": 1 if action == "enable" else 0})
            fallback()

        self._with_fallback(db_action, fallback)

    def list_ingestion_pipelines(self, current: int = 1, size: int = 10) -> dict[str, Any]:
        return self._list_table_page(
            "t_ingestion_pipeline",
            "SELECT id, name, description, create_time, update_time FROM t_ingestion_pipeline WHERE deleted = 0 ORDER BY create_time DESC LIMIT :limit OFFSET :offset",
            lambda: page(store.list_values("pipelines"), current, size),
            current,
            size,
        )

    def create_ingestion_pipeline(self, payload: dict[str, Any], user_id: str) -> dict[str, Any]:
        item_id = str(payload.get("id") or new_id())

        def fallback() -> dict[str, Any]:
            return store.create("pipelines", {"id": item_id, **payload, "createdBy": user_id, "updatedBy": user_id})

        def db_action() -> dict[str, Any]:
            with engine.begin() as conn:
                conn.execute(text("INSERT INTO t_ingestion_pipeline (id, name, description, created_by, updated_by, create_time, update_time, deleted) VALUES (:id, :name, :description, :created_by, :updated_by, now(), now(), 0)"), {"id": item_id, "name": payload.get("name"), "description": payload.get("description"), "created_by": user_id, "updated_by": user_id})
            return fallback()

        return self._with_fallback(db_action, fallback)

    def get_ingestion_pipeline(self, item_id: str) -> dict[str, Any] | None:
        return self._with_fallback(lambda: self._fetch_one("SELECT id, name, description, created_by AS \"createdBy\", updated_by AS \"updatedBy\" FROM t_ingestion_pipeline WHERE id = :id AND deleted = 0", {"id": item_id}), lambda: store.get("pipelines", item_id))

    def update_ingestion_pipeline(self, item_id: str, payload: dict[str, Any], user_id: str) -> dict[str, Any] | None:
        self._update_table("t_ingestion_pipeline", item_id, {"name": payload.get("name"), "description": payload.get("description"), "updated_by": user_id}, lambda: store.update("pipelines", item_id, payload))
        return self.get_ingestion_pipeline(item_id)

    def delete_ingestion_pipeline(self, item_id: str) -> None:
        self._soft_delete("t_ingestion_pipeline", item_id, lambda: store.delete("pipelines", item_id))

    def list_ingestion_tasks(self, current: int = 1, size: int = 10, status: str | None = None) -> dict[str, Any]:
        def db_action() -> dict[str, Any]:
            where = "deleted = 0"
            params: dict[str, Any] = {"limit": size, "offset": max(current - 1, 0) * size}
            if status:
                where += " AND status = :status"
                params["status"] = status
            with engine.connect() as conn:
                total = conn.execute(text(f"SELECT count(*) FROM t_ingestion_task WHERE {where}"), params).scalar() or 0
                rows = conn.execute(text(f"SELECT id, pipeline_id, source_type, source_location, source_file_name, status, chunk_count, error_message, metadata_json, create_time, update_time FROM t_ingestion_task WHERE {where} ORDER BY create_time DESC LIMIT :limit OFFSET :offset"), params).mappings()
                records = [self._task_record(r) for r in rows]
                return {"records": records, "total": total, "size": size, "current": current, "pages": (total + size - 1) // size if size else 0}

        def fallback() -> dict[str, Any]:
            records = sorted(store.list_values("tasks"), key=lambda item: item.get("createTime", ""), reverse=True)
            if status:
                records = [record for record in records if record.get("status") == status]
            return page(records, current, size)

        return self._with_fallback(db_action, fallback)

    def create_ingestion_task(self, payload: dict[str, Any], user_id: str) -> dict[str, Any]:
        item_id = str(payload.get("id") or new_id())
        nodes = self._build_ingestion_task_nodes(item_id, payload)

        def fallback() -> dict[str, Any]:
            task = store.create("tasks", {"id": item_id, "status": payload.get("status", "pending"), "chunkCount": payload.get("chunkCount", 0), **payload, "createdBy": user_id})
            store.ingestion_task_nodes[item_id] = nodes
            return task

        def db_action() -> dict[str, Any]:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO t_ingestion_task (id, pipeline_id, source_type, source_location, source_file_name, status, chunk_count, error_message, logs_json, metadata_json, created_by, updated_by, create_time, update_time, deleted) "
                        "VALUES (:id, :pipeline_id, :source_type, :source_location, :source_file_name, :status, :chunk_count, :error_message, CAST(:logs_json AS jsonb), CAST(:metadata_json AS jsonb), :created_by, :updated_by, now(), now(), 0)"
                    ),
                    {
                        "id": item_id,
                        "pipeline_id": payload.get("pipelineId") or payload.get("pipeline_id"),
                        "source_type": payload.get("sourceType") or payload.get("source_type"),
                        "source_location": payload.get("sourceLocation") or payload.get("source_location"),
                        "source_file_name": payload.get("sourceFileName") or payload.get("source_file_name"),
                        "status": payload.get("status", "pending"),
                        "chunk_count": payload.get("chunkCount", 0),
                        "error_message": payload.get("errorMessage"),
                        "logs_json": json.dumps(payload.get("logs") or [], ensure_ascii=False),
                        "metadata_json": json.dumps(payload.get("metadata") or {}, ensure_ascii=False),
                        "created_by": user_id,
                        "updated_by": user_id,
                    },
                )
                for node in nodes:
                    conn.execute(
                        text(
                            "INSERT INTO t_ingestion_task_node (id, task_id, pipeline_id, node_id, node_type, node_order, status, duration_ms, message, error_message, output_json, create_time, update_time, deleted) "
                            "VALUES (:id, :task_id, :pipeline_id, :node_id, :node_type, :node_order, :status, :duration_ms, :message, :error_message, CAST(:output_json AS jsonb), now(), now(), 0)"
                        ),
                        {
                            "id": node["id"],
                            "task_id": item_id,
                            "pipeline_id": node.get("pipelineId"),
                            "node_id": node.get("nodeId"),
                            "node_type": node.get("nodeType"),
                            "node_order": node.get("nodeOrder"),
                            "status": node.get("status"),
                            "duration_ms": node.get("durationMs"),
                            "message": node.get("message"),
                            "error_message": node.get("errorMessage"),
                            "output_json": json.dumps(node.get("output") or {}, ensure_ascii=False),
                        },
                    )
            return fallback()

        return self._with_fallback(db_action, fallback)

    def get_ingestion_task(self, item_id: str) -> dict[str, Any] | None:
        return self._with_fallback(lambda: self._fetch_one("SELECT id, pipeline_id AS \"pipelineId\", source_type AS \"sourceType\", source_location AS \"sourceLocation\", source_file_name AS \"sourceFileName\", status, chunk_count AS \"chunkCount\", error_message AS \"errorMessage\", metadata_json AS metadata FROM t_ingestion_task WHERE id = :id AND deleted = 0", {"id": item_id}), lambda: store.get("tasks", item_id))

    def list_ingestion_task_nodes(self, task_id: str) -> list[dict[str, Any]]:
        def db_action() -> list[dict[str, Any]]:
            with engine.connect() as conn:
                rows = conn.execute(text("SELECT id, task_id, pipeline_id, node_id, node_type, node_order, status, duration_ms, message, error_message, output_json FROM t_ingestion_task_node WHERE task_id = :task_id AND deleted = 0 ORDER BY node_order ASC, create_time ASC"), {"task_id": task_id}).mappings()
                return [
                    {"id": r["id"], "taskId": r["task_id"], "pipelineId": r["pipeline_id"], "nodeId": r["node_id"], "nodeType": r["node_type"], "nodeOrder": r["node_order"], "status": r["status"], "durationMs": r["duration_ms"], "message": r["message"], "errorMessage": r["error_message"], "output": r["output_json"]}
                    for r in rows
                ]

        return self._with_fallback(db_action, lambda: store.ingestion_task_nodes.get(task_id, []))

    def dashboard_overview(self) -> dict[str, Any]:
        def db_action() -> dict[str, Any]:
            with engine.connect() as conn:
                overview = {
                    "knowledgeBaseCount": conn.execute(text("SELECT count(*) FROM t_knowledge_base WHERE deleted = 0")).scalar() or 0,
                    "documentCount": conn.execute(text("SELECT count(*) FROM t_knowledge_document WHERE deleted = 0")).scalar() or 0,
                    "chunkCount": conn.execute(text("SELECT count(*) FROM t_knowledge_chunk WHERE deleted = 0")).scalar() or 0,
                    "conversationCount": conn.execute(text("SELECT count(*) FROM t_conversation WHERE deleted = 0")).scalar() or 0,
                    "traceCount": conn.execute(text("SELECT count(*) FROM t_rag_trace_run WHERE deleted = 0")).scalar() or 0,
                    "requestCount": conn.execute(text("SELECT count(*) FROM t_message WHERE deleted = 0")).scalar() or 0,
                }
                overview["supportQuality"] = self._dashboard_support_quality_db(conn)
                return overview

        return self._with_fallback(
            db_action,
            lambda: {
                "knowledgeBaseCount": len(store.knowledge_bases),
                "documentCount": len(store.documents),
                "chunkCount": len(store.chunks),
                "conversationCount": len(store.conversations),
                "traceCount": len(store.traces),
                "requestCount": sum(len(messages) for messages in store.messages.values()),
                "supportQuality": self._dashboard_support_quality_fallback(),
            },
        )

    def dashboard_performance(self) -> dict[str, Any]:
        def db_action() -> dict[str, Any]:
            with engine.connect() as conn:
                total = conn.execute(text("SELECT count(*) FROM t_rag_trace_run WHERE deleted = 0")).scalar() or 0
                completed = conn.execute(text("SELECT count(*) FROM t_rag_trace_run WHERE deleted = 0 AND upper(status) IN ('COMPLETED','SUCCESS')")).scalar() or 0
                avg_latency = conn.execute(text("SELECT coalesce(avg(duration_ms), 0) FROM t_rag_trace_run WHERE deleted = 0")).scalar() or 0
                return {"avgLatencyMs": int(avg_latency), "successRate": float(completed / total) if total else 1.0, "totalRequests": total}

        return self._with_fallback(db_action, lambda: {"avgLatencyMs": 0, "successRate": 1.0, "totalRequests": sum(len(messages) for messages in store.messages.values())})

    def dashboard_trends(self) -> dict[str, Any]:
        def db_action() -> dict[str, Any]:
            with engine.connect() as conn:
                rows = conn.execute(text("SELECT date(create_time) AS day, count(*) AS count FROM t_rag_trace_run WHERE deleted = 0 GROUP BY date(create_time) ORDER BY day DESC LIMIT 14")).mappings()
                items = [{"date": str(r["day"]), "count": r["count"]} for r in rows]
                return {"items": list(reversed(items))}

        return self._with_fallback(db_action, lambda: {"items": []})

    def _dashboard_support_quality_db(self, conn: Any) -> dict[str, Any]:
        total = conn.execute(text("SELECT count(*) FROM t_rag_trace_run WHERE deleted = 0")).scalar() or 0
        tool_calls = conn.execute(text("SELECT count(*) FROM t_rag_trace_node WHERE deleted = 0 AND upper(node_type) IN ('TOOL_CALL','MCP','MCP_TOOL')")).scalar() or 0
        no_answer = conn.execute(
            text(
                "SELECT count(*) FROM t_rag_trace_node "
                "WHERE deleted = 0 AND upper(node_type) = 'RETRIEVE' "
                "AND coalesce((extra_data::jsonb ->> 'chunkCount')::int, 0) = 0 "
                "AND coalesce((extra_data::jsonb ->> 'hasMcp')::boolean, false) = false"
            )
        ).scalar() or 0
        escalation = conn.execute(
            text(
                "SELECT count(*) FROM t_rag_trace_run "
                "WHERE deleted = 0 AND (lower(trace_name) LIKE '%smoke%' OR lower(trace_name) LIKE '%burning%' "
                "OR lower(trace_name) LIKE '%injury%' OR lower(trace_name) LIKE '%escalation%' OR lower(trace_name) LIKE '%privacy%' "
                "OR lower(trace_name) LIKE '%legal%')"
            )
        ).scalar() or 0
        feedback_rows = conn.execute(
            text(
                "SELECT id, message_id, feedback_type, content, create_time FROM t_message_feedback "
                "WHERE deleted = 0 AND lower(feedback_type) IN ('dislike','down','negative','bad') "
                "ORDER BY create_time DESC LIMIT 5"
            )
        ).mappings()
        intent_rows = conn.execute(
            text(
                "SELECT node_name, count(*) AS count FROM t_rag_trace_node "
                "WHERE deleted = 0 AND upper(node_type) = 'INTENT' "
                "GROUP BY node_name ORDER BY count DESC LIMIT 5"
            )
        ).mappings()
        return {
            "totalSupportQuestions": int(total),
            "noAnswerCount": int(no_answer),
            "toolCallCount": int(tool_calls),
            "escalationCount": int(escalation),
            "topIntents": [{"intent": row["node_name"] or "unknown", "count": int(row["count"])} for row in intent_rows],
            "recentLowQualityFeedback": [
                {
                    "id": row["id"],
                    "messageId": row["message_id"],
                    "feedbackType": row["feedback_type"],
                    "content": row["content"],
                    "createTime": str(row["create_time"]) if row["create_time"] else None,
                }
                for row in feedback_rows
            ],
        }

    def _dashboard_support_quality_fallback(self) -> dict[str, Any]:
        traces = store.list_values("traces")
        nodes_by_trace = store.trace_nodes
        intent_counts: dict[str, int] = {}
        no_answer = 0
        tool_calls = 0
        escalation = 0
        escalation_terms = ("smoke", "burning", "injury", "escalation", "privacy", "legal", "smoking", "冒烟", "升级")

        for trace in traces:
            trace_id = str(trace.get("traceId") or trace.get("id") or "")
            question = str(trace.get("question") or "").lower()
            if any(term in question for term in escalation_terms):
                escalation += 1
            for node in nodes_by_trace.get(trace_id, []):
                node_type = str(node.get("nodeType") or "").upper()
                node_name = str(node.get("nodeName") or node.get("intentCode") or "unknown")
                if node_type == "INTENT":
                    intent_counts[node_name] = intent_counts.get(node_name, 0) + 1
                if node_type in {"TOOL_CALL", "MCP", "MCP_TOOL"}:
                    tool_calls += 1
                if node_type == "RETRIEVE" and int(node.get("chunkCount") or 0) == 0 and not bool(node.get("hasMcp")):
                    no_answer += 1

        low_quality = [
            feedback
            for feedback in store.list_values("feedbacks")
            if str(feedback.get("feedbackType") or "").lower() in {"dislike", "down", "negative", "bad"}
        ]
        low_quality.sort(key=lambda item: str(item.get("createTime") or ""), reverse=True)

        return {
            "totalSupportQuestions": len(traces),
            "noAnswerCount": no_answer,
            "toolCallCount": tool_calls,
            "escalationCount": escalation,
            "topIntents": [
                {"intent": intent, "count": count}
                for intent, count in sorted(intent_counts.items(), key=lambda item: (-item[1], item[0]))[:5]
            ],
            "recentLowQualityFeedback": low_quality[:5],
        }

    def _fetch_one(self, sql: str, params: dict[str, Any]) -> dict[str, Any] | None:
        with engine.connect() as conn:
            row = conn.execute(text(sql), params).mappings().first()
            return dict(row) if row else None

    def _json_obj(self, raw: Any) -> dict[str, Any]:
        if isinstance(raw, dict):
            return raw
        if not raw:
            return {}
        try:
            data = json.loads(str(raw))
        except (TypeError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def _update_table(self, table: str, item_id: str, values: dict[str, Any], fallback: Callable[[], Any]) -> None:
        clean = {key: value for key, value in values.items() if value is not None}

        def db_action() -> None:
            if clean:
                assignments = ", ".join(f"{key} = :{key}" for key in clean)
                with engine.begin() as conn:
                    conn.execute(text(f"UPDATE {table} SET {assignments}, update_time = now() WHERE id = :id AND deleted = 0"), {"id": item_id, **clean})
            fallback()

        self._with_fallback(db_action, fallback)

    def _soft_delete(self, table: str, item_id: str, fallback: Callable[[], Any]) -> None:
        def db_action() -> None:
            with engine.begin() as conn:
                conn.execute(text(f"UPDATE {table} SET deleted = 1, update_time = now() WHERE id = :id"), {"id": item_id})
            fallback()

        self._with_fallback(db_action, fallback)

    def _list_table_page(self, table: str, sql: str, fallback: Callable[[], dict[str, Any]], current: int, size: int) -> dict[str, Any]:
        def db_action() -> dict[str, Any]:
            params = {"limit": size, "offset": max(current - 1, 0) * size}
            with engine.connect() as conn:
                total = conn.execute(text(f"SELECT count(*) FROM {table} WHERE deleted = 0")).scalar() or 0
                rows = conn.execute(text(sql), params).mappings()
                records = [dict(r) for r in rows]
                return {"records": records, "total": total, "size": size, "current": current, "pages": (total + size - 1) // size if size else 0}

        return self._with_fallback(db_action, fallback)

    def _intent_values(self, item_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": item_id,
            "kb_id": payload.get("kbId") or payload.get("kb_id"),
            "intent_code": payload.get("intentCode") or payload.get("intent_code") or item_id,
            "name": payload.get("name"),
            "level": payload.get("level", 1),
            "parent_code": payload.get("parentCode") or payload.get("parent_code"),
            "description": payload.get("description"),
            "examples": payload.get("examples"),
            "collection_name": payload.get("collectionName") or payload.get("collection_name"),
            "top_k": payload.get("topK") or payload.get("top_k"),
            "mcp_tool_id": payload.get("mcpToolId") or payload.get("mcp_tool_id"),
            "kind": payload.get("kind", "kb"),
            "prompt_snippet": payload.get("promptSnippet") or payload.get("prompt_snippet"),
            "prompt_template": payload.get("promptTemplate") or payload.get("prompt_template"),
            "param_prompt_template": payload.get("paramPromptTemplate") or payload.get("param_prompt_template"),
            "sort_order": payload.get("sortOrder") or payload.get("sort_order") or 0,
            "enabled": int(payload.get("enabled", 1)),
        }

    def _task_record(self, row: Any) -> dict[str, Any]:
        return {
            "id": row["id"],
            "pipelineId": row["pipeline_id"],
            "sourceType": row["source_type"],
            "sourceLocation": row["source_location"],
            "sourceFileName": row["source_file_name"],
            "status": row["status"],
            "chunkCount": row["chunk_count"],
            "errorMessage": row["error_message"],
            "metadata": row["metadata_json"],
            "createTime": str(row["create_time"]) if row["create_time"] else None,
            "updateTime": str(row["update_time"]) if row["update_time"] else None,
        }

    def _build_ingestion_task_nodes(self, task_id: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
        pipeline_id = payload.get("pipelineId") or payload.get("pipeline_id")
        source_type = payload.get("sourceType") or payload.get("source_type") or "manual"
        source_location = payload.get("sourceLocation") or payload.get("source_location") or payload.get("sourceFileName") or payload.get("source_file_name")
        return [
            {
                "id": new_id(),
                "taskId": task_id,
                "pipelineId": pipeline_id,
                "nodeId": "accept-source",
                "nodeType": "SOURCE",
                "nodeOrder": 1,
                "status": "completed",
                "durationMs": 0,
                "message": f"Accepted {source_type} source",
                "errorMessage": None,
                "output": {"sourceType": source_type, "sourceLocation": source_location},
                "createTime": now_text(),
            },
            {
                "id": new_id(),
                "taskId": task_id,
                "pipelineId": pipeline_id,
                "nodeId": "enqueue-task",
                "nodeType": "QUEUE",
                "nodeOrder": 2,
                "status": "completed",
                "durationMs": 0,
                "message": "Published ingestion task event",
                "errorMessage": None,
                "output": {"status": payload.get("status", "pending")},
                "createTime": now_text(),
            },
        ]

    def _cosine(self, left: list[float], right: list[float]) -> float:
        if not left or not right:
            return 0.0
        length = min(len(left), len(right))
        dot = sum(float(left[i]) * float(right[i]) for i in range(length))
        left_norm = sum(float(value) * float(value) for value in left[:length]) ** 0.5
        right_norm = sum(float(value) * float(value) for value in right[:length]) ** 0.5
        if not left_norm or not right_norm:
            return 0.0
        return dot / (left_norm * right_norm)


repository = Repository()
