"""#058.11.2 (F1) — extração nominal/copular gateada.

Invariantes:
- frames EN/PT são determinísticos (regex no texto), sem depender do parse
  (o modelo PT sobre texto EN não gera ``cop``/``nsubj`` utilizáveis);
- só emite tripla com sujeito+objeto fortes (anti-inflação de ``SER`` e
  anti-objeto genérico); sujeito genérico só com predicado específico;
- os gates incrementam ``nominal_gate_reasons`` e **nunca**
  ``rejection_reasons`` (allowlist fixa em ``test_analyze_text``);
- com ``enable_nominal_copular=False`` o ``extract_spacy`` é idêntico ao
  pré-F1 (triplas verbais primeiro; o cap nunca empurra verbal para fora).
"""
from __future__ import annotations

import pytest

from src.cognition.extractor import EntityExtractor, is_propositional_sentence
from src.cognition.triple_refiner import refine_triple_ex

ACCEPTED = [
    (
        "Botafogo's home ground is the Estádio Olímpico Nilton Santos.",
        ("Botafogo", "POSSUIR", "Estádio Olímpico Nilton Santos"),
    ),
    (
        "The team's home ground is the Estádio Olímpico Nilton Santos.",
        ("team", "POSSUIR", "Estádio Olímpico Nilton Santos"),
    ),
    (
        "Botafogo is based in Rio de Janeiro.",
        ("Botafogo", "LOCALIZADO_EM", "Rio de Janeiro"),
    ),
    (
        "Pelé was a player for Santos FC.",
        ("Pelé", "DEFENDEU", "Santos FC"),
    ),
    (
        "Garrincha played for Botafogo for 12 years, the bulk of his professional career.",
        ("Garrincha", "DEFENDEU", "Botafogo"),
    ),
    (
        "Pelé began playing for the Brazilian club Santos at age 15, and for the "
        "Brazil national team at 16.",
        ("Pelé", "DEFENDEU", "Santos"),
    ),
    (
        "At club level, Garrincha played the majority of his professional career "
        "for the Brazilian team Botafogo.",
        ("Garrincha", "DEFENDEU", "Botafogo"),
    ),
    (
        "O Botafogo é sediado no Rio de Janeiro.",
        ("Botafogo", "LOCALIZADO_EM", "Rio de Janeiro"),
    ),
    (
        "Botafogo won the 2024 Copa Libertadores.",
        ("Botafogo", "VENCEU", "2024 Copa Libertadores"),
    ),
]

REJECTED = [
    "Botafogo is a Brazilian football club.",
    "Pelé was a professional footballer.",
    "The club plays in Serie A.",
    "Founded in 1904.",
    "History Formation and merger On 1 July 1894, the Club de Regatas Botafogo "
    "was founded in Rio de Janeiro as a rowing club.",
]


@pytest.fixture()
def extractor() -> EntityExtractor:
    return EntityExtractor(enable_fallback=False)


@pytest.mark.parametrize("text,expected", ACCEPTED)
def test_frames_emit_gated_nominal_triples(
    extractor: EntityExtractor, text: str, expected: tuple[str, str, str]
) -> None:
    triple, matched = extractor._nominal_from_frames(text, text)
    assert matched is True
    assert triple is not None, f"frame deveria emitir tripla: {text}"
    assert (triple.subject, triple.predicate, triple.object) == expected


@pytest.mark.parametrize("text", REJECTED)
def test_frames_reject_non_target_sentences(
    extractor: EntityExtractor, text: str
) -> None:
    triple, _ = extractor._nominal_from_frames(text, text)
    assert triple is None


def test_generic_object_is_rejected_by_gate(extractor: EntityExtractor) -> None:
    triple, matched = extractor._nominal_from_frames(
        "Pelé was a player for the Brazil national team.", "x"
    )
    assert matched is True
    assert triple is None
    assert extractor.nominal_gate_reasons["nominal_object_generic"] >= 1


def test_gates_never_touch_rejection_reasons(extractor: EntityExtractor) -> None:
    extractor._nominal_from_frames("Pelé was a player for the Brazil national team.", "x")
    extractor._build_nominal_triple("team", "Estádio X", "SER")
    extractor._build_nominal_triple("Botafogo", "clube brasileiro", "SER")
    assert dict(extractor.rejection_reasons) == {}
    assert dict(extractor.nominal_gate_reasons)


def test_generic_subject_allowed_only_for_specific_predicate(
    extractor: EntityExtractor,
) -> None:
    allowed = extractor._build_nominal_triple("team", "Estádio Olímpico", "POSSUIR")
    assert allowed is not None
    assert allowed.subject == "team"
    blocked = extractor._build_nominal_triple("team", "Estádio Olímpico", "SER")
    assert blocked is None
    assert extractor.nominal_gate_reasons["nominal_generic_subject_ser"] == 1


def test_weak_object_never_becomes_triple(extractor: EntityExtractor) -> None:
    assert extractor._build_nominal_triple("Botafogo", "Maracanã", "DEFENDEU") is None
    assert extractor.nominal_gate_reasons["nominal_object_weak"] == 1
    assert extractor._build_nominal_triple("Atlético", "Mineiro", "VENCEU") is None
    assert extractor.nominal_gate_reasons["nominal_object_weak"] == 2


