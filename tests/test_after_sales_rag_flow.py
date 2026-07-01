from __future__ import annotations

from pathlib import Path

from app.rag.prompt import RAGPromptService
from app.rag.pipeline import _record_trace
from app.services.store import store


ROOT = Path(__file__).resolve().parents[1]
DEMO_ROOT = ROOT / "resources" / "demo" / "after-sales"


def _doc(name: str) -> str:
    return (DEMO_ROOT / name).read_text(encoding="utf-8")


def test_after_sales_faq_flow_builds_support_prompt_and_trace() -> None:
    messages = RAGPromptService().build_messages(
        "What should a customer do before using X100 for the first time?",
        [],
        {
            "domain": "after-sales",
            "hasKb": True,
            "kbContext": _doc("faq.md"),
            "chunks": [{"content": "Before first use, charge X100 for at least 30 minutes."}],
        },
        ["What should a customer do before using X100 for the first time?"],
    )

    assert "Conclusion:" in messages[0]["content"]
    assert "X100" in messages[-1]["content"]

    store.traces.clear()
    store.trace_nodes.clear()
    _record_trace(
        "trace-after-sales-faq",
        "What should a customer do before using X100 for the first time?",
        "conversation-after-sales",
        "support-agent",
        {"subQuestions": ["What should a customer do before using X100 for the first time?"]},
        {"hasKb": True, "chunks": [{"content": "X100 first use"}]},
    )

    nodes = store.trace_nodes["trace-after-sales-faq"]
    assert {node["nodeType"] for node in nodes} >= {"REWRITE", "INTENT", "RETRIEVE", "PROMPT", "GENERATE"}


def test_after_sales_warranty_flow_uses_policy_context() -> None:
    messages = RAGPromptService().build_messages(
        "Is accidental water damage covered by the X100 warranty?",
        [],
        {
            "domain": "after-sales",
            "hasKb": True,
            "kbContext": _doc("warranty-policy.md"),
        },
        ["Is accidental water damage covered by the X100 warranty?"],
    )

    assert "water damage" in messages[-1]["content"]
    assert "Exclusions" in messages[-1]["content"]


def test_after_sales_troubleshooting_flow_uses_sop_context() -> None:
    messages = RAGPromptService().build_messages(
        "X100 displays E37. What should the customer check first?",
        [],
        {
            "domain": "after-sales",
            "hasKb": True,
            "kbContext": _doc("troubleshooting-x100.md"),
        },
        ["X100 displays E37. What should the customer check first?"],
    )

    assert "Likely Causes:" in messages[0]["content"]
    assert "E37 Display Abnormality" in messages[-1]["content"]


def test_after_sales_ticket_status_tool_only_flow_uses_tool_context() -> None:
    messages = RAGPromptService().build_messages(
        "What is the status of ticket T-10001?",
        [],
        {
            "domain": "after-sales",
            "hasMcp": True,
            "mcpContext": '{"ticketId":"T-10001","status":"awaiting_customer_confirmation","nextAction":"Confirm E37 result."}',
        },
        ["What is the status of ticket T-10001?"],
    )

    assert "AfterSales Copilot" in messages[0]["content"]
    assert "tool result" in messages[0]["content"].lower()
    assert "T-10001" in messages[-1]["content"]
    assert "awaiting_customer_confirmation" in messages[-1]["content"]


def test_after_sales_warranty_status_tool_only_flow_uses_tool_context() -> None:
    messages = RAGPromptService().build_messages(
        "Is serial number SN-X100-2026-0001 still under warranty?",
        [],
        {
            "domain": "after-sales",
            "hasMcp": True,
            "mcpContext": '{"serialNumber":"SN-X100-2026-0001","status":"in_warranty","endDate":"2028-05-20"}',
        },
        ["Is serial number SN-X100-2026-0001 still under warranty?"],
    )

    assert "SN-X100-2026-0001" in messages[-1]["content"]
    assert "in_warranty" in messages[-1]["content"]
    assert "2028-05-20" in messages[-1]["content"]


def test_after_sales_mixed_warranty_repair_flow_uses_tool_and_policy_context() -> None:
    messages = RAGPromptService().build_messages(
        "SN-X100-2024-0099 is already out of warranty. Can it still be repaired?",
        [],
        {
            "domain": "after-sales",
            "hasMcp": True,
            "hasKb": True,
            "mcpContext": '{"serialNumber":"SN-X100-2024-0099","status":"expired","endDate":"2026-03-12"}',
            "kbContext": _doc("warranty-policy.md"),
        },
        ["SN-X100-2024-0099 is already out of warranty. Can it still be repaired?"],
    )

    content = messages[-1]["content"]

    assert "SN-X100-2024-0099" in content
    assert "expired" in content
    assert "Out-Of-Warranty Repair" in content


def test_after_sales_trace_can_include_tool_call_node() -> None:
    store.traces.clear()
    store.trace_nodes.clear()

    _record_trace(
        "trace-after-sales-tool",
        "What is the status of ticket T-10001?",
        "conversation-after-sales",
        "support-agent",
        {"subQuestions": ["What is the status of ticket T-10001?"]},
        {
            "hasMcp": True,
            "chunks": [],
            "traceNodes": [
                {
                    "nodeId": "tool-get-ticket-status",
                    "nodeName": "get_ticket_status",
                    "nodeType": "TOOL_CALL",
                    "status": "completed",
                    "toolId": "get_ticket_status",
                    "sanitizedParameters": {"ticket_id": "T-10001"},
                    "responseStatus": "success",
                    "durationMs": 12,
                }
            ],
        },
    )

    nodes = store.trace_nodes["trace-after-sales-tool"]

    assert any(node["nodeType"] == "TOOL_CALL" and node["nodeName"] == "get_ticket_status" for node in nodes)
    tool_node = next(node for node in nodes if node["nodeType"] == "TOOL_CALL")
    assert tool_node["sanitizedParameters"] == {"ticket_id": "T-10001"}
    assert tool_node["responseStatus"] == "success"
    assert tool_node["traceId"] == "trace-after-sales-tool"
