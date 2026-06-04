from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)
BASE = "/api/ragent"


def login() -> str:
    response = client.post(f"{BASE}/auth/login", json={"username": "admin", "password": "admin"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == "0"
    assert payload["data"]["userId"] == "1"
    return payload["data"]["token"]


def test_success_wrapper_and_auth_flow() -> None:
    token = login()
    response = client.get(f"{BASE}/user/me", headers={"Authorization": token})
    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == "0"
    assert payload["data"]["username"] == "admin"
    assert payload["data"]["userId"] == "1"
    assert "requestId" in payload


def test_knowledge_base_crud() -> None:
    token = login()
    headers = {"Authorization": token}
    created = client.post(f"{BASE}/knowledge-base", json={"name": "KB"}, headers=headers).json()
    kb_id = created["data"]
    listed = client.get(f"{BASE}/knowledge-base", headers=headers).json()
    assert listed["code"] == "0"
    assert any(item["id"] == kb_id for item in listed["data"]["records"])
    update = client.put(f"{BASE}/knowledge-base/{kb_id}", json={"name": "KB2"}, headers=headers)
    assert update.json()["code"] == "0"


def test_document_upload_ingests_chunks() -> None:
    token = login()
    headers = {"Authorization": token}
    kb_id = client.post(f"{BASE}/knowledge-base", json={"name": "Upload KB"}, headers=headers).json()["data"]
    response = client.post(
        f"{BASE}/knowledge-base/{kb_id}/docs/upload",
        headers=headers,
        files={"file": ("doc.txt", b"Ragent retrieval upload test content", "text/plain")},
        data={"sourceType": "file"},
    )
    payload = response.json()
    assert payload["code"] == "0"
    assert payload["data"]["chunkCount"] >= 1
    chunks = client.get(f"{BASE}/knowledge-base/docs/{payload['data']['id']}/chunks", headers=headers).json()
    assert chunks["data"]["total"] >= 1


def test_sse_chat_stream() -> None:
    with client.stream("GET", f"{BASE}/rag/v3/chat", params={"question": "hello"}) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())
    assert "event: meta" in body
    assert "event: message" in body
    assert "event: done" in body
    assert '"delta"' in body


def test_ingestion_pipeline_and_task_routes() -> None:
    token = login()
    headers = {"Authorization": token}
    pipeline = client.post(f"{BASE}/ingestion/pipelines", json={"name": "default", "nodes": []}, headers=headers).json()
    assert pipeline["code"] == "0"
    task = client.post(f"{BASE}/ingestion/tasks", json={"pipelineId": pipeline["data"]["id"]}, headers=headers).json()
    assert task["code"] == "0"
    fetched = client.get(f"{BASE}/ingestion/tasks/{task['data']['taskId']}", headers=headers).json()
    assert fetched["data"]["id"] == task["data"]["taskId"]


def test_session_messages_after_stream() -> None:
    token = login()
    headers = {"Authorization": token}
    with client.stream("GET", f"{BASE}/rag/v3/chat", params={"question": "session test"}, headers=headers) as response:
        body = "".join(response.iter_text())
    assert "event: finish" in body
    sessions = client.get(f"{BASE}/conversations", headers=headers).json()
    assert sessions["code"] == "0"
    assert sessions["data"]
    conversation_id = sessions["data"][0]["conversationId"]
    messages = client.get(f"{BASE}/conversations/{conversation_id}/messages", headers=headers).json()
    assert len(messages["data"]) >= 2
    traces = client.get(f"{BASE}/rag/traces/runs", headers=headers).json()
    assert traces["code"] == "0"
    assert traces["data"]["total"] >= 1
