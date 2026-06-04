from __future__ import annotations

from app.rag.intent import IntentResolver
from app.rag.prompt import RAGPromptService
from app.rag.retrieval import RetrievalEngine
from app.rag.rewrite import QueryRewriteService
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
