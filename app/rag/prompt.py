from __future__ import annotations

import re
from pathlib import Path
from string import Template
from typing import Any


PROMPT_ROOT = Path(__file__).resolve().parents[2] / "resources" / "prompt"


class PromptTemplateLoader:
    def __init__(self) -> None:
        self._cache: dict[str, str] = {}
        self._section_cache: dict[str, dict[str, str]] = {}

    def _resolve(self, name: str) -> Path:
        clean = name.removeprefix("classpath:").removeprefix("prompt/")
        return PROMPT_ROOT / clean

    def load(self, name: str) -> str:
        if not name:
            return ""
        if name not in self._cache:
            path = self._resolve(name)
            self._cache[name] = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
        return self._cache[name]

    def render(self, name: str, values: dict[str, str]) -> str:
        raw = self.load(name)
        if not raw:
            return ""
        rendered = raw
        for key, value in values.items():
            rendered = rendered.replace("{" + key + "}", value)
        rendered = Template(rendered).safe_substitute(values)
        return cleanup_prompt(rendered)

    def sections(self, name: str) -> dict[str, str]:
        if name not in self._section_cache:
            raw = self.load(name)
            sections: dict[str, str] = {}
            current: str | None = None
            body: list[str] = []
            for line in raw.splitlines():
                match = re.match(r"---\s*section:\s*([A-Za-z0-9_-]+)\s*---", line.strip())
                if match:
                    if current is not None:
                        sections[current] = "\n".join(body).strip()
                    current = match.group(1)
                    body = []
                    continue
                if current is not None:
                    body.append(line)
            if current is not None:
                sections[current] = "\n".join(body).strip()
            self._section_cache[name] = sections
        return self._section_cache[name]

    def render_section(self, name: str, section: str, values: dict[str, str]) -> str:
        template = self.sections(name).get(section, "")
        if not template:
            return ""
        rendered = template
        for key, value in values.items():
            rendered = rendered.replace("{" + key + "}", value)
        return cleanup_prompt(rendered)


def cleanup_prompt(text: str) -> str:
    lines = [line.rstrip() for line in (text or "").splitlines()]
    cleaned: list[str] = []
    blank = False
    for line in lines:
        if not line.strip():
            if not blank:
                cleaned.append("")
            blank = True
            continue
        cleaned.append(line)
        blank = False
    return "\n".join(cleaned).strip()


class RAGPromptService:
    def __init__(self) -> None:
        self.loader = PromptTemplateLoader()

    def build_messages(self, question: str, history: list[dict], retrieval: dict, sub_questions: list[str]) -> list[dict]:
        return self.build_structured_messages(question, history, retrieval, sub_questions)

    def build_structured_messages(self, question: str, history: list[dict], retrieval: dict, sub_questions: list[str]) -> list[dict]:
        messages: list[dict[str, str]] = []
        system = self.build_system_prompt(retrieval)
        if system:
            messages.append({"role": "system", "content": system})
        messages.extend({"role": item.get("role", "user"), "content": item.get("content", "")} for item in history[-8:])
        user_content = self.build_user_content(question, retrieval, sub_questions)
        if user_content:
            messages.append({"role": "user", "content": user_content})
        return messages

    def build_system_prompt(self, retrieval: dict[str, Any]) -> str:
        if self._is_after_sales_mode(retrieval):
            return self.loader.load("after-sales-answer-chat-system.st")
        has_kb = bool(retrieval.get("hasKb") or retrieval.get("kbContext"))
        has_mcp = bool(retrieval.get("hasMcp") or retrieval.get("mcpContext"))
        if has_mcp and not has_kb:
            custom = self._single_prompt_template(retrieval, "mcpIntents")
            if custom:
                return cleanup_prompt(custom)
            return self.loader.load("answer-chat-mcp.st")
        if has_mcp and has_kb:
            return self.loader.load("answer-chat-mcp-kb-mixed.st")
        custom = self._single_prompt_template(retrieval, "kbIntents", require_chunks=True)
        if custom:
            return cleanup_prompt(custom)
        return self.loader.load("answer-chat-kb.st") or "You are Ragent AI. Answer with the provided context when it is relevant."

    def build_user_content(self, question: str, retrieval: dict[str, Any], sub_questions: list[str]) -> str:
        evidence = self._build_evidence_body(retrieval)
        question_body = self._build_question_body(question, sub_questions)
        return "\n\n".join(part for part in [evidence, question_body] if part).strip()

    def _build_evidence_body(self, retrieval: dict[str, Any]) -> str:
        structured = retrieval.get("evidence") or []
        if structured:
            lines = ["<evidence>", "Use only the following evidence ids when grounding the answer. If no evidence supports a claim, say insufficient information."]
            for item in structured:
                lines.append(
                    f"[{item.get('id')}] kind={item.get('kind')} source={item.get('title') or item.get('sourceId')} "
                    f"locator={item.get('locator')} score={item.get('score')} channel={item.get('channel')}\n{item.get('snippet') or ''}"
                )
            lines.append("</evidence>")
            return "\n".join(lines)
        sections: list[str] = []
        mcp_context = (retrieval.get("mcpContext") or "").strip()
        kb_context = (retrieval.get("kbContext") or "").strip()
        if mcp_context:
            sections.append(self.loader.render_section("context-format.st", "mcp-evidence", {"body": mcp_context}))
        if kb_context:
            sections.append(self.loader.render_section("context-format.st", "kb-evidence", {"body": kb_context}))
        return "\n\n".join(section for section in sections if section).strip()

    def _build_question_body(self, question: str, sub_questions: list[str]) -> str:
        if len(sub_questions) > 1:
            numbered = "\n".join(f"{idx + 1}. {item}" for idx, item in enumerate(sub_questions))
            return self.loader.render_section("context-format.st", "multi-questions", {"questions": numbered})
        return self.loader.render_section("context-format.st", "single-question", {"question": question})

    def _single_prompt_template(self, retrieval: dict[str, Any], key: str, require_chunks: bool = False) -> str:
        intents = retrieval.get(key) or []
        if len(intents) != 1:
            return ""
        node = intents[0].get("node") or intents[0]
        if require_chunks:
            node_key = str(node.get("intentCode") or node.get("intent_code") or node.get("id") or "")
            if node_key and not (retrieval.get("intentChunks") or {}).get(node_key):
                return ""
        return str(node.get("promptTemplate") or node.get("prompt_template") or "").strip()

    def _is_after_sales_mode(self, retrieval: dict[str, Any]) -> bool:
        mode = str(retrieval.get("promptMode") or retrieval.get("domain") or "").strip().lower()
        return mode in {"after-sales", "after_sales", "support", "customer-support"}
