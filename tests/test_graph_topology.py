"""Testes da topologia do grafo (GraphConnector + rota /api/graph/topology)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app as app_module
from src.database.graph_connector import GraphConnector


class FakeResult:
    def __init__(self, records):
        self._records = records
        self._iterator = None

    def __aiter__(self):
        self._iterator = iter(self._records)
        return self

    async def __anext__(self):
        try:
            return next(self._iterator)
        except StopIteration:
            raise StopAsyncIteration


class FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def run(self, query, **kwargs):
        return FakeResult([
            {"sujeito": "IA", "relacao": "UTILIZA", "objeto": "Redes Neurais", "verificado": True},
            {"sujeito": "Nexus-Alpha", "relacao": "EVOLUI", "objeto": "IA", "verificado": False},
        ])


class FakeDriver:
    def session(self):
        return FakeSession()


@pytest.mark.asyncio
async def test_topology_returns_demo_when_connection_fails(monkeypatch):
    connector = GraphConnector()
    connector.driver = None

    async def boom():
        raise RuntimeError("cluster offline")

    monkeypatch.setattr(connector, "connect", boom)
    result = await connector.topology()
    assert result["nodes"][0]["id"] == "Nexus-Alpha Core"
    assert result["links"] == []


@pytest.mark.asyncio
async def test_topology_builds_nodes_and_links():
    connector = GraphConnector()
    connector.driver = FakeDriver()
    result = await connector.topology()
    ids = {node["id"] for node in result["nodes"]}
    assert {"IA", "Redes Neurais", "Nexus-Alpha"} <= ids
    assert any(
        link["source"] == "IA"
        and link["target"] == "Redes Neurais"
        and link["label"] == "UTILIZA"
        for link in result["links"]
    )
    assert len(result["links"]) == 2
    verified_nodes = {node["id"] for node in result["nodes"] if node.get("verified")}
    assert "Redes Neurais" in verified_nodes and "Nexus-Alpha" not in verified_nodes


class FakeConnector:
    async def topology(self, limit: int = 100):
        return {
            "nodes": [{"id": "X", "group": 1, "val": 15}],
            "links": [],
        }

    async def graph_snapshot(self):
        return {
            "concepts": 3,
            "facts": 10,
            "verified": 2,
            "consolidated": 1,
            "hebbian": 1,
            "episodes": 5,
            "last_episode": "2026-09-21T00:00:00+00:00",
            "ok": True,
        }

    async def count_concepts(self) -> int:
        return 3

    async def count_verified(self) -> int:
        return 2

    async def ensure_schema(self) -> bool:
        return True

    async def close(self):
        return None


class FakeVector:
    def count(self) -> int:
        return 7


def test_topology_endpoint(monkeypatch):
    monkeypatch.setattr(app_module, "GraphConnector", lambda: FakeConnector())
    monkeypatch.setattr(app_module, "_graph_connector", None)
    client = TestClient(app_module.app)
    response = client.get("/api/graph/topology")
    assert response.status_code == 200
    body = response.json()
    assert body["nodes"][0]["id"] == "X"


def test_metrics_endpoint(monkeypatch):
    monkeypatch.setattr(app_module, "_graph_connector", FakeConnector())
    monkeypatch.setattr(app_module, "_vector_connector", FakeVector())
    monkeypatch.setattr(app_module, "_quarantine", None)
    client = TestClient(app_module.app)
    response = client.get("/api/metrics")
    assert response.status_code == 200
    body = response.json()
    assert body["facts"] == 3
    assert body["vectors"] == 7
    assert body["episodes"] == 5
    assert "quarantine" in body
    health = body["cognitive_health"]
    assert set(health) == {
        "episodic_persistence_rate",
        "hebbian_consistency_check",
        "retention_pressure",
    }
    assert health["hebbian_consistency_check"] is True
    assert health["retention_pressure"] == "low"
