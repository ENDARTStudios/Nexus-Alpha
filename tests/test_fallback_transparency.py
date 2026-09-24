"""Testes da transparência de fallback (#058.4).

Invariante: fallback demo-memory nunca mascara falha de extração como
``partial_success``/``success``; nunca grava ``:Fato``/vetor/quórum; métricas
``fallback_health`` expõem o estado; flag ``NEXUS_ALLOW_DEMO_FALLBACK`` default
false em produção.
"""
from __future__ import annotations

import json
import os

from fastapi.testclient import TestClient

import app as app_module


class _FakeGraphDown:
    """Neo4j indisponível: ingest falha sem gravar nada."""

    verify_quorum = 3

    def __init__(self):
        self.ingest_calls = 0
        self.episode_calls = 0

    async def graph_snapshot(self):
        return {
            "concepts": 0, "facts": 0, "verified": 0, "cross_source": 0,
            "max_confirmacoes": 1, "consolidated": 0, "hebbian": 0,
            "episodes": 0, "last_episode": None, "ok": False,
        }

    async def ingest_payload(self, payload):
        self.ingest_calls += 1
        raise RuntimeError("neo4j down")

    async def count_verified(self):
        return 0

    async def persist_episodes(self, episodes):
        self.episode_calls += 1
        return 0

    async def ensure_schema(self):
        return True

    async def close(self):
        return None


class _FakeGraphUp:
    """Neo4j saudável: aceita entidades refinadas."""

    verify_quorum = 3

    def __init__(self):
        self.ingested = []
        self.episode_calls = 0

    async def graph_snapshot(self):
        return {
            "concepts": 1, "facts": 1, "verified": 0, "cross_source": 0,
            "max_confirmacoes": 1, "consolidated": 0, "hebbian": 0,
            "episodes": 0, "last_episode": None, "ok": True,
        }

    async def ingest_payload(self, payload):
        self.ingested.append(payload)
        return len(payload.get("extracted_entities", []))

    async def count_verified(self):
        return 0

    async def persist_episodes(self, episodes):
        self.episode_calls += 1
        return len(episodes)

    async def ensure_schema(self):
        return True

    async def close(self):
        return None


class _FakeVector:
    def __init__(self):
        self.stored = 0

    def count(self):
        return 0

    @property
    def embedding_dim(self):
        return 8

    def store_memory(self, **kwargs):
        self.stored += 1
        return True


def _reset_app(monkeypatch, graph=None, vector=None, allow_demo=None):
    app_module._graph_connector = graph if graph is not None else _FakeGraphDown()
    app_module._vector_connector = vector if vector is not None else _FakeVector()
    app_module._quarantine = None
    app_module._brain = None
    app_module._rejection_quarantine = None
    app_module._ingest_accounting.reset()
    for key in list(app_module._fallback_stats):
        app_module._fallback_stats[key] = 0
    if allow_demo is None:
        monkeypatch.delenv("NEXUS_ALLOW_DEMO_FALLBACK", raising=False)
    else:
        monkeypatch.setenv("NEXUS_ALLOW_DEMO_FALLBACK", allow_demo)
    return TestClient(app_module.app)


def _headers() -> dict:
    return {"X-Nexus-Token": app_module.API_SECRET_TOKEN}


def _payload(entities=None, url="https://example.com/x"):
    return {
        "source_url": url,
        "timestamp": 1,
        "domain_score": 0.5,
        "title": "t",
        "extracted_entities": entities if entities is not None else [],
    }


def _valid_entity():
    return {"subject": "AI", "predicate": "usa", "object": "redes_neurais", "confidence": 0.9}


def test_status_not_success_when_demo_and_zero_entities(monkeypatch):
    """Caso 1 — demo + entities=0 nunca success/partial_success (#058.4)."""
    graph = _FakeGraphDown()
    client = _reset_app(monkeypatch, graph=graph, allow_demo="true")
    resp = client.post("/api/ingest", json=_payload(entities=[]), headers=_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] != "success"
    assert body["status"] != "partial_success"
    assert body["status"] in {"degraded", "failed"}
    assert body["db_status"] == "demo-memory"
    assert body["entities_processed"] == 0
    assert body["masked_extraction_failure"] is True


