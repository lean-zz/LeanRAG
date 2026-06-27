from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator

from app.core.ids import new_id
from app.db.repository import repository
from app.infra.llm import LLMClient
from app.infra.task_state import task_state_store
from app.rag.intent import IntentResolver
from app.rag.memory import ConversationMemoryService
from app.rag.prompt import RAGPromptService
from app.rag.reliability import assign_experiment_variant, build_reliability_decision, guardrail_check
from app.rag.retrieval import RetrievalEngine
from app.rag.rewrite import QueryRewriteService
from app.rag.title import ConversationTitleGenerator
from app.services.store import store

rewriter = QueryRewriteService()
intent_resolver = IntentResolver()
retrieval_engine = RetrievalEngine()
prompt_service = RAGPromptService()
memory_service = ConversationMemoryService()
title_generator = ConversationTitleGenerator()
llm_client = LLMClient()


def sse_event(event: str, data: object) -> str:
    payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


async def stream_chat(question: str, conversation_id: str | None, user_id: str, deep_thinking: bool) -> AsyncIterator[str]:
    started_at = time.monotonic()
    actual_conversation_id = conversation_id or new_id()
    task_id = new_id()
    yield sse_event("meta", {"conversationId": actual_conversation_id, "taskId": task_id})
    if not task_state_store.register(task_id):
        yield sse_event("reject", {"type": "response", "delta": "The chat queue is busy. Please retry later."})
        yield sse_event("done", "[DONE]")
        return

    try:
        assignment = assign_experiment_variant("reliability-v1", user_id, actual_conversation_id)
        guardrail = guardrail_check(question, user_id=user_id)
        title = question[:30] or "New conversation"
        if conversation_id is None:
            title = await title_generator.generate(question)
        repository.ensure_conversation(actual_conversation_id, user_id, title)
        repository.append_message(actual_conversation_id, user_id, "user", question, new_id())

        if guardrail["action"] == "block":
            answer = "This request cannot be answered because it attempts to override system or safety instructions."
            message_id = new_id()
            repository.append_message(actual_conversation_id, user_id, "assistant", answer, message_id)
            retrieval = _with_reliability({"chunks": [], "evidence": []}, guardrail, assignment["variant"])
            retrieval["decision"] = {"type": "refuse", "reasons": [guardrail["reason"]], "confidence": 1.0}
            _record_trace(task_id, question, actual_conversation_id, user_id, {"subQuestions": []}, retrieval, message_id=message_id, latency_ms=_elapsed_ms(started_at))
            yield sse_event("message", {"type": "response", "delta": answer})
            yield sse_event("finish", {"messageId": message_id, "title": _conversation_title(actual_conversation_id)})
            yield sse_event("done", "[DONE]")
            return

        history = memory_service.load(actual_conversation_id, user_id)
        rewrite = await rewriter.rewrite_with_split_async(guardrail.get("sanitizedText") or question, history)
        intents = await intent_resolver.resolve_async(rewrite)

        guidance = await _guidance_prompt(rewrite["rewrittenQuestion"], intents)
        if guidance:
            message_id = new_id()
            repository.append_message(actual_conversation_id, user_id, "assistant", guidance, message_id)
            retrieval = _with_reliability({"chunks": [], "evidence": [], "guidance": True}, guardrail, assignment["variant"])
            retrieval["decision"] = {"type": "clarify", "reasons": ["ambiguous_intent"], "confidence": 0.6}
            _record_trace(task_id, question, actual_conversation_id, user_id, rewrite, retrieval, message_id=message_id, latency_ms=_elapsed_ms(started_at))
            yield sse_event("message", {"type": "response", "delta": guidance})
            yield sse_event("finish", {"messageId": message_id, "title": _conversation_title(actual_conversation_id)})
            yield sse_event("done", "[DONE]")
            return

        if intents and all(intent_resolver.is_system_only(intent) for intent in intents):
            retrieval = _with_reliability({"chunks": [], "evidence": []}, guardrail, assignment["variant"])
            messages = _build_system_only_messages(rewrite["rewrittenQuestion"], history, intents)
            async for event in _stream_answer(actual_conversation_id, task_id, user_id, question, messages, deep_thinking, rewrite, retrieval, temperature=0.7, top_p=None, started_at=started_at):
                yield event
            return

        retrieval = await retrieval_engine.retrieve_async(intents)
        retrieval = _with_reliability(retrieval, guardrail, assignment["variant"])
        if not retrieval.get("hasKb") and not retrieval.get("hasMcp"):
            answer = "No relevant knowledge-base content was retrieved."
            message_id = new_id()
            repository.append_message(actual_conversation_id, user_id, "assistant", answer, message_id)
            _record_trace(task_id, question, actual_conversation_id, user_id, rewrite, retrieval, message_id=message_id, latency_ms=_elapsed_ms(started_at))
            yield sse_event("message", {"type": "response", "delta": answer})
            yield sse_event("finish", {"messageId": message_id, "title": _conversation_title(actual_conversation_id)})
            yield sse_event("done", "[DONE]")
            return

        messages = prompt_service.build_structured_messages(rewrite["rewrittenQuestion"], history, retrieval, rewrite["subQuestions"])
        if deep_thinking:
            yield sse_event("message", {"type": "think", "delta": "Analyzing the question and available context."})
        temperature = 0.3 if retrieval.get("hasMcp") else 0.0
        top_p = 0.8 if retrieval.get("hasMcp") else 1.0
        async for event in _stream_answer(actual_conversation_id, task_id, user_id, question, messages, deep_thinking, rewrite, retrieval, temperature=temperature, top_p=top_p, started_at=started_at):
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
            name = node.get("name") or node.get("intentCode") or node.get("id") or f"Option {index}"
            description = node.get("description") or ""
            options.append(f"{index}. {name}" + (f": {description}" if description else ""))
        topic_name = question[:30] or "this question"
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
    temperature: float | None = None,
    top_p: float | None = None,
    started_at: float | None = None,
) -> AsyncIterator[str]:
    answer_parts: list[str] = []
    try:
        async for model_chunk in llm_client.stream_chat(messages, thinking=deep_thinking, temperature=temperature, top_p=top_p):
            answer_parts.append(model_chunk)
            chunks = [model_chunk[i : i + 12] for i in range(0, len(model_chunk), 12)]
            for chunk in chunks:
                if task_state_store.is_cancelled(task_id):
                    yield sse_event("finish", {"messageId": None, "title": None})
                    yield sse_event("done", "[DONE]")
                    return
                yield sse_event("message", {"type": "response", "delta": chunk})
                await asyncio.sleep(0.001)
    except Exception as exc:
        partial = "".join(answer_parts)
        message_id = new_id()
        if partial:
            repository.append_message(conversation_id, user_id, "assistant", partial, message_id, "partial_answer", 0)
        retrieval["decision"] = {"type": "fallback", "reasons": ["llm_stream_failure"], "confidence": 0.3}
        retrieval.setdefault("traceNodes", []).append(
            {"nodeId": "llm-recoverable-error", "nodeName": "llm-stream-chat", "nodeType": "GENERATE", "status": "failed", "errorMessage": type(exc).__name__}
        )
        _record_trace(task_id, question, conversation_id, user_id, rewrite, retrieval, message_id=message_id if partial else None, latency_ms=_elapsed_ms(started_at) if started_at else None)
        yield sse_event("recoverable_error", {"type": "llm_stream_failure", "message": "Answer generation was interrupted.", "partial": bool(partial)})
        yield sse_event("finish", {"messageId": message_id if partial else None, "title": _conversation_title(conversation_id)})
        yield sse_event("done", "[DONE]")
        return

    answer = "".join(answer_parts) or "No relevant knowledge-base content was retrieved."
    message_id = new_id()
    repository.append_message(
        conversation_id,
        user_id,
        "assistant",
        answer,
        message_id,
        "Analyzing the question and available context." if deep_thinking else None,
        1 if deep_thinking else None,
    )
    await memory_service.compress_if_needed(conversation_id, user_id)
    _record_trace(task_id, question, conversation_id, user_id, rewrite, retrieval, message_id=message_id, latency_ms=_elapsed_ms(started_at) if started_at else None)
    yield sse_event("finish", {"messageId": message_id, "title": _conversation_title(conversation_id)})
    yield sse_event("done", "[DONE]")


