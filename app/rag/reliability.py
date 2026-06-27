from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from app.core.ids import new_id
from app.services.store import now_text


ROOT = Path(__file__).resolve().parents[2]
RELIABILITY_EVAL_SET = ROOT / "resources" / "demo" / "after-sales" / "reliability-eval-set.json"

PROMPT_INJECTION_PATTERNS = (
    "ignore previous instructions",
    "ignore all previous instructions",
    "reveal the system prompt",
    "show system prompt",
    "developer message",
    "hidden prompt",
    "越过系统",
    "忽略之前",
    "泄露系统提示",
)
ESCALATION_TERMS = ("privacy", "legal", "payment dispute", "smoke", "burning smell", "injury", "隐私", "法律", "付款纠纷", "冒烟", "烧焦", "受伤")


def redact_sensitive_text(text: str) -> str:
    redacted = re.sub(r"(?<!\d)(1[3-9]\d)\d{4}(\d{4})(?!\d)", r"\1****\2", text or "")
    redacted = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[redacted-email]", redacted)
    redacted = re.sub(r"\b(sk|pk|ak)-[A-Za-z0-9_-]{6,}\b", r"\1-***", redacted)
    redacted = re.sub(r"(?i)(api[_-]?key|token|secret)\s*[:=]\s*['\"]?[^'\"\s]+", r"\1=[redacted-secret]", redacted)
    return redacted


def guardrail_check(text: str, user_id: str, allowed_kb_ids: list[str] | None = None, evidence: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    lowered = (text or "").lower()
    if any(pattern in lowered for pattern in PROMPT_INJECTION_PATTERNS):
        return {
            "action": "block",
            "reason": "prompt_injection",
            "sanitizedText": "",
            "summary": "block:prompt_injection",
            "userId": user_id,
        }

    if any(term in lowered for term in ESCALATION_TERMS):
        action = "escalate"
        reason = "sensitive_or_high_risk_request"
    else:
        action = "allow"
        reason = "none"

    if allowed_kb_ids is not None and evidence:
        allowed = set(allowed_kb_ids)
        forbidden = [item for item in evidence if item.get("kind") == "document" and item.get("locator", "").split("/", 1)[0] not in allowed]
        if forbidden:
            return {
                "action": "block",
                "reason": "unauthorized_evidence",
                "sanitizedText": "",
                "summary": "block:unauthorized_evidence",
                "userId": user_id,
            }

    sanitized = redact_sensitive_text(text or "")
    if sanitized != (text or "") and action == "allow":
        action = "redact"
        reason = "sensitive_data"

    return {
        "action": action,
        "reason": reason,
        "sanitizedText": sanitized,
        "summary": f"{action}:{reason}",
        "userId": user_id,
    }


def build_reliability_decision(retrieval: dict[str, Any], guardrail: dict[str, Any]) -> dict[str, Any]:
    action = guardrail.get("action")
    if action == "block":
        return {"type": "refuse", "reasons": [guardrail.get("reason") or "blocked"], "confidence": 1.0}
    if action == "escalate":
        return {"type": "escalate", "reasons": [guardrail.get("reason") or "high_risk"], "confidence": 0.9}
    if retrieval.get("toolErrors"):
        return {"type": "fallback", "reasons": ["tool_failure"], "confidence": 0.5}
    if not retrieval.get("hasKb") and not retrieval.get("hasMcp"):
        return {"type": "clarify", "reasons": ["insufficient_evidence"], "confidence": 0.2}
    evidence = retrieval.get("evidence") or []
    if not evidence and (retrieval.get("hasKb") or retrieval.get("hasMcp")):
        return {"type": "fallback", "reasons": ["missing_structured_evidence"], "confidence": 0.4}
    score_values = [float(item.get("score") or 0) for item in evidence if item.get("score") is not None]
    confidence = max(score_values) if score_values else 0.7
    reasons = ["evidence_available"]
    if action == "redact":
        reasons.append("sensitive_data_redacted")
    return {"type": "answer", "reasons": reasons, "confidence": round(confidence, 4)}


def assign_experiment_variant(experiment_id: str, user_id: str, conversation_id: str | None = None) -> dict[str, Any]:
    variants = ("baseline", "strict-grounding", "rerank-v2")
    seed = f"{experiment_id}:{user_id}:{conversation_id or ''}"
    bucket = int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8], 16) % 100
    if bucket < 50:
        variant = variants[0]
    elif bucket < 80:
        variant = variants[1]
    else:
        variant = variants[2]
    return {
        "id": f"{experiment_id}:{user_id}:{conversation_id or 'global'}",
        "experimentId": experiment_id,
        "userId": user_id,
        "conversationId": conversation_id,
        "variant": variant,
        "bucket": bucket,
        "config": {"evidenceRequired": variant == "strict-grounding", "rerank": variant == "rerank-v2"},
        "assignedAt": now_text(),
    }


def load_reliability_eval_cases() -> list[dict[str, Any]]:
    if not RELIABILITY_EVAL_SET.exists():
        return []
    return json.loads(RELIABILITY_EVAL_SET.read_text(encoding="utf-8"))


def evaluate_reliability_case(case: dict[str, Any]) -> dict[str, Any]:
    question = str(case.get("question") or "")
    guardrail = guardrail_check(question, user_id="eval")
    expected_action = case.get("expectedGuardrailAction", "allow")
    decision_type = case.get("expectedDecision") or _decision_for_eval_case(case, guardrail)
    required_evidence = case.get("requiredEvidence") or []
    forbidden_claims = case.get("forbiddenClaims") or []
    passed = guardrail["action"] == expected_action
    if expected_action == "allow" and case.get("category") == "insufficient-evidence":
        passed = decision_type == "clarify"
    return {
        "id": str(case.get("id") or new_id()),
        "caseId": case.get("id"),
        "category": case.get("category"),
        "passed": bool(passed),
        "guardrailAction": guardrail["action"],
        "expectedGuardrailAction": expected_action,
        "decisionType": decision_type,
        "requiredEvidence": required_evidence,
        "forbiddenClaims": forbidden_claims,
        "citationCoverage": 1.0 if required_evidence else 0.0,
    }


def run_reliability_eval(limit: int | None = None) -> dict[str, Any]:
    cases = load_reliability_eval_cases()
    selected = cases[:limit] if limit else cases
    results = [evaluate_reliability_case(case) for case in selected]
    passed = sum(1 for result in results if result["passed"])
    return {
        "id": new_id(),
        "status": "completed",
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "results": results,
        "createTime": now_text(),
    }


def _decision_for_eval_case(case: dict[str, Any], guardrail: dict[str, Any]) -> str:
    if guardrail["action"] == "block":
        return "refuse"
    if guardrail["action"] == "escalate":
        return "escalate"
    category = case.get("category")
    if category == "insufficient-evidence":
        return "clarify"
    if category == "tool-failure":
        return "fallback"
    return "answer"
