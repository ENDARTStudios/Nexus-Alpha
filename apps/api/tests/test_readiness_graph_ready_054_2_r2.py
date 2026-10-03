"""Testes do patch aditivo de readiness em /api/metrics (#054.2.R2, T1-T6).

Fakes espelham o contrato do worker incident (#048.10M.1.2): durante o wake-up
do AuraDB, ``graph_snapshot`` retorna ``ok=False`` com contadores zerados — o
endpoint deve sinalizar ``graph_ready=False`` + ``status="booting"`` em vez de
servir zeros como se fossem baseline vazia.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

from fastapi.testclient import TestClient

import app as app_module


def _load_script_module(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).resolve().parents[1] / "scripts" / relative
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TELEMETRY_CLI = _load_script_module(
    "check_space_telemetry_cli", "check_space_telemetry.py"
)


def _snapshot(ok: bool, verified: int = 20) -> dict:
    return {
        "concepts": 2023 if ok else 0,
        "facts": 598 if ok else 0,
        "verified": verified if ok else 0,
        "cross_source": 0,
        "max_confirmacoes": 1,
        "consolidated": 0,
        "hebbian": 0,
        "episodes": 0,
        "last_episode": None,
        "ok": ok,
    }


class _FakeGraph:
    verify_quorum = 3

    def __init__(self, ok: bool):
        self._ok = ok

    async def graph_snapshot(self):
        return _snapshot(self._ok)

    async def verified_fact_domain_counts(self):
        if not self._ok:
            raise RuntimeError("neo4j waking up")
        return {"pt.wikipedia.org": 20}

    async def get_fact_accounting_counts(self):
        return None

    async def ensure_schema(self):
        return True

    async def close(self):
        return None


def _client_with(monkeypatch, ok: bool) -> TestClient:
    monkeypatch.setattr(app_module, "_graph_connector", _FakeGraph(ok))
    return TestClient(app_module.app)


def test_t1_metrics_not_silent_zeros_when_driver_not_ready(monkeypatch):
    """T1 — ok=False (cold boot) NÃO vira baseline vazia silenciosa:
    expõe graph_ready=False + status booting + boot_reason, mantendo campos."""
    client = _client_with(monkeypatch, ok=False)
    response = client.get("/api/metrics")
    assert response.status_code == 200
    body = response.json()
    assert body["graph_ready"] is False
    assert body["status"] == "booting"
    assert body["boot_reason"] == "neo4j_not_ready"
    # Campos existentes preservados (contrato aditivo).
    assert body["concept_count"] == 0
    assert body["fact_count"] == 0
    assert body["verification"]["quorum"] == 3
    assert body["cognitive_health"]["hebbian_consistency_check"] is False


def test_t2_metrics_online_when_graph_ready(monkeypatch):
    """T2 — com grafo respondendo: status online + graph_ready True + baseline."""
    client = _client_with(monkeypatch, ok=True)
    response = client.get("/api/metrics")
    assert response.status_code == 200
    body = response.json()
    assert body["graph_ready"] is True
    assert body["status"] == "online"
    assert body["verification"]["verified_facts_domain_independent"] == 20
    assert body["cognitive_health"]["hebbian_consistency_check"] is True


def test_t5_existing_contract_preserved_when_ready(monkeypatch):
    """T5 — nenhum campo do contrato legado desaparece quando pronto."""
    client = _client_with(monkeypatch, ok=True)
    body = client.get("/api/metrics").json()
    for key in [
        "status", "timestamp", "facts", "concept_count", "fact_count",
        "verified_facts", "publisher_family_count", "publisher_family_distribution",
        "effective_publisher_count", "publisher_independence_warnings", "vectors",
        "quarantine", "episodes", "cognitive_health", "extraction_quality",
        "fallback_health", "verification", "ingestion_accounting", "metric_glossary",
    ]:
        assert key in body, f"campo legado ausente: {key}"


def test_t6_endpoint_never_claims_ready_when_snapshot_failed(monkeypatch):
    """Contrato: ok=False nunca é servido como pronto (nem com zeros silenciosos)."""
    client = _client_with(monkeypatch, ok=False)
    body = client.get("/api/metrics").json()
    assert not (body["status"] == "online" and body["graph_ready"] is False)
