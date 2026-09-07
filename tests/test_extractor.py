"""Testes do extrator de entidades (modo fallback, sem dependência de modelo spaCy)."""
from __future__ import annotations

from src.cognition.extractor import EntityExtractor, Triple


def test_extractor_fallback_produces_triples():
    extractor = EntityExtractor(enable_fallback=True)
    text = (
        "Inteligência Artificial utiliza Redes Neurais. "
        "Redes Neurais processam grandes volumes de dados."
    )
    triples = extractor.extract(text)
    assert triples, "fallback deveria produzir ao menos uma tripleta"
    assert all(isinstance(t, Triple) for t in triples)
    assert {t.subject for t in triples} & {"Inteligência Artificial", "Redes Neurais"}


def test_extractor_enrich_payload():
    extractor = EntityExtractor(enable_fallback=True)
    payload = {
        "source_url": "https://example.com",
        "timestamp": 0,
        "domain_score": 0.0,
        "metadata": {},
        "title": "IA",
        "content": "Inteligência Artificial utiliza Redes Neurais.",
        "extracted_entities": [],
    }
    enriched = extractor.enrich_payload(payload)
    assert "extracted_entities" in enriched
    assert isinstance(enriched["extracted_entities"], list)


def test_confidence_scoring_bounds():
    score = EntityExtractor._confidence_for("IA", "Redes Neurais", "UTILIZA")
    assert 0.0 < score <= 0.99
    assert EntityExtractor._confidence_for("", "", "") == 0.0