"""#048.10M — testes offline do planejador read-only de expansão não-VENCEU."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.plan_non_venceu_expansion_048_10m import (  # noqa: E402
    DEFENDEU_CANDIDATE_SEEDS,
    aggregate_verified,
    build_defendeu_candidates,
)


def _fact(subject, predicate, obj, domains):
    return {"subject": subject, "predicate": predicate, "object": obj, "domains": domains, "confirmacoes": len(domains)}


def test_aggregate_verified_counts_and_ratios():
    rows = [
        _fact("A", "VENCEU", "COPA", ["rsssf.org", "pt.wikipedia.org", "en.wikipedia.org"]),
        _fact("B", "VENCEU", "COPA", ["rsssf.org", "pt.wikipedia.org", "en.wikipedia.org"]),
        _fact("C", "LOCALIZADO_EM", "SAO PAULO", ["nominatim.openstreetmap.org", "pt.wikipedia.org", "en.wikipedia.org"]),
        _fact("D", "DEFENDEU", "SANTOS FUTEBOL CLUBE", ["pt.wikipedia.org", "en.wikipedia.org", "rsssf.org"]),
    ]
    agg = aggregate_verified(rows)
    assert agg["total_verified_facts"] == 4
    assert agg["facts_by_predicate"]["VENCEU"] == 2
    assert agg["facts_by_predicate"]["LOCALIZADO_EM"] == 1
    assert agg["non_venceu_facts"] == 2
    assert agg["non_VENCEU_ratio"] == 0.5
    assert agg["top_predicate_share"] == 0.5
    assert agg["facts_by_publisher_family"]["Wikimedia"] >= 1


def test_defendeu_candidates_are_unverified_and_not_eligible():
    candidates = build_defendeu_candidates([], set())
    assert len(candidates) >= 6
    for c in candidates:
        assert c["predicate"] == "DEFENDEU"
        assert c["evidence_status"] == "candidate_unverified"
        assert c["eligible_for_future_worker"] is False
        assert c["requires_ontology_change"] is False
        assert c["source_policy"] == "allowed"
        assert set(c["required_domains"]) == {"pt.wikipedia.org", "en.wikipedia.org", "rsssf.org"}


def test_defendeu_seeds_are_person_to_club_shape():
    for seed in DEFENDEU_CANDIDATE_SEEDS:
        assert seed["subject"] and seed["object"]
        assert seed["risk_level"] in {"low", "medium", "high"}
        assert seed["risks"], seed["subject"]


def test_plan_module_is_import_safe_without_network():
    # Import e execução das funções puras não exigem rede/DB.
    agg = aggregate_verified([])
    assert agg["total_verified_facts"] == 0
