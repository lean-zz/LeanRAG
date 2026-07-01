from __future__ import annotations

import json
import socket
import threading
import time

import uvicorn
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app as rag_app
from app.services.store import store
from mcp_server.main import app as mcp_app


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _start_mcp_server() -> tuple[uvicorn.Server, str]:
    port = _free_port()
    config = uvicorn.Config(mcp_app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 5
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    assert server.started
    return server, f"http://127.0.0.1:{port}"


def _response_text(body: str) -> str:
    chunks: list[str] = []
    for line in body.splitlines():
        if not line.startswith("data: "):
            continue
        raw = line.removeprefix("data: ")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("type") == "response":
            chunks.append(str(payload.get("delta") or ""))
    return "".join(chunks)


def test_order_query_uses_seed_order_data() -> None:
    client = TestClient(mcp_app)

    logistics = client.post(
        "/tools/order_query/invoke",
        json={"orderId": "EC202607010001", "queryType": "logistics"},
    ).json()
    refund = client.post(
        "/tools/order_query/invoke",
        json={"orderId": "EC202607010002", "queryType": "refund"},
    ).json()

    assert logistics["isError"] is False
    assert "EC202607010001" in logistics["result"]
    assert "SF744000123CN" in logistics["result"]
    assert "预计 2026-07-03 送达" in logistics["result"]
    assert refund["isError"] is False
    assert "售后审核中" in refund["result"]
    assert "REF202607010002" in refund["result"]


def test_chat_order_query_reaches_mcp_and_streams_tool_data() -> None:
    server, url = _start_mcp_server()
    old_url = settings.mcp_server_url
    object.__setattr__(settings, "mcp_server_url", url)
    store.conversations.clear()
    store.messages.clear()
    store.traces.clear()
    try:
        client = TestClient(rag_app)
        with client.stream(
            "GET",
            "/api/ragent/rag/v3/chat",
            params={"question": "order EC202607010001 logistics status"},
        ) as response:
            assert response.status_code == 200
            body = "".join(response.iter_text())
    finally:
        object.__setattr__(settings, "mcp_server_url", old_url)
        server.should_exit = True

    assert "event: meta" in body
    assert "event: message" in body
    assert "event: finish" in body
    response_text = _response_text(body)
    assert "tool=order_query" in response_text
    assert "EC202607010001" in response_text
    assert "SF744000123CN" in response_text
    assert "预计 2026-07-03 送达" in response_text
    assert any(node.get("nodeType") == "MCP" for trace in store.traces.values() for node in trace.get("nodes", []))
