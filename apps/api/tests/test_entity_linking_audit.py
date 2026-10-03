"""Testes do entity linking audit (#057) — puros, sem Neo4j, sem rede."""
from __future__ import annotations

import json

from src.cognition.entity_linking_audit import (
    FORBIDDEN_MARKERS,
    alias_deterministic,
    assert_no_secret_markers,
    assert_read_only_cypher,
    build_report,
    classify_link_candidate,
    generate_candidate_pairs,
)

_DOMAIN_PT = "pt.wikipedia.org"
_DOMAIN_CLUB = "almanaquedosclubes.com"
_DOMAIN_OFFICIAL = "santosfc.com.br"


def _fact(fact_hash, subject, predicate, obj, domains):
    return {
        "fact_hash": fact_hash,
        "subject": subject,
        "predicate": predicate,
        "object": obj,
        "domains": list(domains),
    }


def test_case1_subject_variant_high():
    left = _fact("h1", "Santos FC", "POSSUIR", "Estádio Urbano Caldeira", [_DOMAIN_PT])
    right = _fact("h2", "Santos Futebol Clube", "POSSUIR", "Estádio Urbano Caldeira", [_DOMAIN_CLUB])
    assert classify_link_candidate(left, right) == ("high", "subject_variant")
    report = build_report([left, right])
    assert report["candidate_pairs"]["high"] == 1
    assert report["examples"][0]["type"] == "subject_variant"
    assert report["examples"][0]["promote_automatically"] is False
    assert report["mismatch_types"]["subject_variant"] == 2


def test_case2_object_variant_medium_not_high():
    left = _fact("h1", "Santos FC", "POSSUIR", "Estádio Urbano Caldeira", [_DOMAIN_PT])
    right = _fact("h3", "Santos FC", "POSSUIR", "Vila Belmiro", [_DOMAIN_OFFICIAL])
    assert classify_link_candidate(left, right) == ("medium", "object_variant")
    report = build_report([left, right])
    assert report["candidate_pairs"]["high"] == 0
    assert report["candidate_pairs"]["medium"] == 1
    assert report["potential_verified_if_high_aliasing"] == 0


def test_case3_same_domain_is_not_candidate():
    left = _fact("h1", "Santos FC", "POSSUIR", "Vila Belmiro", ["a.com"])
    right = _fact("h2", "Santos FC", "POSSUIR", "Vila Belmiro Novo", ["a.com"])
    assert classify_link_candidate(left, right) is None
    report = build_report([left, right])
    assert report["candidate_pairs"] == {"high": 0, "medium": 0, "low": 0}
    assert report["mismatch_types"]["true_unique"] == 2


def test_case4_different_predicate_never_high():
    left = _fact("h1", "Pelé", "DEFENDEU", "Santos FC", [_DOMAIN_PT])
    right = _fact("h2", "Pelé", "JOGOU_POR", "Santos FC", [_DOMAIN_CLUB])
    confidence, mismatch = classify_link_candidate(left, right)
    assert confidence in {"medium", "low"}
    assert confidence != "high"
    assert mismatch == "predicate_variant"
    report = build_report([left, right])
    assert report["candidate_pairs"]["high"] == 0


def test_case5_report_has_no_secrets():
    facts = [
        _fact("h1", "Santos FC", "POSSUIR", "Estádio Urbano Caldeira", [_DOMAIN_PT]),
        _fact("h2", "Santos Futebol Clube", "POSSUIR", "Estádio Urbano Caldeira", [_DOMAIN_CLUB]),
    ]
    report = build_report(facts)
    text = json.dumps(report, ensure_ascii=False)
    assert assert_no_secret_markers(text, FORBIDDEN_MARKERS) == []


def test_alias_requires_expansion_and_shared_core():
    assert alias_deterministic("Santos FC", "Santos Futebol Clube") is True
    assert alias_deterministic("Botafogo de Regatas", "Botafogo Clube de Regatas") is False
    assert alias_deterministic("Fortaleza EC", "Esporte Clube Bahia") is False
    assert alias_deterministic("", "qualquer") is False


def test_empty_domains_and_same_fact_hash_are_ineligible():
    left = _fact("h1", "Santos FC", "POSSUIR", "Vila Belmiro", [])
    right = _fact("h2", "Santos FC", "POSSUIR", "Vila Belmiro", [_DOMAIN_PT])
    assert classify_link_candidate(left, right) is None

    same_hash_a = _fact("hX", "Santos FC", "POSSUIR", "Vila Belmiro", [_DOMAIN_PT])
    same_hash_b = _fact("hX", "Santos FC", "POSSUIR", "Vila Belmiro", [_DOMAIN_CLUB])
    assert classify_link_candidate(same_hash_a, same_hash_b) is None


