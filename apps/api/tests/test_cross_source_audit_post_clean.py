"""Testes da auditoria pós-limpeza (#051) — puros, sem Neo4j."""
from src.cognition.cross_source_audit import (
    audit,
    domain_coverage,
    reconcile_pipeline,
)


def test_domain_coverage_counts_by_host():
    facts = [
        {"subject": "A", "predicate": "UTILIZA", "object": "B", "domains": ["pt.wikipedia.org"]},
        {"subject": "C", "predicate": "UTILIZA", "object": "D", "domains": ["pt.wikipedia.org"]},
        {"subject": "E", "predicate": "UTILIZA", "object": "F", "domains": ["a.com", "b.com"]},
        {"subject": "G", "predicate": "UTILIZA", "object": "H", "domains": []},
    ]
    cov = domain_coverage(facts)
    assert cov["facts_total"] == 4
    assert cov["facts_with_one_domain"] == 2
    assert cov["facts_with_two_or_more_domains"] == 1
    assert cov["facts_by_domain"]["pt.wikipedia.org"] == 2
    assert cov["domains_total"] == 3


def test_reconcile_pipeline_explains_gap():
    rec = reconcile_pipeline(
        raw_triples=209, canonical_triples=78, rejected_noise=130,
        persisted_facts=66, same_domain_multi_url_merge=12,
    )
    assert rec["canonical_to_fact_gap"] == 12
    assert rec["unaccounted_raw"] == 1
    assert rec["gap_explanations"]["same_domain_multi_url_merge"] == 12


def test_audit_exposes_aliasing_alias_of_linking():
    report = audit([
        {"subject": "Santos FC", "predicate": "POSSUIR", "object": "Estadio Urbano Caldeira", "domains": ["a.com"]},
        {"subject": "FC Santos", "predicate": "POSSUIR", "object": "Estadio Urbano Caldeira", "domains": ["b.com"]},
    ], quorum=3)
    assert report["potential_verified_if_aliasing"] == report["potential_verified_if_linking"]
