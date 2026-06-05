from __future__ import annotations

import asyncio

from app.rag.intent import IntentResolver
from app.rag.memory import ConversationMemoryService
from app.rag.prompt import RAGPromptService
from app.rag.retrieval import RetrievalEngine
from app.rag.rewrite import QueryRewriteService
from app.rag.title import ConversationTitleGenerator
from app.services.store import store


def test_query_rewrite_splits_multiple_questions() -> None:
    result = QueryRewriteService().rewrite_with_split("A 是什么？B 怎么办？")
    assert result["rewrittenQuestion"]
    assert result["subQuestions"] == ["A 是什么", "B 怎么办"]


def test_intent_resolver_marks_mcp_keywords() -> None:
    intents = IntentResolver().resolve(["查天气", "知识库问题"])
    assert intents[0]["kind"] == "mcp"
    assert intents[1]["kind"] == "kb"


def test_retrieval_fallback_dedupes_chunks() -> None:
    doc_id = "doc-test"
    store.chunks.clear()
    store.create("chunks", {"kbId": "kb", "docId": doc_id, "content": "Ragent supports knowledge retrieval", "enabled": 1})
    store.create("chunks", {"kbId": "kb", "docId": doc_id, "content": "Ragent supports knowledge retrieval", "enabled": 1})
    result = RetrievalEngine().retrieve([{"subQuestion": "Ragent retrieval", "kind": "kb"}])
    assert result["hasKb"] is True
    assert len(result["chunks"]) == 1


def test_retrieval_reports_search_channels() -> None:
    store.chunks.clear()
    store.create("chunks", {"kbId": "kb", "docId": "doc-test", "content": "Ragent channel retrieval", "enabled": 1})
    result = RetrievalEngine().retrieve(
        [
            {
                "subQuestion": "Ragent retrieval",
                "nodeScores": [{"score": 0.5, "node": {"kind": "kb", "intentCode": "kb.general"}}],
            }
        ],
        top_k=3,
    )
    channel_names = {item["channelName"] for item in result["channelResults"]}
    assert {"intent-directed", "vector-global"}.issubset(channel_names)


def test_prompt_includes_context_and_question() -> None:
    messages = RAGPromptService().build_messages(
        "What is Ragent?",
        [],
        {"kbContext": "Ragent context"},
        ["What is Ragent?"],
    )
    assert messages[0]["role"] == "system"
    assert "Ragent context" in messages[-1]["content"]
    assert "What is Ragent?" in messages[-1]["content"]


def test_prompt_selects_mcp_template_for_mcp_only() -> None:
    messages = RAGPromptService().build_messages(
        "sales?",
        [],
        {"mcpContext": "sales data", "hasMcp": True, "hasKb": False},
        ["sales?"],
    )
    assert messages[0]["role"] == "system"
    assert "<tool-data>" in messages[-1]["content"]


def test_memory_wraps_summary() -> None:
    store.conversation_summaries.clear()
    store.messages.clear()
    store.conversation_summaries["c1:u1"] = {"content": "Previous summary", "lastMessageId": "m1"}
    store.messages["c1"] = [{"id": "m2", "conversationId": "c1", "userId": "u1", "role": "user", "content": "new question"}]
    history = ConversationMemoryService().load("c1", "u1")
    assert history[0]["role"] == "system"
    assert "<conversation-summary>" in history[0]["content"]


def test_memory_summary_is_disabled_by_default() -> None:
    store.conversation_summaries.clear()
    store.messages.clear()
    store.messages["c2"] = [
        {"id": f"m{i}", "conversationId": "c2", "userId": "u1", "role": "user" if i % 2 else "assistant", "content": f"message {i}"}
        for i in range(1, 25)
    ]
    asyncio.run(ConversationMemoryService(summary_enabled=False).compress_if_needed("c2", "u1"))
    assert store.conversation_summaries == {}


def test_title_generator_falls_back_without_provider() -> None:
    title = asyncio.run(ConversationTitleGenerator(max_chars=6).generate("abcdefghi"))
    assert title == "abcdef"
