"""Testes do canonicalizador semântico (colisão de entidades e predicados)."""
from __future__ import annotations

from src.cognition.canonicalizer import SemanticCanonicalizer


def test_triplet_canonicalization_logic():
    canonicalizer = SemanticCanonicalizer()
    raw = {"subject": "ia", "predicate": "utiliza", "object": "ml"}
    result = canonicalizer.canonicalize_triplet(raw)
    assert result["subject"] == "Inteligência Artificial"
    assert result["predicate"] == "UTILIZA"
    assert result["object"] == "Machine Learning"


def test_fallback_unknown_terms():
    canonicalizer = SemanticCanonicalizer()
    raw = {"subject": "algoritmo quântico", "predicate": "acelera", "object": "processamento"}
    result = canonicalizer.canonicalize_triplet(raw)
    assert result["subject"] == "Algoritmo Quântico"
    assert result["predicate"] == "ACELERA"


def test_acronyms_collide_with_full_names():
    canonicalizer = SemanticCanonicalizer()
    a = canonicalizer.canonicalize_triplet({"subject": "AI", "predicate": "usa", "object": "redes neurais"})
    b = canonicalizer.canonicalize_triplet(
        {"subject": "Inteligência Artificial", "predicate": "emprega", "object": "Redes Neurais"}
    )
    assert a["subject"] == b["subject"]
    assert a["predicate"] == b["predicate"]
    assert a["object"] == b["object"]
