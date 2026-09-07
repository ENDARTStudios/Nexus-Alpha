"""Testes da memória local."""
from __future__ import annotations

from src.cognition.memory import LocalMemory


def test_add_relation_indexes_concepts():
    mem = LocalMemory()
    mem.add_relation("IA", "USA", "Redes Neurais", 0.9, "https://example.com")
    assert "IA" in mem.concepts
    assert "Redes Neurais" in mem.concepts
    assert mem.stats() == {"concepts": 2, "relations": 1}


def test_search_by_token_overlap():
    mem = LocalMemory()
    mem.add_relation("Inteligência Artificial", "USA", "Redes Neurais", 0.9, "u1")
    mem.add_relation("Blockchain", "USA", "Criptografia", 0.8, "u2")
    hits = mem.search("redes neurais artificiais")
    assert hits
    assert hits[0]["subject"] == "Inteligência Artificial"


def test_related_returns_incident_relations():
    mem = LocalMemory()
    mem.add_relation("IA", "USA", "Redes", 0.9, "u1")
    mem.add_relation("Redes", "PROCESSA", "Dados", 0.8, "u2")
    related = mem.related("IA")
    assert len(related) == 1
    related = mem.related("Redes")
    assert len(related) == 2