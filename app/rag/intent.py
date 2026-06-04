from __future__ import annotations


class IntentResolver:
    def resolve(self, sub_questions: list[str]) -> list[dict]:
        intents: list[dict] = []
        for question in sub_questions:
            kind = "kb"
            lowered = question.lower()
            if any(word in lowered for word in ["weather", "ticket", "sales", "天气", "机票", "销售"]):
                kind = "mcp"
            intents.append({"subQuestion": question, "kind": kind, "score": 1.0, "nodeScores": []})
        return intents

    def merge_group(self, intents: list[dict]) -> dict:
        return {
            "kbIntents": [item for item in intents if item["kind"] == "kb"],
            "mcpIntents": [item for item in intents if item["kind"] == "mcp"],
        }

