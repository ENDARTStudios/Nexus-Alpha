"""Testes do rate limit por token em /api/ingest (#054.1).

Invariantes: auth (401) precede o limiter e não consome cota; acima do limite
→ 429 com ``Retry-After``; o token cru nunca aparece em chave, log ou corpo.
"""
from __future__ import annotations

import logging

from fastapi.testclient import TestClient

import app as app_module
from src.security.rate_limiter import InMemoryRateLimiter, fingerprint_secret


def _client_with_limit(monkeypatch, requests_limit: int) -> TestClient:
    monkeypatch.setattr(
        app_module,
        "ingest_limiter",
        InMemoryRateLimiter(requests_limit=requests_limit, window_seconds=60),
    )
    return TestClient(app_module.app)


def _payload(url: str = "https://example.com/x") -> dict:
    return {
        "source_url": url,
        "timestamp": 1,
        "domain_score": 0.5,
        "title": "t",
        "extracted_entities": [],
    }


def _post(client: TestClient, token: str, url: str = "https://example.com/x"):
    return client.post(
        "/api/ingest",
        json=_payload(url),
        headers={"X-Nexus-Token": token},
    )


def test_ingest_auth_precedes_rate_limit_and_does_not_consume(monkeypatch):
    client = _client_with_limit(monkeypatch, requests_limit=1)
    invalid = _post(client, "token-invalido")
    assert invalid.status_code == 401
    # Se o 401 tivesse consumido cota, esta chamada válida seria 429.
    valid = _post(client, app_module.API_SECRET_TOKEN)
    assert valid.status_code == 200


def test_ingest_429_with_retry_after_above_limit(monkeypatch):
    client = _client_with_limit(monkeypatch, requests_limit=2)
    token = app_module.API_SECRET_TOKEN
    assert _post(client, token, "https://example.com/1").status_code == 200
    assert _post(client, token, "https://example.com/2").status_code == 200
    third = _post(client, token, "https://example.com/3")
    assert third.status_code == 429
    assert int(third.headers["retry-after"]) >= 1


def test_ingest_429_log_and_body_never_contain_raw_token(monkeypatch, caplog):
    client = _client_with_limit(monkeypatch, requests_limit=1)
    raw_token = f"{app_module.API_SECRET_TOKEN}-sufixo-para-diferenciar"
    with caplog.at_level(logging.WARNING):
        first = _post(client, app_module.API_SECRET_TOKEN)
        blocked = _post(client, app_module.API_SECRET_TOKEN)
    assert first.status_code == 200
    assert blocked.status_code == 429
    assert raw_token not in blocked.text
    assert app_module.API_SECRET_TOKEN not in caplog.text
    assert fingerprint_secret(app_module.API_SECRET_TOKEN) in caplog.text
