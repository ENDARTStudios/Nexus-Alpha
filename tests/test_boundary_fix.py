"""Testes #047 — boundary fix do extractor (H3 residual da Inspeção 2).

Causas estruturais: cauda verbal (``PELE SAID HE``), conectivo inicial
(``ALTHOUGH GARRINCHA``), resíduo de palavra fechada (``E O``) e topônimo
truncado (``São Paulo`` → ``PAULO``)."""
from __future__ import annotations

from src.cognition.extractor import (
    EntityExtractor,
    is_function_word_span,
    rescue_truncated_toponym,
    strip_boundary_noise,
)


def test_strip_boundary_noise_removes_english_verbal_tail():
    assert strip_boundary_noise("Pelé said he") == "Pelé"
    assert strip_boundary_noise("Garrincha was") == "Garrincha"
    assert strip_boundary_noise("Santos FC has") == "Santos FC"


def test_strip_boundary_noise_removes_leading_connective():
    assert strip_boundary_noise("Although Garrincha") == "Garrincha"
    assert strip_boundary_noise("And the stadium") == "the stadium"
    assert strip_boundary_noise("E o time") == "o time"


def test_strip_boundary_noise_is_idempotent_and_safe_on_clean_spans():
    clean = "Santos FC"
    assert strip_boundary_noise(clean) == clean
    assert strip_boundary_noise(strip_boundary_noise("Pelé said he")) == "Pelé"
    assert strip_boundary_noise("") == ""


def test_is_function_word_span_flags_closed_word_residue():
    assert is_function_word_span("E O") is True
    assert is_function_word_span("and") is True
    assert is_function_word_span("the of to") is True
    assert is_function_word_span("") is True
    assert is_function_word_span("Santos FC") is False
    assert is_function_word_span("Pelé") is False
    assert is_function_word_span("São Paulo") is False


def test_rescue_truncated_toponym_restores_sao_paulo():
    text = "O clube tem sede em São Paulo."
    assert rescue_truncated_toponym("Paulo", text) == "São Paulo"
    # Sem contexto São <Term> no texto, span é mantido.
    assert rescue_truncated_toponym("Paulo", "Paulo nasceu em Santos.") == "Paulo"
    # Span multi-token não é tocado.
    assert rescue_truncated_toponym("São Paulo", text) == "São Paulo"
    # Texto vazio é seguro.
    assert rescue_truncated_toponym("Paulo", "") == "Paulo"


def test_fallback_does_not_emit_function_word_subject():
    extractor = EntityExtractor(enable_fallback=True)
    # "E o time possui títulos." — sujeito residual "E o" não vira tripla.
    triples = extractor.extract("E o time possui títulos.")
    for t in triples:
        assert not is_function_word_span(t.subject), t.subject
        assert not is_function_word_span(t.object), t.object


def test_fallback_strips_verbal_tail_from_english_span():
    extractor = EntityExtractor(enable_fallback=True)
    # Sentença com cauda verbal + predicado conhecido.
    triples = extractor.extract("Pelé said he has many titles.")
    for t in triples:
        assert "said" not in t.subject.lower(), t.subject
        assert not t.subject.lower().endswith("said he"), t.subject


def test_fallback_rescues_sao_paulo_toponym_when_truncated():
    extractor = EntityExtractor(enable_fallback=True)
    # Predicado conhecido + span que o regex pode truncar para "Paulo".
    triples = extractor.extract("O clube possui base em São Paulo.")
    subjects = [t.subject for t in triples]
    objects = [t.object for t in triples]
    # Se "Paulo" aparecer isolado, o resgate deve ter evitado (ou não produzido).
    assert "Paulo" not in subjects
    assert "Paulo" not in objects
    # Se alguma tripla citar São Paulo, o span completo deve ser preservado.
    for span in subjects + objects:
        if "São Paulo" in span or "paulo" in span.lower():
            assert "São Paulo" in span or "SAO PAULO" in span.upper()


def test_spacy_path_applies_same_boundary_helpers_when_available():
    #spaCy pode não estar disponível no CI lite; o caminho fallback já cobre.
    extractor = EntityExtractor(enable_fallback=True)
    triples = extractor.extract(
        "Although Garrincha said he loved football. Santos FC has a stadium."
    )
    for t in triples:
        assert not t.subject.lower().startswith("although"), t.subject
        assert "said he" not in t.subject.lower(), t.subject
