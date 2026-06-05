from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import settings
from app.db.repository import repository
from app.infra.llm import EmbeddingClient, RerankClient
from app.infra.milvus import milvus_client
from app.rag.prompt import PromptTemplateLoader


@dataclass
class RetrievedChunk:
    id: str
    kb_id: str | None
    doc_id: str | None
    content: str
    score: float
    channel: str


def _score(query: str, content: str) -> float:
    query_terms = {term.lower() for term in query.split() if term.strip()}
    content_lower = content.lower()
    if not query_terms:
        return 0.0
    hits = sum(1 for term in query_terms if term in content_lower)
    if query and query.lower() in content_lower:
        hits += 2
    return hits / (len(query_terms) + 2)


class RetrievalEngine:
    def __init__(self) -> None:
        self.embedding_client = EmbeddingClient()
        self.rerank_client = RerankClient()
        self.loader = PromptTemplateLoader()

    async def retrieve_async(self, sub_intents: list[dict], top_k: int = 5) -> dict:
        if not sub_intents:
            return {"chunks": [], "kbContext": "", "mcpContext": "", "hasKb": False, "hasMcp": False, "intentChunks": {}}

        contexts = await asyncio.gather(*(self._build_sub_context(item, top_k) for item in sub_intents))
        multi = len(contexts) > 1
        kb_parts: list[str] = []
        mcp_parts: list[str] = []
        all_chunks: list[RetrievedChunk] = []
        intent_chunks: dict[str, list[RetrievedChunk]] = {}

        for index, context in enumerate(contexts, start=1):
            all_chunks.extend(context["chunks"])
            intent_chunks.update(context["intentChunks"])
            if context["kbContext"]:
                kb_parts.append(self._wrap_sub_question("sub-question-kb-wrapper", index, context["question"], context["kbContext"]) if multi else context["kbContext"])
            if context["mcpContext"]:
                mcp_parts.append(self._wrap_sub_question("sub-question-mcp-wrapper", index, context["question"], context["mcpContext"]) if multi else context["mcpContext"])

        kb_intents = [score for item in sub_intents for score in item.get("nodeScores", []) if self._kind(score.get("node") or score) == "kb"]
        mcp_intents = [score for item in sub_intents for score in item.get("nodeScores", []) if self._kind(score.get("node") or score) == "mcp"]
        return {
            "chunks": all_chunks,
            "kbContext": "\n\n".join(kb_parts).strip(),
            "mcpContext": "\n\n".join(mcp_parts).strip(),
            "hasKb": any(part.strip() for part in kb_parts),
            "hasMcp": any(part.strip() for part in mcp_parts),
            "intentChunks": intent_chunks,
            "kbIntents": kb_intents,
            "mcpIntents": mcp_intents,
        }

    async def _build_sub_context(self, intent: dict, top_k: int) -> dict[str, Any]:
        question = intent.get("subQuestion", "")
        kb_intents = [score for score in intent.get("nodeScores", []) if self._kind(score.get("node") or score) == "kb"]
        mcp_intents = [score for score in intent.get("nodeScores", []) if self._kind(score.get("node") or score) == "mcp"]
        if not intent.get("nodeScores") and intent.get("kind") == "kb":
            kb_intents = [intent]
        if not intent.get("nodeScores") and intent.get("kind") == "mcp":
            mcp_intents = [intent]

        sub_top_k = self._top_k(kb_intents, top_k)
        chunks = await self._retrieve_kb(question, sub_top_k) if kb_intents else []
        kb_context = self._format_kb_context(kb_intents, chunks, sub_top_k) if chunks else ""
        mcp_context = await self._execute_mcp(question, mcp_intents) if mcp_intents else ""
        intent_chunks = self._intent_chunks(kb_intents, chunks)
        return {"question": question, "chunks": chunks, "kbContext": kb_context, "mcpContext": mcp_context, "intentChunks": intent_chunks}

    async def _retrieve_kb(self, query: str, top_k: int) -> list[RetrievedChunk]:
        candidates: list[RetrievedChunk] = []
        if query:
            embedding = await self.embedding_client.embed(query)
            vector_rows = []
            if settings.vector_provider == "milvus":
                vector_rows = await milvus_client.search("rag_default_store", embedding, top_k=top_k * 3)
            if not vector_rows:
                vector_rows = repository.search_vectors(embedding, query, top_k=top_k * 3)
            for row in vector_rows:
                metadata = row.get("metadata") or {}
                content = row.get("content") or ""
                candidates.append(RetrievedChunk(str(row["id"]), metadata.get("kb_id"), metadata.get("doc_id"), content, float(row.get("score") or 0), row.get("channel", "pgvector")))

        for chunk in repository.list_chunks(limit=300):
            content = chunk.get("content") or ""
            score = _score(query, content)
            if score > 0:
                candidates.append(RetrievedChunk(str(chunk["id"]), chunk.get("kbId"), chunk.get("docId"), content, score, "keyword-fallback"))

        deduped: dict[str, RetrievedChunk] = {}
        for item in sorted(candidates, key=lambda c: c.score, reverse=True):
            key = item.content.strip()
            if key and key not in deduped:
                deduped[key] = item
        chunks = list(deduped.values())
        rerank_order = await self.rerank_client.rerank(query, [chunk.content for chunk in chunks])
        ordered = [chunks[idx] for idx in rerank_order if 0 <= idx < len(chunks)]
        return (ordered or chunks)[:top_k]

    def _format_kb_context(self, intents: list[dict], chunks: list[RetrievedChunk], top_k: int) -> str:
        body = "\n\n".join(f"[{idx + 1}] {chunk.content}" for idx, chunk in enumerate(chunks[:top_k]))
        rules = self._joined_snippets(intents)
        snippet = self.loader.render_section("context-format.st", "snippet-rules", {"rules": rules}) if rules else ""
        return self.loader.render_section("context-format.st", "kb-section", {"snippet_section": snippet, "chunks_body": body}) or body

    async def _execute_mcp(self, question: str, intents: list[dict]) -> str:
        results: list[str] = []
        for intent in intents:
            node = intent.get("node") or intent
            tool_id = node.get("mcpToolId") or node.get("mcp_tool_id") or self._fallback_tool(question)
            if not tool_id:
                continue
            params = await self._extract_mcp_params(question, tool_id)
            try:
                async with httpx.AsyncClient(timeout=15, trust_env=False) as client:
                    response = await client.post(f"{settings.mcp_server_url.rstrip('/')}/tools/{tool_id}/invoke", json=params)
                    response.raise_for_status()
                    payload = response.json()
                text = payload.get("result") or "\n".join(item.get("text", "") for item in payload.get("content", []) if isinstance(item, dict))
                if text:
                    results.append(f"tool={tool_id}\n{text}")
            except Exception as exc:
                results.append(self.loader.render_section("context-format.st", "mcp-error", {"error_list": f"{tool_id}: {type(exc).__name__}: {exc}"}))
        if not results:
            return ""
        body = "\n\n".join(results)
        rules = self._joined_snippets(intents)
        snippet = self.loader.render_section("context-format.st", "mcp-intent-rules", {"rules": rules}) if rules else ""
        return self.loader.render_section("context-format.st", "mcp-section", {"snippet_section": snippet, "body": body}) or body

    async def _extract_mcp_params(self, question: str, tool_id: str) -> dict[str, Any]:
        if settings.chat_provider:
            tool_definition = await self._tool_definition(tool_id)
            if tool_definition:
                messages = [
                    {"role": "system", "content": self.loader.load("mcp-parameter-extract.st")},
                    {
                        "role": "user",
                        "content": self.loader.render(
                            "mcp-parameter-extract-user.st",
                            {"tool_definition": tool_definition, "user_question": question},
                        ),
                    },
                ]
                try:
                    from app.infra.llm import LLMClient

                    raw = await LLMClient().chat(messages, temperature=0.1, top_p=0.3)
                    parsed = self._parse_json_object(raw)
                    if parsed is not None:
                        return parsed
                except Exception:
                    pass
        return self._extract_mcp_params_rule(question, tool_id)

    async def _tool_definition(self, tool_id: str) -> str:
        try:
            async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
                response = await client.get(f"{settings.mcp_server_url.rstrip('/')}/tools")
                response.raise_for_status()
                payload = response.json()
        except Exception:
            return ""
        for tool in payload.get("tools", []):
            if tool.get("name") == tool_id:
                return json.dumps(tool, ensure_ascii=False)
        return ""

    def _parse_json_object(self, raw: str) -> dict[str, Any] | None:
        cleaned = re.sub(r"^```(?:json)?\s*", "", (raw or "").strip())
        cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None

    def _extract_mcp_params_rule(self, question: str, tool_id: str) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if "weather" in tool_id:
            city = re.search(r"([\u4e00-\u9fff]{2,8})(?:天气|气温|weather)", question, re.I)
            params["city"] = city.group(1) if city else question.strip()[:12]
            if "未来" in question or "forecast" in question.lower():
                params["queryType"] = "forecast"
        elif "sales" in tool_id:
            params["queryType"] = "ranking" if "排名" in question else "detail" if "明细" in question else "summary"
            params["period"] = "本月" if "本月" in question else "本周" if "本周" in question else "本月"
            limit = re.search(r"(?:top|前)\s*(\d+)", question, re.I)
            if limit:
                params["limit"] = int(limit.group(1))
        elif "ticket" in tool_id:
            params["queryType"] = "detail" if "明细" in question else "category" if "分类" in question else "summary"
        return params

    def _wrap_sub_question(self, section: str, index: int, question: str, context: str) -> str:
        return self.loader.render_section("context-format.st", section, {"index": str(index), "question": question, "context": context})

    def _intent_chunks(self, intents: list[dict], chunks: list[RetrievedChunk]) -> dict[str, list[RetrievedChunk]]:
        if not chunks:
            return {}
        if not intents:
            return {"multi_channel": chunks}
        return {str((intent.get("node") or intent).get("intentCode") or (intent.get("node") or intent).get("id") or "multi_channel"): chunks for intent in intents}

    def _joined_snippets(self, intents: list[dict]) -> str:
        snippets = []
        for intent in intents:
            node = intent.get("node") or intent
            snippet = node.get("promptSnippet") or node.get("prompt_snippet")
            if snippet:
                snippets.append(str(snippet))
        return "\n".join(snippets)

    def _top_k(self, intents: list[dict], fallback: int) -> int:
        values = []
        for intent in intents:
            node = intent.get("node") or intent
            value = node.get("topK") or node.get("top_k")
            if value:
                values.append(int(value))
        return max(values) if values else fallback

    def _fallback_tool(self, question: str) -> str:
        lowered = question.lower()
        if "weather" in lowered or "天气" in question:
            return "weather_query"
        if "ticket" in lowered or "工单" in question or "售后" in question:
            return "ticket_query"
        if "sales" in lowered or "销售" in question:
            return "sales_query"
        return ""

    def _kind(self, node: dict) -> str:
        kind = str(node.get("kind") or "").lower()
        if kind in {"2", "mcp"} or node.get("mcpToolId") or node.get("mcp_tool_id"):
            return "mcp"
        if kind in {"1", "system"}:
            return "system"
        return "kb"

    def retrieve(self, sub_intents: list[dict], top_k: int = 5) -> dict:
        return asyncio.run(self.retrieve_async(sub_intents, top_k))
