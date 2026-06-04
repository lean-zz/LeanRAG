from __future__ import annotations

from pathlib import Path
from string import Template


PROMPT_ROOT = Path(__file__).resolve().parents[2] / "resources" / "prompt"


class PromptTemplateLoader:
    def load(self, name: str) -> str:
        path = PROMPT_ROOT / name
        if path.exists():
            return path.read_text(encoding="utf-8", errors="ignore")
        return ""

    def render(self, name: str, values: dict[str, str]) -> str:
        raw = self.load(name)
        if not raw:
            return ""
        return Template(raw).safe_substitute(values)


class RAGPromptService:
    def __init__(self) -> None:
        self.loader = PromptTemplateLoader()

    def build_messages(self, question: str, history: list[dict], retrieval: dict, sub_questions: list[str]) -> list[dict]:
        system = self.loader.load("answer-chat-kb.st") or "You are Ragent AI. Answer with the provided context when it is relevant."
        evidence = retrieval.get("kbContext") or "No retrieved knowledge context."
        user_content = f"Knowledge context:\n{evidence}\n\nQuestion:\n{question}"
        if len(sub_questions) > 1:
            user_content += "\n\nSub questions:\n" + "\n".join(f"{i + 1}. {q}" for i, q in enumerate(sub_questions))
        messages = [{"role": "system", "content": system}]
        messages.extend({"role": item.get("role", "user"), "content": item.get("content", "")} for item in history[-8:])
        messages.append({"role": "user", "content": user_content})
        return messages

