"""Unit and Integration Tests for Phase 6 (FastAPI REST, WebSocket, and GUI Integration)."""

import pytest
import json
import asyncio
from fastapi.testclient import TestClient

from src.app.api import app
from src.workflows.orchestrator import orchestrator


@pytest.fixture
def client():
    return TestClient(app)


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "JARVIS Python Agent"
    assert data["tools_registered"] >= 15


def test_settings_endpoints(client):
    # GET settings
    get_res = client.get("/api/settings")
    assert get_res.status_code == 200
    settings_data = get_res.json()
    assert "activeModel" in settings_data

    # POST settings
    post_res = client.post("/api/settings", json={"activeModel": "llama3.2:3b", "temperature": 0.5})
    assert post_res.status_code == 200
    assert post_res.json()["activeModel"] == "llama3.2:3b"


def test_models_endpoint(client):
    res = client.get("/api/models")
    assert res.status_code == 200
    models = res.json()
    assert isinstance(models, list)
    assert len(models) > 0


def test_conversation_lifecycle(client):
    # 1. Create new conversation
    create_res = client.post("/api/conversations/new")
    assert create_res.status_code == 200
    conv = create_res.json()
    conv_id = conv["id"]
    assert isinstance(conv_id, str) and len(conv_id) > 0

    # 2. List conversations
    list_res = client.get("/api/conversations")
    assert list_res.status_code == 200
    all_convs = list_res.json()
    assert any(c["id"] == conv_id for c in all_convs)

    # 3. Get single conversation
    get_res = client.get(f"/api/conversations/{conv_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == conv_id

    # 4. Switch conversation
    switch_res = client.post(f"/api/conversations/{conv_id}/switch")
    assert switch_res.status_code == 200

    # 5. Delete conversation
    del_res = client.delete(f"/api/conversations/{conv_id}")
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True


def test_tool_execute_endpoint(client):
    res = client.post("/api/tools/execute", json={
        "tool_name": "calculate",
        "args": {"expression": "25 * 4"}
    })
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "100" in data["output"]


def test_confirm_save_file(client, tmp_path, monkeypatch):
    # Monkeypatch home directory to temporary path
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    res = client.post("/api/tools/confirm_save_file", json={
        "filename": "test_phase6.txt",
        "content": "Hello from Phase 6 Test!"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "test_phase6.txt" in data["filePath"]

    saved_file = tmp_path / "Desktop" / "test_phase6.txt"
    assert saved_file.is_file()
    assert saved_file.read_text(encoding="utf-8") == "Hello from Phase 6 Test!"


def test_chat_endpoint(client):
    # Direct chat endpoint execution
    res = client.post("/api/chat", json={
        "query": "Berapa hasil dari 50 + 50?"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert len(data["response"]) > 0
    assert "conversation_id" in data


def test_websocket_chat_streaming(client):
    with client.websocket_connect("/ws/chat") as websocket:
        websocket.send_text(json.dumps({
            "type": "chat",
            "query": "Halo, tes websocket"
        }))

        received_types = set()
        for _ in range(250):
            try:
                msg = websocket.receive_json()
                msg_type = msg.get("type")
                received_types.add(msg_type)
                if msg_type == "done":
                    break
            except Exception:
                break

        assert "status" in received_types or "trace" in received_types
        assert "token" in received_types
        assert "done" in received_types


def test_gui_static_serving(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "Jarvis - AI Assistant" in res.text
    assert "api_adapter.js" in res.text

    # Test api_adapter.js is served
    adapter_res = client.get("/api_adapter.js")
    assert adapter_res.status_code == 200
    assert "window.jarvis" in adapter_res.text


if __name__ == "__main__":
    pytest.main(["-v", "tests/test_phase6.py"])
