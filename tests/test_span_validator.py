"""Testes do validador determinístico de span de entidade (#050) — puros."""
from __future__ import annotations

import sys

from src.cognition.span_validator import (
    reject_reason_for_span,
    validate_entity_span,
)
from src.cognition.triple_refiner import refine_triple_ex


def test_rejects_fragment_objects_from_production():
    assert validate_entity_span("EM 1959", "object") == (False, "object_date_like")
    assert validate_entity_span("EM 2015", "object") == (False, "object_date_like")
    assert validate_entity_span("1959", "object") == (False, "object_numeric_only")
    assert validate_entity_span("COM ISSO", "object") == (False, "object_prepositional_phrase")
    assert validate_entity_span("COMO OBJETIVO", "object") == (False, "object_prepositional_phrase")
    assert validate_entity_span("APOS A PUBLICACAO EM 1986", "object") == (False, "object_adverbial_phrase")
    assert validate_entity_span("DE APRENDIZADO PROFUNDO", "object") == (False, "object_prepositional_phrase")
    assert validate_entity_span("isso", "object") == (False, "object_pronoun")


def test_rejects_quantifier_subject():
    assert validate_entity_span("MAIORIA ALGORITMOS DE APRENDIZADO NAO", "subject") == (
        False, "subject_quantifier_phrase"
    )
    assert validate_entity_span("ALGUNS MODELOS", "subject") == (False, "subject_quantifier_phrase")


def test_rejects_stopword_and_too_long():
    assert validate_entity_span("EM 1959", "subject") == (False, "subject_generic_phrase")
    assert validate_entity_span("DE REDES NEURAIS", "subject") == (False, "subject_starts_with_stopword")
    long_object = "um dois tres quatro cinco seis sete oito nove"
    assert validate_entity_span(long_object, "object") == (False, "object_too_long")


def test_accepts_legitimate_entities():
    assert validate_entity_span("Inteligência Artificial", "subject") == (True, None)
    assert validate_entity_span("Processamento de linguagem natural", "object") == (True, None)
    assert validate_entity_span("Santos FC", "subject") == (True, None)
    assert validate_entity_span("Estádio Urbano Caldeira", "object") == (True, None)
    assert validate_entity_span("Aprendizado por Reforço", "object") == (True, None)
    assert validate_entity_span("Alan Turing", "subject") == (True, None)


def test_known_entities_whitelist_overrides_rules():
    known = {"em 1959"}
    assert validate_entity_span("EM 1959", "object") == (False, "object_date_like")
    assert validate_entity_span("EM 1959", "object", known) == (True, None)


def test_reject_reason_helper():
    assert reject_reason_for_span("EM 1959", "object") == "object_date_like"
    assert reject_reason_for_span("Santos FC", "subject") is None


def test_refiner_integration_rejects_fragment_spans():
    assert refine_triple_ex(
        {"subject": "IA", "predicate": "DEFINE", "object": "EM 1959"}
    ) == (None, "object_date_like")
    _, reason = refine_triple_ex(
        {"subject": "MAIORIA ALGORITMOS DE APRENDIZADO NAO", "predicate": "POSSUIR", "object": "ALGO"}
    )
    assert reason == "subject_quantifier_phrase"


def test_validator_does_not_import_heavy_training_stack():
    assert "torch" not in sys.modules
    assert "llamafactory" not in sys.modules
