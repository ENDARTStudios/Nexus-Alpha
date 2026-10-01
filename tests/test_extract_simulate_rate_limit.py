"""Testes do rate limit em /api/extract e /api/simulate (#054.1).

Balde duplo no extract: anônimo 10/min por IP (``expensive_limiter``),
autenticado 120/min por token fingerprint (``expensive_auth_limiter``) —
o worker autônomo posta extrações em rajada por ciclo. Simulate é sempre
anônimo (10/min por IP). 429 sempre com ``Retry-After``.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

import app as app_module
from src.security.rate_limiter import InMemoryRateLimiter

_TEXT = "Nexus-Alpha extrai triplas verificadas de páginas públicas."  # min_length=20


def test_extract_anonymous_blocked_above_limit(monkeypatch):
    monkeypatch.setattr(
        app_module,
        "expensive_limiter",
        InMemoryRateLimiter(requests_limit=2, window_seconds=60),
    )
    client = TestClient(app_module.app)
    assert client.post("/api/extract", json={"text": _TEXT}).status_code == 200
    assert client.post("/api/extract", json={"text": _TEXT}).status_code == 200
    third = client.post("/api/extract", json={"text": _TEXT})
    assert third.status_code == 429
    assert int(third.headers["retry-after"]) >= 1


def test_extract_authenticated_uses_own_token_bucket(monkeypatch):
    monkeypatch.setattr(
        app_module,
        "expensive_limiter",
        InMemoryRateLimiter(requests_limit=1, window_seconds=60),
    )
    monkeypatch.setattr(
        app_module,
        "expensive_auth_limiter",
        InMemoryRateLimiter(requests_limit=2, window_seconds=60),
    )
    client = TestClient(app_module.app)
    headers = {"X-Nexus-Token": app_module.API_SECRET_TOKEN}
    # Anônimo esgota o balde público de IP.
    assert client.post("/api/extract", json={"text": _TEXT}).status_code == 200
    assert client.post("/api/extract", json={"text": _TEXT}).status_code == 429
    # Autenticado usa balde próprio (não herda o bloqueio de IP).
    assert client.post("/api/extract", json={"text": _TEXT}, headers=headers).status_code == 200
    assert client.post("/api/extract", json={"text": _TEXT}, headers=headers).status_code == 200
    assert client.post("/api/extract", json={"text": _TEXT}, headers=headers).status_code == 429


def test_extract_invalid_token_falls_back_to_ip_bucket(monkeypatch):
    monkeypatch.setattr(
        app_module,
        "expensive_limiter",
        InMemoryRateLimiter(requests_limit=1, window_seconds=60),
    )
    client = TestClient(app_module.app)
    headers = {"X-Nexus-Token": "token-invalido"}
    assert client.post("/api/extract", json={"text": _TEXT}, headers=headers).status_code == 200
    assert client.post("/api/extract", json={"text": _TEXT}, headers=headers).status_code == 429


class _FakeGraphForRateLimit:
    """Grafo mínimo autossuficiente (não depende de estado de outros testes)."""

    async def topology(self):
        return {
            "nodes": [{"id": "IA"}, {"id": "Dados"}],
            "links": [{"source": "IA", "target": "Dados"}],
        }


def test_simulate_anonymous_blocked_above_limit(monkeypatch):
    monkeypatch.setattr(
        app_module,
        "expensive_limiter",
        InMemoryRateLimiter(requests_limit=1, window_seconds=60),
    )
    monkeypatch.setattr(app_module, "_graph_connector", _FakeGraphForRateLimit())
    client = TestClient(app_module.app)
    first = client.post("/api/simulate", json={"rounds": 2, "seed": 1})
    assert first.status_code == 200
    second = client.post("/api/simulate", json={"rounds": 2, "seed": 1})
    assert second.status_code == 429
    assert int(second.headers["retry-after"]) >= 1
