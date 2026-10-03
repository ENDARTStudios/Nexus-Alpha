"""Testes do resolvedor vetorial de entidades (clustering semântico)."""
from __future__ import annotations

from src.cognition.entity_resolver import EntityResolver


def test_entity_resolution_clustering(monkeypatch):
    resolver = EntityResolver(similarity_threshold=0.85)
    monkeypatch.setattr(
        "src.cognition.entity_resolver.get_embedding",
        lambda text, dim=384: [0.9, 0.1, 0.0]
        if ("IA" in text or "GenAI" in text)
        else [0.0, 0.0, 1.0],
    )
    monkeypatch.setattr("src.cognition.entity_resolver.cosine_similarity", lambda a, b: 0.92)

    term_1 = resolver.resolve_entity("IA Generativa")
    term_2 = resolver.resolve_entity("IA Generativa (GenAI)")
    assert term_1 == "IA Generativa"
    assert term_2 == "IA Generativa"


def test_entity_resolution_separation(monkeypatch):
    resolver = EntityResolver(similarity_threshold=0.85)
    monkeypatch.setattr(
        "src.cognition.entity_resolver.get_embedding", lambda text, dim=384: [0.1, 0.2]
    )
    monkeypatch.setattr("src.cognition.entity_resolver.cosine_similarity", lambda a, b: 0.40)

    term_1 = resolver.resolve_entity("Inteligência Artificial")
    term_2 = resolver.resolve_entity("Computação Quântica")
    assert term_1 != term_2


def test_entity_resolution_near_duplicates_with_real_embedding():
    resolver = EntityResolver(similarity_threshold=0.80)
    canonical = resolver.resolve_entity("IA Generativa")
    assert resolver.resolve_entity("IA Generativa (GenAI)") == canonical


def test_resolve_triplet_returns_canonical_entities():
    resolver = EntityResolver(similarity_threshold=0.80)
    triplet = {
        "subject": "IA Generativa",
        "predicate": "USA",
        "object": "Redes Neurais",
        "confidence": 0.9,
    }
    out = resolver.resolve_triplet(dict(triplet))
    assert out["subject"] == "IA Generativa"
    assert out["predicate"] == "USA"
    assert out["object"] == "Redes Neurais"