def _record_trace(
    trace_id: str,
    question: str,
    conversation_id: str,
    user_id: str,
    rewrite: dict,
    retrieval: dict,
    message_id: str | None = None,
    latency_ms: int | None = None,
) -> None:
    guardrail = retrieval.get("guardrail") or {"action": "allow", "reason": "none", "summary": "allow:none"}
    decision = retrieval.get("decision") or build_reliability_decision(retrieval, guardrail)
    trace_nodes = [
        {"id": new_id(), "nodeId": "guardrail", "traceId": trace_id, "nodeName": "guardrail-check", "nodeType": "GUARDRAIL", "status": "completed", "outputJson": guardrail},
        {"id": new_id(), "nodeId": "rewrite", "traceId": trace_id, "nodeName": "query-rewrite-and-split", "nodeType": "REWRITE", "status": "completed", "subQuestions": rewrite.get("subQuestions", [])},
        {"id": new_id(), "nodeId": "intent", "traceId": trace_id, "nodeName": "intent-resolve", "nodeType": "INTENT", "status": "completed"},
        {"id": new_id(), "nodeId": "retrieve", "traceId": trace_id, "nodeName": "retrieval-engine", "nodeType": "RETRIEVE", "status": "completed", "chunkCount": len(retrieval.get("chunks", [])), "hasMcp": retrieval.get("hasMcp", False), "evidenceCount": len(retrieval.get("evidence") or [])},
        {"id": new_id(), "nodeId": "prompt-render", "traceId": trace_id, "nodeName": "prompt-render", "nodeType": "PROMPT", "status": "completed", "scene": "mixed" if retrieval.get("hasKb") and retrieval.get("hasMcp") else "mcp" if retrieval.get("hasMcp") else "kb"},
        {"id": new_id(), "nodeId": "decision", "traceId": trace_id, "nodeName": "reliability-decision", "nodeType": "DECISION", "status": "completed", "outputJson": decision},
        {"id": new_id(), "nodeId": "llm", "traceId": trace_id, "nodeName": "llm", "nodeType": "GENERATE", "status": "completed"},
    ]
    for node in retrieval.get("traceNodes") or []:
        trace_nodes.insert(-2, {"id": new_id(), "traceId": trace_id, **node})
    repository.record_trace(
        trace_id,
        question,
        conversation_id,
        trace_id,
        user_id,
        trace_nodes,
        evidence=retrieval.get("evidence") or [],
        decisions=[decision],
        guardrail=guardrail,
        variant=retrieval.get("variant"),
        message_id=message_id,
        latency_ms=latency_ms,
    )


def _with_reliability(retrieval: dict, guardrail: dict, variant: str) -> dict:
    next_retrieval = dict(retrieval)
    next_retrieval["guardrail"] = guardrail
    next_retrieval["variant"] = variant
    next_retrieval["decision"] = build_reliability_decision(next_retrieval, guardrail)
    return next_retrieval


def _conversation_title(conversation_id: str) -> str | None:
    conversation = store.conversations.get(conversation_id)
    return conversation.get("title") if conversation else None


def _elapsed_ms(started_at: float) -> int:
    return int((time.monotonic() - started_at) * 1000)
