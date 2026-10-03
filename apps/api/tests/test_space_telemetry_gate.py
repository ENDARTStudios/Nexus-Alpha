"""#048.10H.1 — testes do gate duro de telemetria (env/mocks, sem rede)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.ops.space_telemetry import (  # noqa: E402
    check_space_telemetry,
    evaluate_payload,
)
import scripts.worker_cycle as worker  # noqa: E402


def _good_payload() -> dict:
    return {
        "status": "online",
        "concept_count": 1894,
        "fact_count": 335,
        "ingestion_accounting": {"run_scoped_gap": 0, "graph_scoped_gap": -21, "unaccounted_raw": 0},
        "verification": {"quorum": 3},
        "fallback_health": {"fallback_promoted_to_graph": 0},
        "extraction_quality": {"top_invalid_predicates": []},
    }


# --- gate duro: worker não abre a porta -------------------------------------


def test_worker_gate_raises_when_blocked():
    result = evaluate_payload({"facts": 1894})
    with pytest.raises(worker.TelemetryBlocked):
        worker._enforce_telemetry_gate(result)


def test_worker_gate_passes_when_ok():
    worker._enforce_telemetry_gate(evaluate_payload(_good_payload()))  # não levanta


def test_worker_calls_gate_before_miner_or_rag():
    source = (ROOT / "scripts" / "worker_cycle.py").read_text(encoding="utf-8")
    gate_pos = source.index("_enforce_telemetry_gate(_telemetry_gate")
    assert gate_pos < source.index("ReasoningEngine()")
    assert gate_pos < source.index("WebMiner()")
    assert gate_pos < source.index("rag.fetch_and_verify(")
    assert gate_pos < source.index("/api/ingest")


# --- preflight: credenciais / url / offline ---------------------------------


def test_check_space_telemetry_missing_url(monkeypatch):
    monkeypatch.delenv("HF_SPACE_URL", raising=False)
    monkeypatch.delenv("NEXUS_SPACE_URL", raising=False)
    monkeypatch.delenv("NEXUS_ALLOW_UNVERIFIED_LOCAL", raising=False)
    result = check_space_telemetry(space_url="")
    assert result.ok is False
    assert result.reason == "MISSING_SPACE_URL"


def test_check_space_telemetry_missing_credentials(monkeypatch):
    monkeypatch.delenv("NEXUS_ALLOW_UNVERIFIED_LOCAL", raising=False)
    result = check_space_telemetry(space_url="https://example.hf.space", hf_token="", nexus_token="")
    assert result.ok is False
    assert result.reason == "MISSING_SPACE_CREDENTIALS"


def test_check_space_telemetry_offline_flag():
    result = check_space_telemetry(allow_unverified_local=True)
    assert result.ok is True
    assert result.reason == "ALLOW_UNVERIFIED_LOCAL"


def test_check_space_telemetry_offline_env(monkeypatch):
    monkeypatch.setenv("NEXUS_ALLOW_UNVERIFIED_LOCAL", "true")
    result = check_space_telemetry(space_url="https://example.hf.space", hf_token="x", nexus_token="y")
    assert result.ok is True
    assert result.reason == "ALLOW_UNVERIFIED_LOCAL"