def test_fallback_writes_nothing_to_graph_or_vectors(monkeypatch):
    """Caso 2 — fallback não grava :Fato/vetor/quórum (#058.4)."""
    graph = _FakeGraphDown()
    vector = _FakeVector()
    client = _reset_app(monkeypatch, graph=graph, vector=vector, allow_demo="true")
    # entidades válidas no payload, mas Neo4j falha → nada persiste
    resp = client.post(
        "/api/ingest", json=_payload(entities=[_valid_entity()]), headers=_headers()
    )
    body = resp.json()
    assert body["db_status"] == "demo-memory"
    assert body["vectors_indexed"] == 0
    assert vector.stored == 0
    assert graph.episode_calls == 0
    metrics = client.get("/api/metrics").json()
    assert metrics["fallback_health"]["fallback_promoted_to_graph"] == 0
    # ingest foi tentado mas não gravou (fake levanta exceção)
    assert graph.ingest_calls >= 1


def test_flag_off_in_production_defaults_failed(monkeypatch):
    """Caso 3 — NEXUS_ALLOW_DEMO_FALLBACK default false → failed (#058.4)."""
    client = _reset_app(monkeypatch, graph=_FakeGraphDown(), allow_demo=None)
    # sem env → default false
    assert "NEXUS_ALLOW_DEMO_FALLBACK" not in os.environ
    resp = client.post("/api/ingest", json=_payload(entities=[]), headers=_headers())
    body = resp.json()
    assert body["status"] == "failed"
    assert body["allow_demo_fallback"] is False
    assert body["masked_extraction_failure"] is True
    # flag explícita false também
    client2 = _reset_app(monkeypatch, graph=_FakeGraphDown(), allow_demo="false")
    resp2 = client2.post("/api/ingest", json=_payload(entities=[]), headers=_headers())
    assert resp2.json()["status"] == "failed"
    assert resp2.json()["allow_demo_fallback"] is False


def test_fallback_metrics_increment(monkeypatch):
    """Caso 4 — métricas fallback_health + extraction_quality (#058.4)."""
    client = _reset_app(monkeypatch, graph=_FakeGraphDown(), allow_demo="true")
    for i in range(2):
        client.post(
            "/api/ingest",
            json=_payload(entities=[], url=f"https://example.com/{i}"),
            headers=_headers(),
        )
    metrics = client.get("/api/metrics").json()
    fh = metrics["fallback_health"]
    assert fh["demo_memory_events"] == 2
    assert fh["masked_extraction_failures"] == 2
    assert fh["sources_with_zero_entities"] == 2
    assert fh["fallback_promoted_to_graph"] == 0
    assert fh["allow_demo_fallback"] is True
    eq = metrics["extraction_quality"]
    assert eq["fallback_events"] == 2
    assert eq["masked_extraction_failures"] == 2


def test_metrics_no_secret_leak(monkeypatch):
    """Caso 5 — anti-leak: fallback_health não expõe segredos (#058.4)."""
    client = _reset_app(monkeypatch, graph=_FakeGraphDown(), allow_demo="true")
    client.post("/api/ingest", json=_payload(entities=[]), headers=_headers())
    text = client.get("/api/metrics").text
    for marker in (
        "HF_TOKEN",
        "NEXUS_API_TOKEN",
        "NEO4J_URI",
        "NEO4J_PASSWORD",
        "QDRANT_API_KEY",
        "X-Nexus-Token",
        app_module.API_SECRET_TOKEN,
    ):
        assert marker not in text
    body = json.loads(text)
    assert "fallback_health" in body
    assert set(body["fallback_health"]) >= {
        "demo_memory_events",
        "masked_extraction_failures",
        "fallback_promoted_to_graph",
        "sources_with_zero_entities",
        "allow_demo_fallback",
    }


def test_success_path_unchanged_when_graph_up(monkeypatch):
    """Sanidade — caminho saudável continua success (#058.4)."""
    graph = _FakeGraphUp()
    vector = _FakeVector()
    client = _reset_app(monkeypatch, graph=graph, vector=vector, allow_demo=None)
    resp = client.post(
        "/api/ingest", json=_payload(entities=[_valid_entity()]), headers=_headers()
    )
    body = resp.json()
    assert body["status"] == "success"
    assert body["db_status"] == "cluster-active"
    assert body["entities_processed"] >= 1
    assert body["masked_extraction_failure"] is False
    assert vector.stored == 1
    metrics = client.get("/api/metrics").json()
    assert metrics["fallback_health"]["demo_memory_events"] == 0
    assert metrics["fallback_health"]["masked_extraction_failures"] == 0
