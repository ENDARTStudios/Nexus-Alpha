"""#048.10H.1 — testes do validador de fatos GEO esperados (offline, sem rede)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.validate_geo_expected_facts import main as validator_main  # noqa: E402
from scripts.validate_geo_expected_facts import (  # noqa: E402
    validate_geo_expected_facts,
    validate_multi_batch,
)

REGISTRY = ROOT / "reports" / "geo_expected_facts_048_10H.json"
NEXT_REGISTRY = ROOT / "reports" / "geo_expected_facts_next_batch_048_10k.json"
DOMAINS = ["pt.wikipedia.org", "en.wikipedia.org", "nominatim.openstreetmap.org"]


def _expected() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def _fact(subject: str, predicate: str = "LOCALIZADO_EM", obj: str = "SÃO PAULO", domains=None, verified=True) -> dict:
    return {"subject": subject, "predicate": predicate, "object": obj, "verified": verified, "domains": domains or list(DOMAINS)}


def _geo_report(facts: list[dict]) -> dict:
    return {"facts": facts}


def _post(**over) -> dict:
    payload = {
        "verification": {"verified_facts_domain_independent": 15, "quorum": 3},
        "extraction_quality": {"top_invalid_predicates": []},
        "fallback_health": {"fallback_promoted_to_graph": 0},
        "ingestion_accounting": {"unaccounted_raw": 0},
    }
    payload.update(over)
    return payload


ALL4 = [_fact("ALLIANZ PARQUE"), _fact("MORUMBI"), _fact("PACAEMBU"), _fact("NEO QUÍMICA ARENA")]


def test_all_four_verified():
    result = validate_geo_expected_facts(_expected(), _post(), _geo_report(ALL4))
    assert result["ok"] is True
    assert result["expected_facts_verified"] == 4
    assert result["classification"] == "SUCCESS_048_10H_GEO_VERIFIED"


def test_missing_fact():
    result = validate_geo_expected_facts(_expected(), _post(), _geo_report(ALL4[:3]))
    assert result["ok"] is False
    assert any("NEO QUÍMICA ARENA" in f for f in result["missing_facts"])


def test_partial_two_domains():
    partial = [_fact("ALLIANZ PARQUE", domains=DOMAINS[:2])] + ALL4[1:]
    result = validate_geo_expected_facts(_expected(), _post(), _geo_report(partial))
    assert result["ok"] is False
    assert any("ALLIANZ PARQUE" in f for f in result["partial_facts"])


def test_junk_object_detected():
    facts = ALL4 + [_fact("X", obj="BAIRRO DE PERDIZES", domains=DOMAINS)]
    result = validate_geo_expected_facts(_expected(), _post(), _geo_report(facts))
    assert result["junk_objects_detected"] >= 1
    assert result["ok"] is False


def test_forbidden_predicate_detected():
    facts = ALL4 + [_fact("X", predicate="SER", obj="ALGO")]
    result = validate_geo_expected_facts(_expected(), _post(), _geo_report(facts))
    assert result["forbidden_predicates_detected"] >= 1
    assert result["ok"] is False


def test_regression_existing_verified():
    baseline = {"verification": {"verified_facts_domain_independent": 11}}
    post = _post(verification={"verified_facts_domain_independent": 10, "quorum": 3})
    result = validate_geo_expected_facts(_expected(), post, _geo_report(ALL4), baseline)
    assert result["regression_existing_verified"] is True
    assert result["ok"] is False


def test_insufficient_evidence_without_fact_level():
    result = validate_geo_expected_facts(_expected(), _post(), {})
    assert result["classification"] == "PARTIAL_GEO_VALIDATION_INSUFFICIENT_EVIDENCE"
    assert result["ok"] is False


def test_cli_missing_reports(tmp_path):
    output = tmp_path / "out.json"
    code = validator_main(["--post", str(tmp_path / "nope.json"), "--expected", str(tmp_path / "nope2.json"), "--output", str(output)])
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["blocking_reason"] == "BLOCKED_MISSING_REPORTS"
    assert code == 1


def _next_expected() -> dict:
    return json.loads(NEXT_REGISTRY.read_text(encoding="utf-8"))


def test_multi_batch_current_ok_next_not_seeded():
    result = validate_multi_batch(_expected(), _next_expected(), _post(), _geo_report(ALL4))
    assert result["batches"]["current_048_10H"]["status"] == "OK"
    assert result["batches"]["next_048_10K"]["status"] == "FUTURE_BATCH_NOT_SEEDED"
    assert result["aggregate"]["ok"] is True


def test_multi_batch_current_pending_worker():
    result = validate_multi_batch(_expected(), _next_expected(), _post(), {})
    assert result["batches"]["current_048_10H"]["status"] == "PENDING_WORKER"
    assert result["aggregate"]["ok"] is False


def test_multi_batch_next_junk_detected():
    next_expected = _next_expected()
    next_facts = [_fact(f["subject"], obj=f["object"]) for f in next_expected["expected_facts"]]
    facts = ALL4 + next_facts + [_fact("X", obj="BAIRRO DE X")]
    result = validate_multi_batch(_expected(), next_expected, _post(), _geo_report(facts))
    assert result["batches"]["next_048_10K"]["status"] == "FAIL"
    assert result["aggregate"]["ok"] is False

