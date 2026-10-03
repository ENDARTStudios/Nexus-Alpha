"""Testes do TriangulationFilter."""
from __future__ import annotations

from src.security.triangulation import TriangulationFilter


def test_verified_when_three_distinct_domains():
    f = TriangulationFilter(min_sources=3, threshold=0.6)
    fact = {
        "subject": "Grafeno", "predicate": "CONDUZ", "object": "Eletricidade",
        "confidence": 0.9, "source_url": "https://a.com",
    }
    history = [
        {"source_url": "https://b.edu", "confidence": 0.85},
        {"source_url": "https://c.org", "confidence": 0.7},
    ]
    decision = f.process_discovered_triplets(fact, history)
    assert decision["status"] == "VERIFIED_FACT"
    assert decision["action"] == "INSERT_INTO_GRAPH"


def test_quarantine_when_too_few_domains():
    f = TriangulationFilter(min_sources=3, threshold=0.6)
    fact = {"confidence": 0.9, "source_url": "https://a.com", "subject": "X", "predicate": "Y", "object": "Z"}
    decision = f.process_discovered_triplets(fact, [{"source_url": "https://a.com", "confidence": 0.9}])
    assert decision["status"] == "QUARANTINE"


def test_domain_normalization_strips_www():
    f = TriangulationFilter(min_sources=2, threshold=0.5)
    fact = {"confidence": 0.7, "source_url": "https://www.a.com/x", "subject": "X", "predicate": "Y", "object": "Z"}
    history = [{"source_url": "https://b.com/y", "confidence": 0.7}]
    decision = f.process_discovered_triplets(fact, history)
    assert decision["status"] == "VERIFIED_FACT"