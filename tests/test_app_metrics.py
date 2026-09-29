"""#052.3 - clareza metrica do /api/metrics.

Garante que o contrato expoe, sem ambiguidade:
* `facts` legado preservado (compatibilidade) + `concept_count` / `fact_count`;
* `ingestion_accounting.run_scoped_gap` e `graph_scoped_gap`;
* verificacao/qualidade intactas (quorum 3, sem promocao de fallback);
* anti-leak (nenhum segredo no payload).
"""
from __future__ import annotations

from fastapi.testclient import TestClient

import app as app_module


class _FakeGraph:
    verify_quorum = 3

    async def graph_snapshot(self):
        return {
            "concepts": 1894,
            "facts": 335,
            "verified": 11,
            "cross_source": 12,
            "max_confirmacoes": 3,
            "consolidated": 0,
            "hebbian": 0,
            "episodes": 2260,
            "last_episode": None,
            "ok": True,
            "distinct_fact_hashes": 314,
        }

    async def count_verified(self):
        return 11

    async def verified_fact_domain_counts(self):
        return {
            "pt.wikipedia.org": 10,
            "en.wikipedia.org": 10,
            "rsssf.org": 5,
            "nominatim.openstreetmap.org": 4,
        }

    async def get_fact_accounting_counts(self):
        return {
            "persisted_facts": 335,
            "distinct_non_null_fact_hashes": 335,
            "missing_fact_hash_count": 0,
            "distinct_fact_node_keys": 335,
            "duplicate_fact_hash_group_count": 0,
        }

    async def close(self):
        return None


class _FakeVector:
    def count(self):
        return 1137


def _client() -> TestClient:
    app_module._graph_connector = _FakeGraph()
    app_module._vector_connector = _FakeVector()
    app_module._quarantine = None
    app_module._brain = None
    app_module._rejection_quarantine = None
    app_module._ingest_accounting.reset()
    for key in list(app_module._fallback_stats):
        app_module._fallback_stats[key] = 0
    app_module._unmapped_predicates.clear()
    app_module._invalid_predicates.clear()
    for key in list(app_module._extraction_stats):
        value = app_module._extraction_stats[key]
        if isinstance(value, dict):
            for inner in value:
                value[inner] = 0
        else:
            app_module._extraction_stats[key] = 0
    return TestClient(app_module.app)


def test_metrics_clarity_fields_present_and_legacy_preserved():
    body = _client().get("/api/metrics").json()
    assert body["status"] == "online"
    # Legado preservado (mesma semantica de antes: :Conceito) para compatibilidade.
    assert body["facts"] == 1894
    assert body["concept_count"] == 1894
    assert body["fact_count"] == 335
    assert body["verified_facts"] == 11


def test_metrics_scoped_gaps_exposed():
    accounting = _client().get("/api/metrics").json()["ingestion_accounting"]
    assert "run_scoped_gap" in accounting
    assert "graph_scoped_gap" in accounting
    assert "run_distinct_canonical_keys" in accounting
    assert "run_persisted_facts_created" in accounting
    assert "graph_distinct_fact_hashes" in accounting
    # #052.3.1 — nova base contábil + status
    assert accounting["distinct_fact_node_keys"] == 335
    assert accounting["fact_accounting_status"] == "ok"
    assert accounting["graph_scoped_gap"] == 0
    assert accounting["persisted_facts"] == 335


def test_metrics_verification_and_quality_contract():
    body = _client().get("/api/metrics").json()
    assert body["verification"]["quorum"] == 3
    assert body["verification"]["verified_facts_domain_independent"] == 11
    assert body["verification"]["facts_with_multi_domain"] == 12
    assert body["verification"]["max_domain_confirmations"] == 3
    assert body["ingestion_accounting"]["duplicate_cross_domain"] == 0
    assert body["extraction_quality"]["top_invalid_predicates"] == []
    assert body["fallback_health"]["fallback_promoted_to_graph"] == 0
    assert body["ingestion_accounting"]["unaccounted_raw"] == 0


def test_metrics_glossary_present():
    body = _client().get("/api/metrics").json()
    assert "metric_glossary" in body
    assert body["metric_glossary"]["concept_count"]
    assert body["metric_glossary"]["fact_count"]
    assert body["metric_glossary"]["run_scoped_gap"]
    assert body["metric_glossary"]["graph_scoped_gap"]


def test_metrics_publisher_family_telemetry():
    body = _client().get("/api/metrics").json()
    assert body["publisher_family_count"] == 3
    assert body["effective_publisher_count"] == 3
    assert set(body["publisher_family_distribution"]) == {"Wikimedia", "RSSSF", "OpenStreetMap"}
    assert "RSSSF_AND_RSSSF_BRASIL_SAME_FAMILY_SUSPECTED" in body["publisher_independence_warnings"]
    assert "OPENSTREETMAP_IS_GEOGRAPHIC_OPEN_DATA_NOT_NEWS_EDITORIAL" in body["publisher_independence_warnings"]
    # contrato legado preservado
    assert body["concept_count"] == 1894
    assert body["fact_count"] == 335
    assert body["verification"]["quorum"] == 3


def test_metrics_no_secret_leak():
    text = _client().get("/api/metrics").text
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
