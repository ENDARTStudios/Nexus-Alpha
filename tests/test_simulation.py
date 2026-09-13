"""Testes do motor de simulação de enxame (SwarmSimulator) e da rota /api/simulate."""
from __future__ import annotations

from fastapi.testclient import TestClient

import app as app_module
from src.simulation import SwarmSimulator


def _chain_topology():
    return {
        "nodes": [{"id": "A"}, {"id": "B"}, {"id": "C"}],
        "links": [
            {"source": "A", "target": "B"},
            {"source": "B", "target": "C"},
        ],
    }


def test_from_topology_builds_agents_and_edges():
    sim = SwarmSimulator.from_topology(_chain_topology())
    assert set(sim.agents) == {"A", "B", "C"}
    assert sim.edge_count == 2
    assert "B" in sim.agents["A"].neighbors


def test_run_reduces_variance():
    sim = SwarmSimulator.from_topology(_chain_topology())
    sim.agents["A"].stance = 0.9
    sim.agents["C"].stance = 0.1
    initial = sim.report([])["std_stance"]
    final = sim.report(sim.run(rounds=25))["std_stance"]
    assert final <= initial


def test_deterministic_with_seed():
    first = SwarmSimulator.from_topology(_chain_topology(), seed=7).run(5)
    second = SwarmSimulator.from_topology(_chain_topology(), seed=7).run(5)
    assert first == second


def test_inject_sets_stance_only_for_known_agents():
    sim = SwarmSimulator.from_topology({"nodes": [{"id": "A"}, {"id": "B"}], "links": []})
    assert sim.inject({"A": 0.95, "Z": 0.5}) == 1
    assert sim.agents["A"].stance == 0.95


def test_report_uniform_opinion_is_consensus():
    sim = SwarmSimulator.from_topology(
        {"nodes": [{"id": "A"}, {"id": "B"}], "links": [{"source": "A", "target": "B"}]}
    )
    report = sim.report([])
    assert report["consensus"] == 1.0
    assert report["verdict"] == "convergencia"
    assert report["agent_count"] == 2


def test_empty_graph_report():
    report = SwarmSimulator.from_topology({"nodes": [], "links": []}).report([])
    assert report["status"] == "empty"
    assert report["agent_count"] == 0


class FakeGraphForSim:
    async def topology(self):
        return {
            "nodes": [{"id": "IA"}, {"id": "Dados"}],
            "links": [{"source": "IA", "target": "Dados"}],
        }

    async def search_context(self, keywords, limit: int = 8):
        return [{"subject": "IA", "predicate": "USA", "object": "Dados"}]


def test_simulate_endpoint_full_graph(monkeypatch):
    monkeypatch.setattr(app_module, "_graph_connector", FakeGraphForSim())
    client = TestClient(app_module.app)
    response = client.post("/api/simulate", json={"rounds": 5, "seed": 1})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["agent_count"] == 2


def test_simulate_endpoint_by_topic(monkeypatch):
    monkeypatch.setattr(app_module, "_graph_connector", FakeGraphForSim())
    client = TestClient(app_module.app)
    response = client.post("/api/simulate", json={"topic": "IA", "rounds": 3})
    assert response.status_code == 200
    assert response.json()["agent_count"] == 2
