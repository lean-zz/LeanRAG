from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.ids import new_id
from app.infra.messaging import rocketmq
from app.main import app
from app.services.store import store


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


def test_dashboard_overview_includes_support_quality_metrics() -> None:
    headers = login()
    store.traces.clear()
    store.trace_nodes.clear()
    store.feedbacks.clear()

    store.traces["trace-tool"] = {
        "id": "trace-tool",
        "traceId": "trace-tool",
        "question": "What is the status of ticket T-10001?",
        "status": "completed",
        "createTime": "2026-06-26T10:00:00",
    }
    store.trace_nodes["trace-tool"] = [
        {"id": new_id(), "nodeType": "INTENT", "nodeName": "after_sales.ticket_status", "status": "completed"},
        {"id": new_id(), "nodeType": "TOOL_CALL", "nodeName": "get_ticket_status", "status": "completed"},
    ]
    store.traces["trace-no-answer"] = {
        "id": "trace-no-answer",
        "traceId": "trace-no-answer",
        "question": "Unknown X100 policy question",
        "status": "completed",
        "createTime": "2026-06-26T10:01:00",
    }
    store.trace_nodes["trace-no-answer"] = [
        {"id": new_id(), "nodeType": "RETRIEVE", "nodeName": "retrieval-engine", "status": "completed", "chunkCount": 0, "hasMcp": False},
    ]
    store.traces["trace-escalation"] = {
        "id": "trace-escalation",
        "traceId": "trace-escalation",
        "question": "The X100 is smoking. Can I keep testing?",
        "status": "completed",
        "createTime": "2026-06-26T10:02:00",
    }
    store.trace_nodes["trace-escalation"] = [
        {"id": new_id(), "nodeType": "INTENT", "nodeName": "after_sales.escalation", "status": "completed"},
    ]
    store.feedbacks["feedback-low"] = {
        "id": "feedback-low",
        "messageId": "message-low",
        "userId": "1",
        "feedbackType": "dislike",
        "content": "answer missed warranty basis",
        "createTime": "2026-06-26T10:03:00",
    }

    overview = client.get(f"{BASE}/admin/dashboard/overview", headers=headers).json()
    quality = overview["data"]["supportQuality"]

    assert quality["totalSupportQuestions"] == 3
    assert quality["noAnswerCount"] == 1
    assert quality["toolCallCount"] == 1
    assert quality["escalationCount"] == 1
    assert quality["topIntents"][0]["intent"] == "after_sales.escalation"
    assert quality["recentLowQualityFeedback"][0]["content"] == "answer missed warranty basis"


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
