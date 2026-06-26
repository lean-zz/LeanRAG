from __future__ import annotations

from app.rag.prompt import RAGPromptService


def test_after_sales_prompt_contains_required_answer_contract() -> None:
    messages = RAGPromptService().build_messages(
        "What should a customer do before using X100?",
        [],
        {
            "domain": "after-sales",
            "hasKb": True,
            "kbContext": "X100 first-use checklist from FAQ.",
        },
        ["What should a customer do before using X100?"],
    )

    system = messages[0]["content"]

    assert "AfterSales Copilot" in system
    assert "Conclusion:" in system
    assert "Basis:" in system
    assert "Steps:" in system
    assert "Need To Confirm:" in system
    assert "Escalation:" in system


def test_after_sales_prompt_preserves_generic_prompt_path() -> None:
    messages = RAGPromptService().build_messages(
        "What is Ragent?",
        [],
        {"hasKb": True, "kbContext": "Ragent context"},
        ["What is Ragent?"],
    )

    assert "AfterSales Copilot" not in messages[0]["content"]
    assert "Ragent context" in messages[-1]["content"]


def test_after_sales_prompt_requires_grounding_and_escalation_rules() -> None:
    messages = RAGPromptService().build_messages(
        "The machine is smoking. Can I keep powering it on?",
        [],
        {"domain": "after-sales", "hasKb": True, "kbContext": "Safety cases require escalation."},
        ["The machine is smoking. Can I keep powering it on?"],
    )

    system = messages[0]["content"]

    assert "Document Basis" in system
    assert "Tool Basis" in system
    assert "insufficient information" in system.lower()
    assert "safety" in system.lower()
    assert "severe product failure" in system.lower()