def test_pairs_are_deterministic_and_capped():
    facts = [
        _fact("h2", "Santos FC", "POSSUIR", "Vila Belmiro", [_DOMAIN_OFFICIAL]),
        _fact("h1", "Santos FC", "POSSUIR", "Estádio Urbano Caldeira", [_DOMAIN_PT]),
        _fact("h3", "Santos Futebol Clube", "POSSUIR", "Estádio Urbano Caldeira", [_DOMAIN_CLUB]),
        _fact("h4", "Pelé", "DEFENDEU", "Santos FC", ["ge.globo.com"]),
    ]
    kwargs = dict(audit_id="fixed", generated_at="2026-09-22T00:00:00+00:00",
                  build_space_commit="c0ad9e0", worker_run_id="w1")
    first = build_report(facts, **kwargs)
    second = build_report(list(reversed(facts)), **kwargs)
    assert first == second

    capped = build_report(facts, max_examples=1, **kwargs)
    assert len(capped["examples"]) == 1
    assert capped["examples"][0]["confidence"] == "high"


def test_pairs_sorted_confidence_then_score_then_hash():
    facts = [
        _fact("zz", "Santos FC", "POSSUIR", "Vila Belmiro", [_DOMAIN_OFFICIAL]),
        _fact("aa", "Santos FC", "POSSUIR", "Estádio Urbano Caldeira", [_DOMAIN_PT]),
        _fact("mm", "Pelé", "DEFENDEU", "Santos FC", ["ge.globo.com"]),
    ]
    pairs = generate_candidate_pairs(facts)
    order = [p["confidence"] for p in pairs]
    assert order == sorted(order, key=lambda c: {"high": 2, "medium": 1, "low": 0}[c], reverse=True)
    for pair in pairs:
        assert pair["left_fact_hash"] <= pair["right_fact_hash"]
        assert pair["promote_automatically"] is False


def test_inputs_are_not_mutated():
    facts = [_fact("h1", "Santos FC", "POSSUIR", "Vila Belmiro", [_DOMAIN_PT])]
    snapshot = json.dumps(facts, ensure_ascii=False, sort_keys=True)
    build_report(facts)
    assert json.dumps(facts, ensure_ascii=False, sort_keys=True) == snapshot


def test_report_structure_matches_dod():
    facts = [
        _fact("h1", "Santos FC", "POSSUIR", "Estádio Urbano Caldeira", [_DOMAIN_PT]),
        _fact("h2", "Santos Futebol Clube", "POSSUIR", "Estádio Urbano Caldeira", [_DOMAIN_CLUB]),
    ]
    report = build_report(facts, quorum=3, audit_id="a", generated_at="t",
                          build_space_commit="c", worker_run_id="w")
    assert set(report) >= {
        "audit_id", "generated_at", "build_space_commit", "worker_run_id", "quorum",
        "facts_total", "domains_total", "domain_coverage", "candidate_pairs",
        "potential_verified_if_high_aliasing", "potential_verified_if_medium_aliasing",
        "mismatch_types", "examples", "parameters", "truthfulness_note",
    }
    assert set(report["candidate_pairs"]) == {"high", "medium", "low"}
    assert set(report["mismatch_types"]) == {
        "subject_variant", "object_variant", "predicate_variant", "true_unique",
    }
    assert report["promote_automatically"] is False
    assert report["truthfulness_note"]["medium_is_upper_bound"] is True
    assert report["truthfulness_note"]["only_high_is_recommended_for_curated_alias_review"] is True
    assert report["parameters"]["qdrant_used"] is False
    assert report["domain_coverage"]["facts_by_domain"][_DOMAIN_PT] == 1


def test_read_only_cypher_guard():
    assert_read_only_cypher("MATCH (f:Fato) RETURN f")
    assert_read_only_cypher("OPTIONAL MATCH (ff:FonteWeb)-[:CONFIRMA]->(f) RETURN ff")
    for forbidden in (
        "MERGE (f:Fato) SET f.x = 1",
        "CREATE (f:Fato)",
        "DELETE f",
        "LOAD CSV FROM 'x' AS row",
    ):
        try:
            assert_read_only_cypher(forbidden)
        except ValueError:
            continue
        raise AssertionError(f"deveria bloquear: {forbidden}")


def test_quorum_components_need_three_domains():
    facts = [
        _fact("h1", "Santos FC", "POSSUIR", "Estádio Urbano Caldeira", [_DOMAIN_PT]),
        _fact("h2", "Santos Futebol Clube", "POSSUIR", "Estádio Urbano Caldeira", [_DOMAIN_CLUB]),
    ]
    report = build_report(facts, quorum=3)
    assert report["potential_verified_if_high_aliasing"] == 0

    third = _fact("h3", "Santos FC", "POSSUIR", "Estádio Urbano Caldeira", ["ge.globo.com"])
    report_three = build_report(facts + [third], quorum=3)
    assert report_three["potential_verified_if_high_aliasing"] == 1
