"""Testes da contabilidade do ingest (#052) — accounting puro + anti-leak."""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

import app as app_module
from app import IngestAccounting


def _t(subject: str, predicate: str, obj: str) -> dict:
    return {"subject": subject, "predicate": predicate, "object": obj}


def test_case1_intra_url_duplicate():
    acct = IngestAccounting()
    acct.record_payload(
        [_t("IA", "UTILIZA", "APRENDIZADO PROFUNDO"), _t("IA", "UTILIZA", "APRENDIZADO PROFUNDO")],
        source_url="https://a.com/x", domain="a.com",
    )
    snap = acct.snapshot(raw_triples=2, rejected_noise=0, persisted_facts=1)
    assert snap["distinct_canonical_keys"] == 1
    assert snap["duplicate_same_source_url"] == 1
    assert snap["duplicate_canonical_occurrences"] == 1
    assert snap["canonical_to_fact_gap"] == 0
    assert snap["unaccounted_raw"] == 0


def test_case2_duplicate_same_domain():
    acct = IngestAccounting()
    acct.record_payload([_t("IA", "UTILIZA", "X")], "https://a.com/1", "a.com")
    acct.record_payload([_t("IA", "UTILIZA", "X")], "https://a.com/2", "a.com")
    snap = acct.snapshot(raw_triples=2, rejected_noise=0, persisted_facts=1)
    assert snap["distinct_canonical_keys"] == 1
    assert snap["duplicate_same_domain"] == 1
    assert snap["duplicate_cross_domain"] == 0
    assert snap["duplicate_canonical_occurrences"] == 1


def test_case3_duplicate_cross_domain():
    acct = IngestAccounting()
    acct.record_payload([_t("IA", "UTILIZA", "X")], "https://a.com/1", "a.com")
    acct.record_payload([_t("IA", "UTILIZA", "X")], "https://b.com/1", "b.com")
    acct.record_payload([_t("IA", "UTILIZA", "X")], "https://c.com/1", "c.com")
    snap = acct.snapshot(raw_triples=3, rejected_noise=0, persisted_facts=1)
    assert snap["distinct_canonical_keys"] == 1
    assert snap["duplicate_cross_domain"] == 2
    assert snap["duplicate_canonical_occurrences"] == 2
    assert snap["new_facts_created"] == 1


def test_case4_reconciliation_closes():
    acct = IngestAccounting()
    acct.record_payload([_t("A", "UTILIZA", "1"), _t("B", "UTILIZA", "2"),
                         _t("C", "UTILIZA", "3"), _t("D", "UTILIZA", "4")], "https://x.com/1", "x.com")
    acct.record_payload([_t("C", "UTILIZA", "3"), _t("D", "UTILIZA", "4"), _t("E", "UTILIZA", "5")],
                        "https://y.com/1", "y.com")
    snap = acct.snapshot(raw_triples=10, rejected_noise=3, persisted_facts=5)
    assert snap["canonical_triples"] == 7
    assert snap["distinct_canonical_keys"] == 5
    assert snap["duplicate_canonical_occurrences"] == 2
    assert snap["canonical_to_fact_gap"] == 0
    assert snap["unaccounted_raw"] == 0


def test_accounting_mode_bounded():
    acct = IngestAccounting(max_keys=2)
    for i in range(5):
        acct.record_payload([_t(f"S{i}", "UTILIZA", "O")], f"https://d{i}.com/1", f"d{i}.com")
    assert acct.accounting_mode == "approximate_overflow"


class _FakeGraph:
    verify_quorum = 3

    def __init__(self):
        self.ingested = []

    async def graph_snapshot(self):
        return {
            "concepts": 10, "facts": 4, "verified": 0, "cross_source": 0,
            "max_confirmacoes": 1, "consolidated": 0, "hebbian": 0,
            "episodes": 0, "last_episode": None, "ok": True,
        }

    async def ingest_payload(self, payload):
        self.ingested.append(payload)
        return len(payload.get("extracted_entities", []))

    async def count_verified(self):
        return 0

    async def persist_episodes(self, episodes):
        return len(episodes)

    async def ensure_schema(self):
        return True

    async def close(self):
        return None


class _FakeVector:
    def count(self):
        return 0

    def store_memory(self, **kwargs):
        return True


def test_metrics_exposes_ingestion_accounting():
    app_module._graph_connector = _FakeGraph()
    app_module._vector_connector = _FakeVector()
    app_module._quarantine = None
    app_module._brain = None
    app_module._rejection_quarantine = None
    app_module._ingest_accounting.reset()
    client = TestClient(app_module.app)
    body = client.get("/api/metrics").json()
    accounting = body["ingestion_accounting"]
    assert accounting["persisted_facts"] == 4
    assert accounting["distinct_canonical_keys"] == 0
    assert accounting["canonical_to_fact_gap"] == -4
    assert set(accounting) >= {
        "raw_triples", "canonical_triples", "distinct_canonical_keys",
        "duplicate_canonical_occurrences", "persisted_facts", "canonical_to_fact_gap",
        "unaccounted_raw", "duplicate_same_source_url", "duplicate_same_domain",
        "duplicate_cross_domain", "rejected_after_canonical",
        "merged_into_existing_fact", "new_facts_created", "process_started_at",
        "last_ingest_at", "accounting_mode",
    }


def test_metrics_does_not_leak_secrets():
    import os

    app_module._graph_connector = _FakeGraph()
    app_module._vector_connector = _FakeVector()
    app_module._quarantine = None
    app_module._rejection_quarantine = None
    client = TestClient(app_module.app)
    text = client.get("/api/metrics").text
    for marker in ("HF_TOKEN", "NEXUS_API_TOKEN", "NEO4J_URI", "NEO4J_PASSWORD", "QDRANT_API_KEY", "X-Nexus-Token"):
        assert marker not in text
    for value in (os.environ.get("HF_TOKEN"), os.environ.get("NEXUS_API_TOKEN"), os.environ.get("NEO4J_PASSWORD")):
        if value:
            assert value not in text
    assert json.loads(text)["status"] == "online"
