"""#048.10G/#048.10H.1 — testes do preflight de telemetria do Space (puro, sem rede)."""
from __future__ import annotations

from src.ops.space_telemetry import evaluate_payload


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


def test_ok_when_all_fields_present():
    result = evaluate_payload(_good_payload())
    assert result.ok is True
    assert result.reason is None
    assert result.missing_fields == []


def test_blocked_when_stale_missing_fields():
    stale = {"facts": 1894, "ingestion_accounting": {"persisted_facts": 335}}
    result = evaluate_payload(stale)
    assert result.ok is False
    assert result.reason == "BLOCKED_SPACE_STALE_TELEMETRY"
    assert "concept_count" in result.missing_fields
    assert "ingestion_accounting.run_scoped_gap" in result.missing_fields


def test_blocked_on_quorum_change():
    payload = _good_payload()
    payload["verification"]["quorum"] = 2
    result = evaluate_payload(payload)
    assert result.ok is False
    assert result.reason == "BLOCKED_QUORUM_MISMATCH"


def test_blocked_on_fallback_promoted():
    payload = _good_payload()
    payload["fallback_health"]["fallback_promoted_to_graph"] = 1
    assert evaluate_payload(payload).reason == "BLOCKED_FALLBACK_PROMOTED"


def test_blocked_on_invalid_predicates():
    payload = _good_payload()
    payload["extraction_quality"]["top_invalid_predicates"] = [{"predicate": "X"}]
    assert evaluate_payload(payload).reason == "BLOCKED_INVALID_PREDICATES"


def test_blocked_on_unaccounted_raw():
    payload = _good_payload()
    payload["ingestion_accounting"]["unaccounted_raw"] = 3
    assert evaluate_payload(payload).reason == "BLOCKED_UNACCOUNTED_RAW"


def test_blocked_on_non_dict():
    assert evaluate_payload("nope").reason == "BLOCKED_SPACE_STALE_TELEMETRY"
