"""#048.10G — testes do preflight de telemetria do Space (mock, sem rede)."""
from __future__ import annotations

from scripts.check_space_telemetry import check_space_telemetry


def _good_payload() -> dict:
    return {
        "concept_count": 1894,
        "fact_count": 335,
        "ingestion_accounting": {"run_scoped_gap": 0, "graph_scoped_gap": -21},
        "verification": {"quorum": 3},
        "fallback_health": {"fallback_promoted_to_graph": 0},
        "extraction_quality": {"top_invalid_predicates": []},
    }


def test_ok_when_all_fields_present():
    result = check_space_telemetry(_good_payload())
    assert result["ok"] is True
    assert result["classification"] == "OK"


def test_blocked_when_stale_missing_fields():
    stale = {"facts": 1894, "ingestion_accounting": {"persisted_facts": 335}}
    result = check_space_telemetry(stale)
    assert result["ok"] is False
    assert result["classification"] == "BLOCKED_SPACE_STALE_TELEMETRY"
    assert "concept_count" in result["missing"]
    assert "ingestion_accounting.run_scoped_gap" in result["missing"]


def test_blocked_on_quorum_change():
    payload = _good_payload()
    payload["verification"]["quorum"] = 2
    result = check_space_telemetry(payload)
    assert result["ok"] is False
    assert "verification.quorum!=3" in result["missing"]


def test_blocked_on_fallback_promoted():
    payload = _good_payload()
    payload["fallback_health"]["fallback_promoted_to_graph"] = 1
    assert check_space_telemetry(payload)["ok"] is False


def test_blocked_on_invalid_predicates():
    payload = _good_payload()
    payload["extraction_quality"]["top_invalid_predicates"] = [{"predicate": "X"}]
    assert check_space_telemetry(payload)["ok"] is False


def test_blocked_on_non_dict():
    assert check_space_telemetry("nope")["classification"] == "BLOCKED_SPACE_STALE_TELEMETRY"
