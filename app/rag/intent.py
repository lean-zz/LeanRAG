from __future__ import annotations

import json
import re
from typing import Any

from app.core.config import settings
from app.db.repository import repository
from app.infra.llm import LLMClient
from app.rag.prompt import PromptTemplateLoader

INTENT_MIN_SCORE = 0.35
MAX_INTENT_COUNT = 3


class IntentResolver:
    def __init__(self) -> None:
        self.loader = PromptTemplateLoader()
        self.llm = LLMClient()

    def resolve(self, sub_questions: list[str] | dict) -> list[dict]:
        questions = self._questions(sub_questions)
        return [self._resolve_one_rule(question) for question in questions]

    async def resolve_async(self, rewrite_result: dict) -> list[dict]:
        questions = self._questions(rewrite_result)
        results: list[dict] = []
        for question in questions:
            if settings.chat_provider:
                result = await self._resolve_one_llm(question)
                if result:
                    results.append(result)
                    continue
            results.append(self._resolve_one_rule(question))
        return self._cap_total_intents(results)

    def merge_group(self, intents: list[dict]) -> dict:
        kb_intents: list[dict] = []
        mcp_intents: list[dict] = []
        system_intents: list[dict] = []
        for item in intents:
            for score in item.get("nodeScores") or []:
                kind = self._kind(score.get("node") or score)
                if kind == "mcp":
                    mcp_intents.append(score)
                elif kind == "system":
                    system_intents.append(score)
                else:
                    kb_intents.append(score)
            if not item.get("nodeScores"):
                kind = item.get("kind")
                if kind == "mcp":
                    mcp_intents.append(item)
                elif kind == "system":
                    system_intents.append(item)
                else:
                    kb_intents.append(item)
        return {"kbIntents": kb_intents, "mcpIntents": mcp_intents, "systemIntents": system_intents}

    def is_system_only(self, intent: dict) -> bool:
        scores = intent.get("nodeScores") or []
        if not scores:
            return intent.get("kind") == "system"
        return len(scores) == 1 and self._kind(scores[0].get("node") or scores[0]) == "system"

    def _questions(self, value: list[str] | dict) -> list[str]:
        if isinstance(value, dict):
            questions = value.get("subQuestions") or [value.get("rewrittenQuestion", "")]
        else:
            questions = value
        return [str(item).strip() for item in questions if str(item).strip()]

    async def _resolve_one_llm(self, question: str) -> dict | None:
        nodes = self._intent_nodes()
        if not nodes:
            return None
        intent_list = self._format_intent_list(nodes)
        prompt = self.loader.render("intent-classifier.st", {"intent_list": intent_list})
        try:
            raw = await self.llm.chat(
                [{"role": "system", "content": prompt}, {"role": "user", "content": question}],
                temperature=0.1,
                top_p=0.3,
            )
            scores = self._parse_llm_scores(raw, nodes)
            if scores:
                return self._intent_result(question, scores)
        except Exception:
            return None
        return None

    def _resolve_one_rule(self, question: str) -> dict:
        nodes = self._intent_nodes()
        scores = self._rule_scores(question, nodes)
        if scores:
            return self._intent_result(question, scores)

        kind = "kb"
        lowered = question.lower()
        if any(word in lowered for word in ["weather", "ticket", "sales", "天气", "机票", "销售"]):
            kind = "mcp"
        return {"subQuestion": question, "kind": kind, "score": 1.0, "nodeScores": []}

    def _intent_result(self, question: str, scores: list[dict]) -> dict:
        first_kind = self._kind(scores[0].get("node") or scores[0]) if scores else "kb"
        return {"subQuestion": question, "kind": first_kind, "score": scores[0].get("score", 1.0) if scores else 1.0, "nodeScores": scores}

    def _intent_nodes(self) -> list[dict[str, Any]]:
        try:
            nodes = repository.list_intent_nodes()
        except Exception:
            return []
        enabled = [dict(node) for node in nodes if int(node.get("enabled", 1)) == 1]
        by_code = {str(node.get("intentCode") or node.get("intent_code") or node.get("id")): node for node in enabled}
        children: dict[str, list[dict]] = {key: [] for key in by_code}
        roots: list[dict] = []
        for node in enabled:
            code = str(node.get("intentCode") or node.get("intent_code") or node.get("id"))
            parent = node.get("parentCode") or node.get("parent_code")
            if parent and str(parent) in by_code:
                children[str(parent)].append(node)
            else:
                roots.append(node)
            node["_code"] = code
        for root in roots:
            self._fill_full_path(root, children, "")
        leaves = [node for node in enabled if not children.get(str(node.get("_code")))]
        return leaves or enabled

    def _fill_full_path(self, node: dict, children: dict[str, list[dict]], parent_path: str) -> None:
        name = str(node.get("name") or node.get("intentCode") or node.get("id") or "")
        full_path = f"{parent_path} > {name}" if parent_path and name else name or parent_path
        node["fullPath"] = full_path
        for child in children.get(str(node.get("_code")), []):
            self._fill_full_path(child, children, full_path)

    def _rule_scores(self, question: str, nodes: list[dict]) -> list[dict]:
        query = question.lower()
        scored: list[dict] = []
        for node in nodes:
            phrases = self._keyword_phrases(node)
            hits = sum(1 for phrase in phrases if phrase and phrase in query)
            domain_hits = self._domain_rule_hits(question, query, node)
            hits += domain_hits
            if node.get("name") and str(node["name"]).lower() in query:
                hits += 2
            if hits:
                code = str(node.get("intentCode") or node.get("intent_code") or "")
                if code.startswith("order.query") and domain_hits == 0:
                    continue
                scored.append({"node": node, "score": min(1.0, hits / 4), "reason": "rule keyword match"})
        return sorted(scored, key=lambda item: item["score"], reverse=True)[:MAX_INTENT_COUNT]

    def _domain_rule_hits(self, question: str, query: str, node: dict) -> int:
        code = str(node.get("intentCode") or node.get("intent_code") or "")
        if not code.startswith("order.query"):
            return 0
        has_order_context = bool(re.search(r"(?:订单号?|order)\s*[:：]?\s*[A-Za-z0-9-]{6,32}", question, re.I)) or any(
            word in question for word in ["我的", "这个订单", "该订单", "这笔订单"]
        )
        asks_progress = any(word in question for word in ["进度", "状态", "到哪", "到哪里", "单号", "签收", "审核"]) or any(
            word in query for word in ["status", "progress", "tracking"]
        )
        if code == "order.query.logistics" and (
            has_order_context
            and (any(word in question for word in ["物流", "快递", "送到", "签收", "运单"]) or any(word in query for word in ["logistics", "tracking", "delivery"]))
        ):
            return 4
        if code == "order.query.refund_status" and (
            (has_order_context or asks_progress)
            and (any(word in question for word in ["退款", "退货", "售后", "平台介入"]) or any(word in query for word in ["refund", "return"]))
        ):
            return 4
        if code == "order.query.address_change" and (
            has_order_context and (any(word in question for word in ["地址", "手机号", "电话", "收货信息"]) or "address" in query)
        ):
            return 4
        if code == "order.query.fulfillment" and (
            has_order_context and (any(word in question for word in ["订单", "发货", "付款", "支付", "取消"]) or any(word in query for word in ["order", "payment", "fulfillment"])
            )
        ):
            return 3
        return 0

    def _keyword_phrases(self, node: dict) -> set[str]:
        fields = ["intentCode", "name", "description", "examples", "collectionName", "mcpToolId"]
        phrases: set[str] = set()
        for key in fields:
            value = str(node.get(key) or "").lower()
            if not value:
                continue
            if key in {"intentCode", "collectionName", "mcpToolId"}:
                phrases.update(part for part in re.split(r"[\W_.-]+", value) if len(part) > 1)
                continue
            phrases.update(part.strip() for part in re.split(r"[;；,，、\n\r\t|/]+", value) if len(part.strip()) > 1)
            phrases.update(part for part in re.split(r"\W+", value) if len(part) > 1 and len(part) <= 12)
        return phrases

    def _format_intent_list(self, nodes: list[dict]) -> str:
        parts: list[str] = []
        for node in nodes:
            node_id = node.get("intentCode") or node.get("id")
            parts.append(f"- id={node_id}")
            parts.append(f"  path={node.get('fullPath') or node.get('name') or ''}")
            parts.append(f"  description={node.get('description') or ''}")
            parts.append(f"  type={self._kind(node).upper()}")
            if node.get("mcpToolId"):
                parts.append(f"  toolId={node['mcpToolId']}")
            if node.get("examples"):
                parts.append(f"  examples={node['examples']}")
            parts.append("")
        return "\n".join(parts)

    def _parse_llm_scores(self, raw: str, nodes: list[dict]) -> list[dict]:
        cleaned = re.sub(r"^```(?:json)?\s*", "", (raw or "").strip())
        cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            return []
        if isinstance(data, dict):
            data = data.get("results", [])
        by_code = {str(node.get("intentCode") or node.get("id")): node for node in nodes}
        scores: list[dict] = []
        for item in data if isinstance(data, list) else []:
            node = by_code.get(str(item.get("id")))
            score = float(item.get("score") or 0)
            if node and score >= INTENT_MIN_SCORE:
                scores.append({"node": node, "score": score, "reason": item.get("reason", "")})
        return sorted(scores, key=lambda item: item["score"], reverse=True)[:MAX_INTENT_COUNT]

    def _cap_total_intents(self, intents: list[dict]) -> list[dict]:
        total = sum(len(item.get("nodeScores") or []) for item in intents)
        if total <= MAX_INTENT_COUNT:
            return intents
        remaining = MAX_INTENT_COUNT
        capped: list[dict] = []
        for item in intents:
            scores = item.get("nodeScores") or []
            keep = scores[: max(1, min(len(scores), remaining))]
            remaining -= len(keep)
            capped.append({**item, "nodeScores": keep})
            if remaining <= 0:
                capped.extend({**rest, "nodeScores": []} for rest in intents[len(capped) :])
                break
        return capped

    def _kind(self, node: dict) -> str:
        kind = str(node.get("kind") or "").lower()
        if kind in {"2", "mcp"} or node.get("mcpToolId") or node.get("mcp_tool_id"):
            return "mcp"
        if kind in {"1", "system"}:
            return "system"
        return "kb"
