from __future__ import annotations

from app.core.config import settings
from app.infra.llm import LLMClient
from app.rag.prompt import PromptTemplateLoader


class ConversationTitleGenerator:
    def __init__(self, max_chars: int | None = None) -> None:
        self.max_chars = max_chars if max_chars is not None else settings.rag_conversation_title_max_length
        self.loader = PromptTemplateLoader()
        self.llm = LLMClient()

    async def generate(self, question: str) -> str:
        fallback = (question or "新对话").strip()[: self.max_chars]
        if not settings.chat_provider:
            return fallback
        prompt = self.loader.render("conversation-title.st", {"question": question, "title_max_chars": str(self.max_chars)})
        try:
            title = await self.llm.chat([{"role": "user", "content": prompt}], temperature=0.2, top_p=0.5)
        except Exception:
            return fallback
        title = (title or "").strip().strip('"').strip("'")
        return title[: self.max_chars] or fallback
