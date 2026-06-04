from __future__ import annotations

import re


class QueryRewriteService:
    def rewrite_with_split(self, question: str, history: list[dict] | None = None) -> dict:
        text = " ".join((question or "").split())
        if not text:
            return {"rewrittenQuestion": "", "subQuestions": []}
        parts = [p.strip() for p in re.split(r"[?？;；\n]+", text) if p.strip()]
        return {"rewrittenQuestion": text, "subQuestions": parts or [text]}

