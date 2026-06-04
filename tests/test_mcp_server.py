from __future__ import annotations

from fastapi.testclient import TestClient

from mcp_server.main import app


client = TestClient(app)


def test_weather_tool_returns_text_content() -> None:
    response = client.post("/tools/weather_query/invoke", json={"city": "北京", "queryType": "current"})
    payload = response.json()
    assert response.status_code == 200
    assert payload["isError"] is False
    assert "北京" in payload["result"]


def test_ticket_and_sales_tools_are_parameterized() -> None:
    ticket = client.post("/tools/ticket_query/invoke", json={"region": "华东", "queryType": "summary"}).json()
    sales = client.post("/tools/sales_query/invoke", json={"period": "本月", "queryType": "ranking", "limit": 3}).json()
    assert ticket["isError"] is False
    assert "工单统计" in ticket["result"]
    assert sales["isError"] is False
    assert "¥" in sales["result"]

