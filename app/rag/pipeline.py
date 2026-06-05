from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from app.core.ids import new_id
from app.db.repository import repository
from app.infra.llm import LLMClient
from app.infra.task_state import task_state_store
from app.rag.intent import IntentResolver
from app.rag.prompt import RAGPromptService
from app.rag.retrieval import RetrievalEngine
from app.rag.rewrite import QueryRewriteService
from app.services.store import store

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

        rewrite = await rewriter.rewrite_with_split_async(question, history)
        intents = await intent_resolver.resolve_async(rewrite)

        guidance = await _guidance_prompt(rewrite["rewrittenQuestion"], intents)
        if guidance:
            message_id = new_id()
            repository.append_message(actual_conversation_id, user_id, "assistant", guidance, message_id)
            _record_trace(task_id, question, actual_conversation_id, user_id, rewrite, {"chunks": [], "guidance": True})
            yield sse_event("message", {"type": "response", "delta": guidance})
            yield sse_event("finish", {"messageId": message_id, "title": _conversation_title(actual_conversation_id)})
            yield sse_event("done", "[DONE]")
            return

        if intents and all(intent_resolver.is_system_only(intent) for intent in intents):
            messages = _build_system_only_messages(rewrite["rewrittenQuestion"], history, intents)
            async for event in _stream_answer(actual_conversation_id, task_id, user_id, question, messages, deep_thinking, rewrite, {"chunks": []}):
                yield event
            return

        retrieval = await retrieval_engine.retrieve_async(intents)
        if not retrieval.get("hasKb") and not retrieval.get("hasMcp"):
            answer = "未检索到与问题相关的文档内容。"
            message_id = new_id()
            repository.append_message(actual_conversation_id, user_id, "assistant", answer, message_id)
            _record_trace(task_id, question, actual_conversation_id, user_id, rewrite, retrieval)
            yield sse_event("message", {"type": "response", "delta": answer})
            yield sse_event("finish", {"messageId": message_id, "title": _conversation_title(actual_conversation_id)})
            yield sse_event("done", "[DONE]")
            return

        messages = prompt_service.build_structured_messages(rewrite["rewrittenQuestion"], history, retrieval, rewrite["subQuestions"])
        if deep_thinking:
            yield sse_event("message", {"type": "think", "delta": "正在分析问题和可用上下文。"})
        async for event in _stream_answer(actual_conversation_id, task_id, user_id, question, messages, deep_thinking, rewrite, retrieval):
            yield event
    finally:
        task_state_store.unregister(task_id)


def stop_task(task_id: str) -> None:
    task_state_store.cancel(task_id)


def _build_system_only_messages(question: str, history: list[dict], intents: list[dict]) -> list[dict]:
    custom_prompt = ""
    for intent in intents:
        for score in intent.get("nodeScores") or []:
            node = score.get("node") or {}
            custom_prompt = node.get("promptTemplate") or node.get("prompt_template") or ""
            if custom_prompt:
                break
    system = custom_prompt or prompt_service.loader.load("answer-chat-system.st")
    messages = [{"role": "system", "content": system}]
    messages.extend({"role": item.get("role", "user"), "content": item.get("content", "")} for item in history[-8:])
    messages.append({"role": "user", "content": question})
    return messages


async def _guidance_prompt(question: str, intents: list[dict]) -> str:
    for intent in intents:
        scores = intent.get("nodeScores") or []
        if len(scores) < 2:
            continue
        sorted_scores = sorted(scores, key=lambda item: item.get("score", 0), reverse=True)
        top = float(sorted_scores[0].get("score") or 0)
        close = [item for item in sorted_scores if top - float(item.get("score") or 0) <= 0.15 and float(item.get("score") or 0) >= 0.4]
        if len(close) < 2:
            continue
        if not await _confirm_ambiguous(question, close):
            continue
        options = []
        for index, item in enumerate(close[:3], start=1):
            node = item.get("node") or {}
            name = node.get("name") or node.get("intentCode") or node.get("id") or f"选项{index}"
            description = node.get("description") or ""
            options.append(f"{index}. {name}" + (f"：{description}" if description else ""))
        topic_name = question[:30] or "该问题"
        return prompt_service.loader.render("guidance-prompt.st", {"topic_name": topic_name, "options": "\n".join(options)})
    return ""


async def _confirm_ambiguous(question: str, candidates: list[dict]) -> bool:
    candidate_text = "\n".join(
        f"- id={(item.get('node') or {}).get('intentCode') or (item.get('node') or {}).get('id')}; "
        f"name={(item.get('node') or {}).get('name')}; score={item.get('score')}"
        for item in candidates
    )
    prompt = prompt_service.loader.render("guidance-ambiguity-check.st", {"question": question, "candidates": candidate_text})
    if not prompt:
        return True
    try:
        raw = await llm_client.chat([{"role": "user", "content": prompt}], temperature=0.1, top_p=0.3)
        if not raw:
            return True
        data = json.loads(raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip())
        return bool(data.get("ambiguous"))
    except Exception:
        return True


async def _stream_answer(
    conversation_id: str,
    task_id: str,
    user_id: str,
    question: str,
    messages: list[dict],
    deep_thinking: bool,
    rewrite: dict,
    retrieval: dict,
) -> AsyncIterator[str]:
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

    answer = "".join(answer_parts) or "未检索到与问题相关的文档内容。"
    message_id = new_id()
    repository.append_message(
        conversation_id,
        user_id,
        "assistant",
        answer,
        message_id,
        "正在分析问题和可用上下文。" if deep_thinking else None,
        1 if deep_thinking else None,
    )
    _record_trace(task_id, question, conversation_id, user_id, rewrite, retrieval)
    yield sse_event("finish", {"messageId": message_id, "title": _conversation_title(conversation_id)})
    yield sse_event("done", "[DONE]")


def _record_trace(trace_id: str, question: str, conversation_id: str, user_id: str, rewrite: dict, retrieval: dict) -> None:
    trace_nodes = [
        {"id": new_id(), "nodeId": "rewrite", "traceId": trace_id, "nodeName": "query-rewrite-and-split", "nodeType": "REWRITE", "status": "completed", "subQuestions": rewrite.get("subQuestions", [])},
        {"id": new_id(), "nodeId": "intent", "traceId": trace_id, "nodeName": "intent-resolve", "nodeType": "INTENT", "status": "completed"},
        {"id": new_id(), "nodeId": "retrieve", "traceId": trace_id, "nodeName": "retrieval-engine", "nodeType": "RETRIEVE", "status": "completed", "chunkCount": len(retrieval.get("chunks", [])), "hasMcp": retrieval.get("hasMcp", False)},
        {"id": new_id(), "nodeId": "llm", "traceId": trace_id, "nodeName": "llm", "nodeType": "GENERATE", "status": "completed"},
    ]
    repository.record_trace(trace_id, question, conversation_id, trace_id, user_id, trace_nodes)


def _conversation_title(conversation_id: str) -> str | None:
    conversation = store.conversations.get(conversation_id)
    return conversation.get("title") if conversation else None
