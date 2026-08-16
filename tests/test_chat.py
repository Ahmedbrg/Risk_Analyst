from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_chat_single_message():
    """Should return a risk analysis for a chat message."""
    resp = client.post("/api/v1/chat", json={"message": "Revenue decreased 30%."}) 
    assert resp.status_code == 200
    data = resp.json()
    assert data["role"] == "assistant"
    assert data["risk_analysis"] is not None


def test_chat_follow_up():
    """Follow-up messages should keep the same conversation."""
    # First message
    resp1 = client.post("/api/v1/chat", json={"message": "Revenue decreased 30%."})
    conv_id = resp1.json()["risk_analysis"]["conversation_id"]

    # Follow-up
    resp2 = client.post("/api/v1/chat", json={
        "conversation_id": conv_id,
        "message": "We only have two months of cash left.",
    })
    assert resp2.status_code == 200
    assert resp2.json()["risk_analysis"]["conversation_id"] == conv_id


def test_conversation_history():
    """Should be able to retrieve conversation history."""
    resp = client.post("/api/v1/chat", json={"message": "Our main contract expires soon."})
    conv_id = resp.json()["risk_analysis"]["conversation_id"]

    hist = client.get(f"/api/v1/conversations/{conv_id}")
    assert hist.status_code == 200
    assert len(hist.json()["messages"]) >= 2  # user + assistant
