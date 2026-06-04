from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

from app.core.ids import new_id
from app.db.repository import repository
from app.infra.llm import LLMClient
from app.infra.task_state import task_state_store
from app.rag.intent import IntentResolver
from app.rag.prompt import RAGPromptService
from app.rag.retrieval import RetrievalEngine
from app.rag.rewrite import QueryRewriteService
from app.services.store import now_text, store

rewriter = QueryRewriteService()
intent_resolver = IntentResolver()
retrieval_engine = RetrievalEngine()
prompt_service = RAGPromptService()
llm_client = LLMClient()


def sse_event(event: str, data: object) -> str:
    payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


async def stream_chat(question: str, conversation_id: str | None, user_id: str, deep_thinking: bool) -> AsyncIterator[str]:
    actual_conversation_id = conversation_id or new_id()
    task_id = new_id()
    yield sse_event("meta", {"conversationId": actual_conversation_id, "taskId": task_id})
    if not task_state_store.register(task_id):
        yield sse_event("reject", {"type": "response", "delta": "当前排队中的聊天任务过多，请稍后重试。"})
        yield sse_event("done", "[DONE]")
        return

    try:
        repository.ensure_conversation(actual_conversation_id, user_id, question[:30] or "新对话")
        repository.append_message(actual_conversation_id, user_id, "user", question, new_id())
        history = repository.list_messages(actual_conversation_id, user_id)
        rewrite = rewriter.rewrite_with_split(question, history)
        intents = intent_resolver.resolve(rewrite["subQuestions"])
        retrieval = await retrieval_engine.retrieve_async(intents)
        messages = prompt_service.build_messages(rewrite["rewrittenQuestion"], history, retrieval, rewrite["subQuestions"])
        if deep_thinking:
            yield sse_event("message", {"type": "think", "delta": "正在分析问题和可用知识库。"})

        answer_parts: list[str] = []
        async for model_chunk in llm_client.stream_chat(messages, thinking=deep_thinking):
            answer_parts.append(model_chunk)
            chunks = [model_chunk[i : i + 12] for i in range(0, len(model_chunk), 12)]
            for chunk in chunks:
                if task_state_store.is_cancelled(task_id):
                    yield sse_event("finish", {"messageId": None, "title": None})
                    yield sse_event("done", "[DONE]")
                    return
                yield sse_event("message", {"type": "response", "delta": chunk})
                await asyncio.sleep(0.001)

        answer = "".join(answer_parts)
        if not answer:
            answer = "未检索到与问题相关的文档内容。"

        message_id = new_id()
        repository.append_message(actual_conversation_id, user_id, "assistant", answer, message_id, "正在分析问题和可用知识库。" if deep_thinking else None, 1 if deep_thinking else None)
        trace_id = task_id
        trace_nodes = [
            {"id": new_id(), "nodeId": "rewrite", "traceId": trace_id, "nodeName": "rewrite", "nodeType": "REWRITE", "status": "completed", "subQuestions": rewrite["subQuestions"]},
            {"id": new_id(), "nodeId": "retrieve", "traceId": trace_id, "nodeName": "retrieve", "nodeType": "RETRIEVE", "status": "completed", "chunkCount": len(retrieval.get("chunks", []))},
            {"id": new_id(), "nodeId": "llm", "traceId": trace_id, "nodeName": "llm", "nodeType": "GENERATE", "status": "completed"},
        ]
        repository.record_trace(trace_id, question, actual_conversation_id, task_id, user_id, trace_nodes)
        yield sse_event("finish", {"messageId": message_id, "title": store.conversations[actual_conversation_id]["title"]})
        yield sse_event("done", "[DONE]")
    finally:
        task_state_store.unregister(task_id)


def stop_task(task_id: str) -> None:
    task_state_store.cancel(task_id)
