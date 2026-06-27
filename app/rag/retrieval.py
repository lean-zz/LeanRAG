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


@dataclass
class ChannelSearchResult:
    channel_name: str
    priority: int
    chunks: list[RetrievedChunk]


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

    async def retrieve_async(self, sub_intents: list[dict], top_k: int | None = None) -> dict:
        top_k = top_k if top_k is not None else settings.rag_search_default_top_k
        if not sub_intents:
            return {"chunks": [], "kbContext": "", "mcpContext": "", "hasKb": False, "hasMcp": False, "intentChunks": {}, "channelResults": [], "evidence": [], "toolErrors": []}

        contexts = await asyncio.gather(*(self._build_sub_context(item, top_k) for item in sub_intents))
        multi = len(contexts) > 1
        kb_parts: list[str] = []
        mcp_parts: list[str] = []
        all_chunks: list[RetrievedChunk] = []
        intent_chunks: dict[str, list[RetrievedChunk]] = {}
        channel_results: list[dict[str, Any]] = []
        tool_errors: list[dict[str, Any]] = []

        for index, context in enumerate(contexts, start=1):
            all_chunks.extend(context["chunks"])
            intent_chunks.update(context["intentChunks"])
            channel_results.extend(context.get("channelResults") or [])
            tool_errors.extend(context.get("toolErrors") or [])
            if context["kbContext"]:
                kb_parts.append(self._wrap_sub_question("sub-question-kb-wrapper", index, context["question"], context["kbContext"]) if multi else context["kbContext"])
            if context["mcpContext"]:
                mcp_parts.append(self._wrap_sub_question("sub-question-mcp-wrapper", index, context["question"], context["mcpContext"]) if multi else context["mcpContext"])

        kb_intents = [score for item in sub_intents for score in item.get("nodeScores", []) if self._kind(score.get("node") or score) == "kb"]
        mcp_intents = [score for item in sub_intents for score in item.get("nodeScores", []) if self._kind(score.get("node") or score) == "mcp"]
        evidence = self._evidence_from_chunks(all_chunks, "retrieval-engine")
        evidence.extend(self._evidence_from_mcp_context("\n\n".join(mcp_parts), len(evidence) + 1, "mcp-tool-call"))
        return {
            "chunks": all_chunks,
            "kbContext": "\n\n".join(kb_parts).strip(),
            "mcpContext": "\n\n".join(mcp_parts).strip(),
            "hasKb": any(part.strip() for part in kb_parts),
            "hasMcp": any(part.strip() for part in mcp_parts),
            "intentChunks": intent_chunks,
            "kbIntents": kb_intents,
            "mcpIntents": mcp_intents,
            "channelResults": channel_results,
            "evidence": evidence,
            "toolErrors": tool_errors,
            "traceNodes": self._trace_nodes(contexts),
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
        channel_results = await self._retrieve_kb_channels(question, kb_intents, sub_top_k) if kb_intents else []
        chunks = await self._post_process_channel_results(question, channel_results, sub_top_k)
        kb_context = self._format_kb_context(kb_intents, chunks, sub_top_k) if chunks else ""
        mcp_result = await self._execute_mcp(question, mcp_intents) if mcp_intents else {"context": "", "toolErrors": []}
        mcp_context = mcp_result["context"]
        intent_chunks = self._intent_chunks(kb_intents, chunks)
        trace = self._channel_trace_nodes(question, channel_results, len(chunks), bool(mcp_context))
        return {
            "question": question,
            "chunks": chunks,
            "kbContext": kb_context,
            "mcpContext": mcp_context,
            "intentChunks": intent_chunks,
            "traceNodes": trace,
            "toolErrors": mcp_result.get("toolErrors") or [],
            "channelResults": [
                {"channelName": item.channel_name, "priority": item.priority, "chunkCount": len(item.chunks)}
                for item in channel_results
            ],
        }

    async def _retrieve_kb_channels(self, query: str, intents: list[dict], top_k: int) -> list[ChannelSearchResult]:
        results: list[ChannelSearchResult] = []
        directed_intents = [intent for intent in intents if self._intent_score(intent) >= settings.rag_search_intent_directed_min_intent_score]
        if settings.rag_search_intent_directed_enabled and directed_intents:
            limit = top_k * max(settings.rag_search_intent_directed_top_k_multiplier, 1)
            chunks = await self._retrieve_kb(query, limit, "intent-directed")
            results.append(ChannelSearchResult("intent-directed", 1, chunks))

        if self._should_use_vector_global(intents):
            limit = top_k * max(settings.rag_search_vector_global_top_k_multiplier, 1)
            chunks = await self._retrieve_kb(query, limit, "vector-global")
            results.append(ChannelSearchResult("vector-global", 10, chunks))

        if not results:
            chunks = await self._retrieve_kb(query, top_k, "vector-global")
            results.append(ChannelSearchResult("vector-global", 10, chunks))
        return results

    async def _post_process_channel_results(self, query: str, channel_results: list[ChannelSearchResult], top_k: int) -> list[RetrievedChunk]:
        deduped: dict[str, tuple[int, RetrievedChunk]] = {}
        for result in sorted(channel_results, key=lambda item: item.priority):
            for chunk in result.chunks:
                key = chunk.id or chunk.content.strip()
                if not key:
                    continue
                current = deduped.get(key)
                if current is None or result.priority < current[0] or (result.priority == current[0] and chunk.score > current[1].score):
                    deduped[key] = (result.priority, chunk)

        chunks = [item[1] for item in sorted(deduped.values(), key=lambda item: (item[0], -item[1].score))]
        rerank_order = await self.rerank_client.rerank(query, [chunk.content for chunk in chunks])
        ordered = [chunks[idx] for idx in rerank_order if 0 <= idx < len(chunks)]
        return (ordered or chunks)[:top_k]

    async def _retrieve_kb(self, query: str, top_k: int, channel_name: str) -> list[RetrievedChunk]:
        candidates: list[RetrievedChunk] = []
        if query:
            embedding = await self.embedding_client.embed(query)
            vector_rows = []
            if settings.vector_provider == "milvus":
                vector_rows = await milvus_client.search("rag_default_store", embedding, top_k=top_k)
            if not vector_rows:
                vector_rows = repository.search_vectors(embedding, query, top_k=top_k)
            for row in vector_rows:
                metadata = row.get("metadata") or {}
                content = row.get("content") or ""
                candidates.append(RetrievedChunk(str(row["id"]), metadata.get("kb_id"), metadata.get("doc_id"), content, float(row.get("score") or 0), channel_name))

        for chunk in repository.list_chunks(limit=300):
            content = chunk.get("content") or ""
            score = _score(query, content)
            if score > 0:
                candidates.append(RetrievedChunk(str(chunk["id"]), chunk.get("kbId"), chunk.get("docId"), content, score, channel_name))

        deduped: dict[str, RetrievedChunk] = {}
        for item in sorted(candidates, key=lambda c: c.score, reverse=True):
            key = item.content.strip()
            if key and key not in deduped:
                deduped[key] = item
        return list(deduped.values())[:top_k]

    def _should_use_vector_global(self, intents: list[dict]) -> bool:
        if not settings.rag_search_vector_global_enabled:
            return False
        if not intents:
            return True
        scores = [self._intent_score(intent) for intent in intents]
        max_score = max(scores) if scores else 0.0
        if max_score < settings.rag_search_vector_global_confidence_threshold:
            return True
        if len(intents) == 1 and max_score < settings.rag_search_vector_global_single_intent_supplement_threshold:
            return True
        return False

    def _intent_score(self, intent: dict) -> float:
        try:
            return float(intent.get("score", 1.0))
        except (TypeError, ValueError):
            return 1.0

    def _channel_trace_nodes(
        self,
        question: str,
        channel_results: list[ChannelSearchResult],
        final_chunk_count: int,
        has_mcp: bool,
    ) -> list[dict[str, Any]]:
        base = abs(hash(question))
        nodes: list[dict[str, Any]] = [
            {
                "nodeId": f"retrieve-{base}",
                "nodeName": "multi-channel-retrieval",
                "nodeType": "RETRIEVE_CHANNEL",
                "status": "completed",
                "chunkCount": final_chunk_count,
                "hasMcp": has_mcp,
            }
        ]
        for index, result in enumerate(channel_results, start=1):
            nodes.append(
                {
                    "nodeId": f"retrieve-{base}-channel-{index}",
                    "nodeName": result.channel_name,
                    "nodeType": "SEARCH_CHANNEL",
                    "status": "completed",
                    "priority": result.priority,
                    "chunkCount": len(result.chunks),
                }
            )
        return nodes

    def _format_kb_context(self, intents: list[dict], chunks: list[RetrievedChunk], top_k: int) -> str:
        body = "\n\n".join(f"[E{idx + 1}] {chunk.content}" for idx, chunk in enumerate(chunks[:top_k]))
        rules = self._joined_snippets(intents)
        snippet = self.loader.render_section("context-format.st", "snippet-rules", {"rules": rules}) if rules else ""
        return self.loader.render_section("context-format.st", "kb-section", {"snippet_section": snippet, "chunks_body": body}) or body

    async def _execute_mcp(self, question: str, intents: list[dict]) -> dict[str, Any]:
        results: list[str] = []
        tool_errors: list[dict[str, Any]] = []
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
                tool_errors.append({"toolId": tool_id, "errorType": type(exc).__name__, "recoverable": True})
                results.append(self.loader.render_section("context-format.st", "mcp-error", {"error_list": f"{tool_id}: tool temporarily unavailable"}))
        if not results:
            return {"context": "", "toolErrors": tool_errors}
        body = "\n\n".join(results)
        rules = self._joined_snippets(intents)
        snippet = self.loader.render_section("context-format.st", "mcp-intent-rules", {"rules": rules}) if rules else ""
        context = self.loader.render_section("context-format.st", "mcp-section", {"snippet_section": snippet, "body": body}) or body
        return {"context": context, "toolErrors": tool_errors}

    def _evidence_from_chunks(self, chunks: list[RetrievedChunk], produced_by_node: str) -> list[dict[str, Any]]:
        evidence: list[dict[str, Any]] = []
        for index, chunk in enumerate(chunks, start=1):
            source_id = chunk.doc_id or chunk.kb_id or chunk.id
            evidence.append(
                {
                    "id": f"E{index}",
                    "kind": "document",
                    "sourceId": source_id,
                    "title": source_id,
                    "locator": f"{chunk.kb_id or 'kb'}/{chunk.id}",
                    "snippet": chunk.content[:500],
                    "score": chunk.score,
                    "channel": chunk.channel,
                    "producedByNode": produced_by_node,
                    "sensitivityLevel": "internal",
                }
            )
        return evidence

    def _evidence_from_mcp_context(self, mcp_context: str, start_index: int, produced_by_node: str) -> list[dict[str, Any]]:
        if not mcp_context.strip():
            return []
        evidence: list[dict[str, Any]] = []
        for offset, block in enumerate([part.strip() for part in mcp_context.split("\n\n") if part.strip()], start=0):
            match = re.search(r"tool=([A-Za-z0-9_-]+)", block)
            tool_id = match.group(1) if match else "mcp-tool"
            evidence.append(
                {
                    "id": f"E{start_index + offset}",
                    "kind": "tool",
                    "sourceId": tool_id,
                    "title": tool_id,
                    "locator": f"mcp/{tool_id}",
                    "snippet": block[:500],
                    "score": 1.0,
                    "channel": "mcp",
                    "producedByNode": produced_by_node,
                    "sensitivityLevel": "internal",
                }
            )
        return evidence

    def _trace_nodes(self, contexts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nodes: list[dict[str, Any]] = []
        for context in contexts:
            nodes.extend(context.get("traceNodes") or [])
            if context.get("mcpContext"):
                nodes.append({"nodeId": f"mcp-{abs(hash(context.get('question', '')))}", "nodeName": "mcp-tool-call", "nodeType": "MCP", "status": "completed"})
        return nodes

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

    def retrieve(self, sub_intents: list[dict], top_k: int | None = None) -> dict:
        return asyncio.run(self.retrieve_async(sub_intents, top_k))
