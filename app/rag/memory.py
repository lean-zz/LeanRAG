from __future__ import annotations

from app.core.config import settings
from app.db.repository import repository
from app.infra.llm import LLMClient
from app.rag.prompt import PromptTemplateLoader


class ConversationMemoryService:
    def __init__(
        self,
        keep_turns: int | None = None,
        summary_start_turns: int | None = None,
        summary_max_chars: int | None = None,
        summary_enabled: bool | None = None,
    ) -> None:
        self.keep_turns = keep_turns if keep_turns is not None else settings.rag_memory_history_keep_turns
        self.summary_start_turns = summary_start_turns if summary_start_turns is not None else settings.rag_memory_summary_start_turns
        self.summary_max_chars = summary_max_chars if summary_max_chars is not None else settings.rag_memory_summary_max_chars
        self.summary_enabled = summary_enabled if summary_enabled is not None else settings.rag_memory_summary_enabled
        self.loader = PromptTemplateLoader()
        self.llm = LLMClient()

    def load(self, conversation_id: str, user_id: str) -> list[dict]:
        history = repository.list_messages(conversation_id, user_id)
        recent = history[-self._keep_messages() :]
        summary = repository.latest_conversation_summary(conversation_id, user_id)
        content = (summary or {}).get("content")
        if not content:
            return recent
        wrapped = self.loader.render_section("context-format.st", "summary-wrapper", {"content": str(content).strip()})
        return [{"role": "system", "content": wrapped}] + recent

    async def compress_if_needed(self, conversation_id: str, user_id: str) -> None:
        if not self.summary_enabled:
            return
        history = repository.list_messages(conversation_id, user_id)
        if self._turn_count(history) < self.summary_start_turns:
            return
        to_summarize = history[: -self._keep_messages()]
        if not to_summarize:
            return
        latest = repository.latest_conversation_summary(conversation_id, user_id) or {}
        last_summary_id = latest.get("last_message_id") or latest.get("lastMessageId")
        if last_summary_id and any(item.get("id") == last_summary_id for item in history[-self._keep_messages() :]):
            return

        summary = await self._summarize(to_summarize, str(latest.get("content") or ""))
        if not summary:
            return
        last_message_id = str(to_summarize[-1].get("id") or "")
        if last_message_id:
            repository.upsert_conversation_summary(conversation_id, user_id, summary, last_message_id)

    async def _summarize(self, messages: list[dict], existing_summary: str) -> str:
        if settings.chat_provider:
            system = self.loader.render("conversation-summary.st", {"summary_max_chars": str(self.summary_max_chars)})
            llm_messages: list[dict[str, str]] = [{"role": "system", "content": system}]
            if existing_summary:
                llm_messages.append({"role": "assistant", "content": f"历史摘要：\n{existing_summary}"})
            for item in messages:
                role = item.get("role")
                if role in {"user", "assistant"}:
                    llm_messages.append({"role": role, "content": item.get("content", "")})
            llm_messages.append({"role": "user", "content": f"合并以上对话与历史摘要，去重后输出更新摘要。要求：严格不超过 {self.summary_max_chars} 字符；仅一行。"})
            try:
                result = await self.llm.chat(llm_messages, temperature=0.3, top_p=0.9)
                if result:
                    return result.strip()[: self.summary_max_chars]
            except Exception:
                pass

        lines = []
        if existing_summary:
            lines.append(existing_summary.strip())
        for item in messages[-6:]:
            role = item.get("role", "user")
            content = " ".join(str(item.get("content") or "").split())
            if content:
                lines.append(f"{role}: {content[:120]}")
        return "；".join(lines)[-self.summary_max_chars :]

    def _keep_messages(self) -> int:
        return max(self.keep_turns, 1) * 2

    def _turn_count(self, messages: list[dict]) -> int:
        user_messages = sum(1 for item in messages if item.get("role") == "user")
        return max(user_messages, (len(messages) + 1) // 2)
