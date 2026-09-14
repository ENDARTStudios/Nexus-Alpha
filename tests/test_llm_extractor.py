"""Testes do extrator canônico baseado em LLM (schema controlado)."""
from __future__ import annotations

import json

from src.cognition.llm_extractor import LLMCanonicalExtractor


def test_llm_extractor_canonical_schema(monkeypatch):
    extractor = LLMCanonicalExtractor()
    mock_llm_output = json.dumps({
        "triplets": [
            {"subject": "ia generativa", "predicate": "UTILIZA", "object": "transformers", "confidence": 0.95},
            {"subject": "deep learning", "predicate": "INVALID_VERB", "object": "dados", "confidence": 0.50},
        ]
    })
    monkeypatch.setattr(
        "src.cognition.llm_extractor.generate_text",
        lambda system_prompt, user_prompt: mock_llm_output,
    )

    results = extractor.extract_canonical_triplets("Texto qualquer de entrada para o processamento.")

    assert len(results) == 1
    assert results[0]["subject"] == "Ia Generativa"
    assert results[0]["predicate"] == "UTILIZA"
    assert results[0]["object"] == "Transformers"


def test_llm_extractor_empty_fallback(monkeypatch):
    extractor = LLMCanonicalExtractor()
    monkeypatch.setattr(
        "src.cognition.llm_extractor.generate_text",
        lambda system_prompt, user_prompt: "Resposta corrompida fora do json",
    )
    results = extractor.extract_canonical_triplets("Texto de entrada suficientemente longo para o processamento.")
    assert results == []


def test_llm_extractor_without_llm_returns_empty(monkeypatch):
    extractor = LLMCanonicalExtractor()
    monkeypatch.setattr(
        "src.cognition.llm_extractor.generate_text",
        lambda system_prompt, user_prompt: "",
    )
    assert extractor.extract_canonical_triplets("Texto longo o suficiente para passar o guard.") == []


def test_llm_extractor_parses_markdown_fenced_json(monkeypatch):
    extractor = LLMCanonicalExtractor()
    fenced = '```json\n{"triplets": [{"subject": "redes neurais", "predicate": "PRODUZ", "object": "predicoes", "confidence": 0.8}]}\n```'
    monkeypatch.setattr(
        "src.cognition.llm_extractor.generate_text",
        lambda system_prompt, user_prompt: fenced,
    )
    results = extractor.extract_canonical_triplets("Texto longo o suficiente para o extrator processar.")
    assert len(results) == 1
    assert results[0]["predicate"] == "PRODUZ"


def test_clean_json_strips_surrounding_prose():
    raw = 'Claro! Aqui está o resultado: {"triplets": [{"subject": "a", "predicate": "UTILIZA", "object": "b"}]} Fim.'
    cleaned = LLMCanonicalExtractor._clean_json(raw)
    assert cleaned.startswith("{") and cleaned.endswith("}")
    assert '"triplets"' in cleaned
