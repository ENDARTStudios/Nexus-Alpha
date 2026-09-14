"""Testes da rota FastAPI /api/chat (com serviço mockado)."""
from __future__ import annotations

from fastapi.testclient import TestClient

import app as app_module


class FakeService:
    async def answer(self, message: str, session_id: str) -> dict:
        return {
            "reply": f"eco:{message}",
            "session_id": session_id,
            "reasoning_steps": ["Recebendo a pergunta.", "Sintetizando a resposta final."],
            "sources": ["neo4j"],
            "provider": "fake",
        }


def test_health_ok():
    client = TestClient(app_module.app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_endpoint_returns_reply(monkeypatch):
    monkeypatch.setattr(app_module, "get_chat_service", lambda: FakeService())
    client = TestClient(app_module.app)
    response = client.post("/api/chat", json={"message": "olá", "session_id": "s1"})
    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "eco:olá"
    assert body["session_id"] == "s1"
    assert body["provider"] == "fake"
    assert body["reasoning_steps"]


def test_chat_endpoint_rejects_empty_message():
    client = TestClient(app_module.app)
    response = client.post("/api/chat", json={"message": "", "session_id": "s1"})
    assert response.status_code == 422


def test_chat_rate_limit_returns_429(monkeypatch):
    from src.security.rate_limiter import InMemoryRateLimiter

    monkeypatch.setattr(
        app_module, "rate_limiter", InMemoryRateLimiter(requests_limit=1, window_seconds=60)
    )
    monkeypatch.setattr(app_module, "get_chat_service", lambda: FakeService())
    client = TestClient(app_module.app)
    first = client.post("/api/chat", json={"message": "a", "session_id": "r"})
    assert first.status_code == 200
    second = client.post("/api/chat", json={"message": "b", "session_id": "r"})
    assert second.status_code == 429
