from __future__ import annotations

from fastapi.testclient import TestClient

from mcp_server.main import app


client = TestClient(app)


def invoke(tool_name: str, payload: dict) -> dict:
    response = client.post(f"/tools/{tool_name}/invoke", json=payload)
    assert response.status_code == 200
    return response.json()


def test_get_ticket_status_returns_demo_ticket() -> None:
    payload = invoke("get_ticket_status", {"ticket_id": "T-10001"})

    assert payload["isError"] is False
    assert payload["tool"] == "get_ticket_status"
    assert "T-10001" in payload["result"]
    assert "awaiting_customer_confirmation" in payload["result"]
    assert "nextAction" in payload["result"]


def test_get_ticket_status_returns_not_found_for_unknown_ticket() -> None:
    payload = invoke("get_ticket_status", {"ticket_id": "T-99999"})

    assert payload["isError"] is True
    assert "T-99999" in payload["result"]
    assert "not found" in payload["result"].lower()


def test_get_warranty_status_returns_demo_serial() -> None:
    payload = invoke("get_warranty_status", {"serial_number": "SN-X100-2026-0001"})

    assert payload["isError"] is False
    assert "SN-X100-2026-0001" in payload["result"]
    assert "in_warranty" in payload["result"]
    assert "2028-05-20" in payload["result"]


def test_get_warranty_status_returns_not_found_for_unknown_serial() -> None:
    payload = invoke("get_warranty_status", {"serial_number": "SN-X100-0000-0000"})

    assert payload["isError"] is True
    assert "SN-X100-0000-0000" in payload["result"]
    assert "not found" in payload["result"].lower()


def test_find_service_center_returns_city_and_product_result() -> None:
    payload = invoke("find_service_center", {"city": "Shanghai", "product_model": "X100"})

    assert payload["isError"] is False
    assert "Shanghai" in payload["result"]
    assert "X100" in payload["result"]
    assert "appointmentRequired" in payload["result"]


def test_find_service_center_returns_not_found_for_unsupported_city() -> None:
    payload = invoke("find_service_center", {"city": "Hangzhou", "product_model": "X100"})

    assert payload["isError"] is True
    assert "Hangzhou" in payload["result"]
    assert "mail-in repair" in payload["result"]


def test_get_product_by_serial_returns_demo_product() -> None:
    payload = invoke("get_product_by_serial", {"serial_number": "SN-X100-2024-0099"})

    assert payload["isError"] is False
    assert "SN-X100-2024-0099" in payload["result"]
    assert "X100" in payload["result"]
    assert "2024-03-12" in payload["result"]


def test_after_sales_tools_are_listed() -> None:
    payload = client.get("/tools").json()
    names = {item["name"] for item in payload["tools"]}

    assert {
        "get_ticket_status",
        "get_warranty_status",
        "find_service_center",
        "get_product_by_serial",
    }.issubset(names)
