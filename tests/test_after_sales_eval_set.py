from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVAL_SET = ROOT / "resources" / "demo" / "after-sales" / "eval-set.json"
REQUIRED_SECTIONS = {"Conclusion", "Basis", "Steps", "Need To Confirm", "Escalation"}
VALID_ROUTES = {"knowledge-only", "tool-only", "mixed", "clarification", "escalation"}


def _cases() -> list[dict]:
    return json.loads(EVAL_SET.read_text(encoding="utf-8"))


def _deterministic_fallback_route(case: dict) -> str:
    """Small executable oracle for the seed set's routing contract."""
    basis = case["requiredBasis"]
    has_document_basis = any(item.startswith("doc:") for item in basis)
    has_tool_basis = any(item.startswith("tool:") for item in basis)

    if "Escalation" in case["requiredSections"] and case["category"] == "refusal-escalation":
        return "escalation"
    if has_document_basis and has_tool_basis:
        return "mixed"
    if has_tool_basis:
        return "tool-only"
    if has_document_basis:
        return "knowledge-only"
    return "clarification"


def test_after_sales_eval_set_has_required_case_counts() -> None:
    cases = _cases()
    by_category: dict[str, int] = {}
    for case in cases:
        by_category[case["category"]] = by_category.get(case["category"], 0) + 1

    assert len(cases) >= 30
    assert by_category["faq"] >= 8
    assert by_category["troubleshooting"] >= 6
    assert by_category["policy"] >= 5
    assert by_category["tool"] >= 5
    assert by_category["mixed"] >= 3
    assert by_category["refusal-escalation"] >= 3


def test_after_sales_eval_set_schema_is_valid() -> None:
    for case in _cases():
        assert case["id"]
        assert case["category"]
        assert case["question"]
        assert case["expectedRoute"] in VALID_ROUTES
        assert set(case["requiredSections"]).issubset(REQUIRED_SECTIONS)
        assert isinstance(case["requiredBasis"], list)
        assert isinstance(case["forbiddenClaims"], list)


def test_after_sales_eval_set_tool_and_mixed_cases_require_basis() -> None:
    for case in _cases():
        if case["expectedRoute"] in {"tool-only", "mixed"}:
            assert any("tool:" in basis for basis in case["requiredBasis"])
        if case["expectedRoute"] in {"knowledge-only", "mixed"}:
            assert any("doc:" in basis for basis in case["requiredBasis"])


def test_after_sales_eval_set_can_run_against_deterministic_fallback_route() -> None:
    for case in _cases():
        assert _deterministic_fallback_route(case) == case["expectedRoute"]
