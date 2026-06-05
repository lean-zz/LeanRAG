from __future__ import annotations

from fastapi.testclient import TestClient

from app.infra.messaging import rocketmq
from app.main import app


client = TestClient(app)
BASE = "/api/ragent"


def login() -> dict[str, str]:
    response = client.post(f"{BASE}/auth/login", json={"username": "admin", "password": "admin"})
    assert response.status_code == 200
    token = response.json()["data"]["token"]
    return {"Authorization": token}


def test_user_management_crud_and_password_change() -> None:
    headers = login()
    user_id = client.post(f"{BASE}/users", json={"username": "ops", "password": "pw", "role": "user"}, headers=headers).json()["data"]
    listed = client.get(f"{BASE}/users", headers=headers).json()
    assert any(item["id"] == user_id and "password" not in item for item in listed["data"]["records"])

    assert client.put(f"{BASE}/users/{user_id}", json={"role": "admin"}, headers=headers).json()["code"] == "0"
    assert client.put(f"{BASE}/user/password", json={"newPassword": "admin"}, headers=headers).json()["code"] == "0"
    assert client.delete(f"{BASE}/users/{user_id}", headers=headers).json()["code"] == "0"


def test_sample_questions_and_mappings_crud() -> None:
    headers = login()
    sample_id = client.post(f"{BASE}/sample-questions", json={"title": "Intro", "question": "What is Ragent?"}, headers=headers).json()["data"]
    assert client.get(f"{BASE}/sample-questions/{sample_id}", headers=headers).json()["data"]["id"] == sample_id
    assert client.put(f"{BASE}/sample-questions/{sample_id}", json={"description": "updated"}, headers=headers).json()["code"] == "0"
    assert client.delete(f"{BASE}/sample-questions/{sample_id}", headers=headers).json()["code"] == "0"

    mapping_id = client.post(f"{BASE}/mappings", json={"domain": "default", "sourceTerm": "AI", "targetTerm": "artificial intelligence"}, headers=headers).json()["data"]
    assert client.get(f"{BASE}/mappings/{mapping_id}", headers=headers).json()["data"]["id"] == mapping_id
    assert client.put(f"{BASE}/mappings/{mapping_id}", json={"priority": 10}, headers=headers).json()["code"] == "0"
    assert client.delete(f"{BASE}/mappings/{mapping_id}", headers=headers).json()["code"] == "0"


def test_intent_tree_crud_and_batch_actions() -> None:
    headers = login()
    node_id = client.post(f"{BASE}/intent-tree", json={"name": "Knowledge", "intentCode": "kb", "kind": "kb"}, headers=headers).json()["data"]
    trees = client.get(f"{BASE}/intent-tree/trees", headers=headers).json()
    assert any(item["id"] == node_id for item in trees["data"])

    assert client.post(f"{BASE}/intent-tree/batch/disable", json={"ids": [node_id]}, headers=headers).json()["code"] == "0"
    assert client.post(f"{BASE}/intent-tree/batch/enable", json={"ids": [node_id]}, headers=headers).json()["code"] == "0"
    assert client.post(f"{BASE}/intent-tree/batch/delete", json={"ids": [node_id]}, headers=headers).json()["code"] == "0"


def test_ingestion_task_publishes_fallback_event_and_dashboard_counts() -> None:
    headers = login()
    rocketmq.drain_local_events()
    pipeline = client.post(f"{BASE}/ingestion/pipelines", json={"name": "default"}, headers=headers).json()["data"]
    task = client.post(f"{BASE}/ingestion/tasks", json={"pipelineId": pipeline["id"], "sourceType": "url", "sourceLocation": "https://example.com/a.txt"}, headers=headers).json()["data"]

    events = rocketmq.drain_local_events()
    assert events
    assert events[-1]["topic"] == "ingestion.task.created"
    assert events[-1]["payload"]["taskId"] == task["taskId"]

    listed = client.get(f"{BASE}/ingestion/tasks", headers=headers).json()
    assert listed["data"]["total"] >= 1
    overview = client.get(f"{BASE}/admin/dashboard/overview", headers=headers).json()
    assert {"knowledgeBaseCount", "documentCount", "chunkCount", "conversationCount", "traceCount", "requestCount"} <= set(overview["data"])


def test_rag_settings_exposes_model_health() -> None:
    headers = login()
    settings = client.get(f"{BASE}/rag/settings", headers=headers).json()
    assert settings["code"] == "0"
    assert settings["data"]["modelHealthPath"] == "/rag/model-health"

    health = client.get(f"{BASE}/rag/model-health", headers=headers).json()
    assert health["code"] == "0"
    assert health["data"]["status"] == "fallback"
    assert health["data"]["fallbackAvailable"] is True
    assert {item["kind"] for item in health["data"]["components"]} == {"chat", "embedding", "rerank"}
