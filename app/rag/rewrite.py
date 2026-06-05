from __future__ import annotations

import json
import re

from app.core.config import settings
from app.db.repository import repository
from app.infra.llm import LLMClient
from app.rag.prompt import PromptTemplateLoader


class QueryRewriteService:
    def __init__(self) -> None:
        self.loader = PromptTemplateLoader()
        self.llm = LLMClient()

    def rewrite_with_split(self, question: str, history: list[dict] | None = None) -> dict:
        normalized = self._normalize_terms(question)
        return self._rule_based(normalized)

    async def rewrite_with_split_async(self, question: str, history: list[dict] | None = None) -> dict:
        normalized = self._normalize_terms(question)
        if not settings.chat_provider:
            return self._rule_based(normalized)

        messages: list[dict[str, str]] = []
        system = self.loader.load("user-question-rewrite.st")
        if system:
            messages.append({"role": "system", "content": system})
        for item in (history or [])[-4:]:
            role = item.get("role")
            if role in {"user", "assistant"}:
                messages.append({"role": role, "content": item.get("content", "")})
        messages.append({"role": "user", "content": normalized})

        try:
            raw = await self.llm.chat(messages, temperature=0.1, top_p=0.3)
            parsed = self._parse_llm_result(raw)
            if parsed:
                return parsed
        except Exception:
            pass
        return self._rule_based(normalized)

    def _normalize_terms(self, question: str) -> str:
        text = " ".join((question or "").split())
        if not text:
            return ""
        try:
            mappings = repository.list_mappings(current=1, size=1000).get("records", [])
        except Exception:
            mappings = []
        for item in sorted(mappings, key=lambda row: row.get("priority") or 0, reverse=True):
            if int(item.get("enabled", 1)) != 1:
                continue
            source = item.get("sourceTerm") or item.get("source_term")
            target = item.get("targetTerm") or item.get("target_term")
            if source and target and source in text:
                text = text.replace(str(source), str(target))
        return text

    def _rule_based(self, question: str) -> dict:
        if not question:
            return {"rewrittenQuestion": "", "subQuestions": []}
        parts = [p.strip() for p in re.split(r"[?？。；;\n]+", question) if p.strip()]
        return {"rewrittenQuestion": question, "subQuestions": parts or [question]}

    def _parse_llm_result(self, raw: str) -> dict | None:
        if not raw:
            return None
        cleaned = raw.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            return None
        rewrite = str(data.get("rewrite") or "").strip()
        subs = data.get("sub_questions") or data.get("subQuestions") or []
        sub_questions = [str(item).strip() for item in subs if str(item).strip()] if isinstance(subs, list) else []
        if not rewrite:
            return None
        return {"rewrittenQuestion": rewrite, "subQuestions": sub_questions or [rewrite]}