def test_entity_strength_exact_known_and_alias_containment(extractor: EntityExtractor) -> None:
    assert extractor._entity_strength("Botafogo", "DEFENDEU") == "strong"
    assert extractor._entity_strength("santos futebol clube", "DEFENDEU") == "strong"
    assert extractor._entity_strength("the Brazilian club Santos", "DEFENDEU") == "strong"
    assert extractor._entity_strength("the Brazilian club Santos", "SER") != "strong"
    assert extractor._entity_strength("a Brazilian football club", "SER") == "generic"
    assert extractor._entity_strength("Santos", "SER") == "strong"


def test_nominal_term_ok_allows_four_token_stadium_object() -> None:
    assert EntityExtractor._nominal_term_ok("Estádio Olímpico Nilton Santos") is True
    assert EntityExtractor._nominal_term_ok("ab") is False
    assert EntityExtractor._nominal_term_ok("") is False
    assert EntityExtractor._nominal_term_ok("ele foi") is False


def test_flag_defaults_on_and_is_configurable() -> None:
    assert EntityExtractor().enable_nominal_copular is True
    assert EntityExtractor(enable_nominal_copular=False).enable_nominal_copular is False


def test_nominal_triple_refines_to_canonical_target_shape(extractor: EntityExtractor) -> None:
    triple, _ = extractor._nominal_from_frames(
        "Botafogo is based in Rio de Janeiro.", "Botafogo is based in Rio de Janeiro."
    )
    assert triple is not None
    refined, reason = refine_triple_ex(triple.to_dict())
    assert reason == "ok"
    assert refined is not None
    assert refined["subject"] == "BOTAFOGO DE FUTEBOL E REGATAS"
    assert refined["predicate"] == "LOCALIZADO_EM"
    assert refined["object"] == "RIO DE JANEIRO"


def test_defendeu_triple_refines_to_known_aliases(extractor: EntityExtractor) -> None:
    triple, _ = extractor._nominal_from_frames(
        "Pelé began playing for the Brazilian club Santos at age 15, and for the "
        "Brazil national team at 16.",
        "x",
    )
    assert triple is not None
    refined, reason = refine_triple_ex(triple.to_dict())
    assert reason == "ok"
    assert refined is not None
    assert refined["subject"] == "EDSON ARANTES DO NASCIMENTO"
    assert refined["predicate"] == "DEFENDEU"
    assert refined["object"] == "SANTOS FUTEBOL CLUBE"


# --- integração com spaCy (pula no ambiente sem modelo) ---------------------

@pytest.mark.parametrize("text,expected", ACCEPTED)
def test_extract_spacy_emits_nominal_triples_only_when_enabled(
    text: str, expected: tuple[str, str, str]
) -> None:
    on = EntityExtractor(enable_fallback=False, enable_nominal_copular=True)
    if on._nlp is None:
        pytest.skip("spaCy indisponível")
    off = EntityExtractor(enable_fallback=False, enable_nominal_copular=False)
    triples = on.extract_spacy(text, max_triples=50)
    assert expected in [(t.subject, t.predicate, t.object) for t in triples]
    off_triples = off.extract_spacy(text, max_triples=50)
    assert expected not in [(t.subject, t.predicate, t.object) for t in off_triples]


@pytest.mark.parametrize("text", REJECTED)
def test_extract_spacy_does_not_emit_for_rejected_sentences(text: str) -> None:
    extractor = EntityExtractor(enable_fallback=False, enable_nominal_copular=True)
    if extractor._nlp is None:
        pytest.skip("spaCy indisponível")
    assert extractor.extract_spacy(text, max_triples=50) == []


def test_possessive_sentence_split_is_glued_back() -> None:
    extractor = EntityExtractor(enable_fallback=False, enable_nominal_copular=True)
    if extractor._nlp is None:
        pytest.skip("spaCy indisponível")
    triples = extractor.extract_spacy(
        "Botafogo's home ground is the Estádio Olímpico Nilton Santos.", max_triples=50
    )
    assert any(t.predicate == "POSSUIR" and t.subject == "Botafogo" for t in triples)


def test_verbal_path_wins_and_nominal_does_not_duplicate() -> None:
    extractor = EntityExtractor(enable_fallback=False, enable_nominal_copular=True)
    if extractor._nlp is None:
        pytest.skip("spaCy indisponível")
    triples = extractor.extract_spacy(
        "Pelé defendeu o Santos durante toda a sua carreira.", max_triples=50
    )
    defendeu = [t for t in triples if t.predicate == "DEFENDEU"]
    assert len(defendeu) == 1
    assert defendeu[0].object == "Santos"


def test_nominal_gate_counter_isolated_from_rejection_counter() -> None:
    extractor = EntityExtractor(enable_fallback=False, enable_nominal_copular=True)
    if extractor._nlp is None:
        pytest.skip("spaCy indisponível")
    extractor.extract_spacy(
        "Botafogo is a Brazilian football club. O Santos FC é um clube brasileiro "
        "fundado em 1912.",
        max_triples=50,
    )
    assert dict(extractor.rejection_reasons) == {}
    assert dict(extractor.nominal_gate_reasons)
