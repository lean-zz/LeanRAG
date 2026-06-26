from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEMO_ROOT = ROOT / "resources" / "demo" / "after-sales"


def _load(name: str) -> list[dict]:
    return json.loads((DEMO_ROOT / name).read_text(encoding="utf-8"))


def test_after_sales_intent_seed_has_required_root_intents() -> None:
    nodes = _load("intent-tree.json")
    by_code = {node["intentCode"]: node for node in nodes}

    assert {
        "after_sales.product_usage",
        "after_sales.troubleshooting",
        "after_sales.warranty",
        "after_sales.return_exchange",
        "after_sales.service_center",
        "after_sales.ticket_status",
        "after_sales.escalation",
    }.issubset(by_code)


def test_after_sales_troubleshooting_seed_has_required_children() -> None:
    nodes = _load("intent-tree.json")
    by_code = {node["intentCode"]: node for node in nodes}

    assert by_code["after_sales.troubleshooting.fault_code"]["parentCode"] == "after_sales.troubleshooting"
    assert by_code["after_sales.troubleshooting.cannot_start"]["parentCode"] == "after_sales.troubleshooting"
    assert "E37" in " ".join(by_code["after_sales.troubleshooting.fault_code"]["examples"])


def test_after_sales_tool_backed_intents_have_tool_ids() -> None:
    nodes = _load("intent-tree.json")
    tool_nodes = [node for node in nodes if node["kind"] == "mcp"]

    assert tool_nodes
    assert {node["mcpToolId"] for node in tool_nodes} >= {
        "get_ticket_status",
        "get_warranty_status",
        "find_service_center",
        "get_product_by_serial",
    }
    assert all(node["mcpToolId"] for node in tool_nodes)


def test_after_sales_query_term_mappings_are_enabled() -> None:
    mappings = _load("query-term-mappings.json")

    assert {item["targetTerm"] for item in mappings} >= {
        "cannot start",
        "fault",
        "display abnormality",
        "return and exchange policy",
        "repair service",
        "warranty status",
    }
    assert all(item["enabled"] is True for item in mappings)
