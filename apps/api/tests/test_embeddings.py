"""Testes do embedding local determinístico (feature hashing)."""
from __future__ import annotations

import math

from src.cognition.embeddings import hash_embedding


def _cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def test_dimension_and_unit_norm():
    vector = hash_embedding("Inteligência Artificial utiliza Redes Neurais", 384)
    assert len(vector) == 384
    assert abs(math.sqrt(sum(v * v for v in vector)) - 1.0) < 1e-6


def test_deterministic():
    assert hash_embedding("mesmo texto", 64) == hash_embedding("mesmo texto", 64)


def test_similar_texts_are_closer_than_unrelated():
    query = hash_embedding("redes neurais artificiais", 256)
    related = hash_embedding("redes neurais artificiais profundas", 256)
    unrelated = hash_embedding("receita de bolo de chocolate", 256)
    assert _cosine(query, related) > _cosine(query, unrelated)


def test_empty_text_returns_zero_vector():
    assert hash_embedding("", 16) == [0.0] * 16
