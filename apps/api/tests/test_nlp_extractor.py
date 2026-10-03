"""Testes do NLPExtractor em modo fallback (sem transformers)."""
from __future__ import annotations

from src.cognition.nlp_extractor import NLPExtractor


def test_fallback_extracts_predicates():
    extractor = NLPExtractor()
    text = "Inteligência Artificial utiliza Redes Neurais e processa grandes volumes de dados."
    triples = extractor.extract_triplets(text, "Inteligência Artificial")
    assert triples
    predicates = {t["predicate"] for t in triples}
    assert "UTILIZA" in predicates or "PROCESSA" in predicates


def test_returns_empty_for_invalid_input():
    extractor = NLPExtractor()
    assert extractor.extract_triplets("", "X") == []
    assert extractor.extract_triplets("texto sem entidade", "") == []