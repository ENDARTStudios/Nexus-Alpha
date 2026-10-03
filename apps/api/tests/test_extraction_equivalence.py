"""Teste golden de equivalência cross-extractor (v1.13.0 item 3-lite #042).

A mesma tripla semântica, nas superfícies produzidas pelos três extratores
(EntityExtractor fallback, NLPExtractor, LLM/heuristic), deve convergir para
UMA única tripla refinada — é isso que permite a `chave` do Neo4j colidir e o
quórum fechar. Puro e sem rede: só canonicalizer + refiner.
"""
from __future__ import annotations

from src.cognition.triple_refiner import refine_triple, refine_triple_ex


# Mesmo fato, três superfícies de extração.
FALLBACK_STYLE = {"subject": "ia", "predicate": "usa", "object": "rede neural"}
NLP_STYLE = {"subject": "Inteligência Artificial", "predicate": "utiliza", "object": "Redes Neurais"}
LLM_STYLE = {"subject": "A INTELIGENCIA ARTIFICIAL", "predicate": "UTILIZA", "object": "redes_neurais"}

EXPECTED_KEY = ("INTELIGÊNCIA ARTIFICIAL", "UTILIZA", "REDES NEURAIS")


def _key(raw: dict) -> tuple:
    refined = refine_triple(dict(raw))
    assert refined is not None
    return (refined["subject"], refined["predicate"], refined["object"])


def test_all_extractor_surfaces_converge_to_single_canonical_triple():
    assert _key(FALLBACK_STYLE) == EXPECTED_KEY
    assert _key(NLP_STYLE) == EXPECTED_KEY
    assert _key(LLM_STYLE) == EXPECTED_KEY


def test_reflexive_predicate_converges_to_controlled():
    refined = refine_triple(
        {"subject": "IA", "predicate": "conecta-se a", "object": "dados"}
    )
    assert refined is not None
    assert refined["predicate"] == "CONECTA_A"


def test_unmapped_verb_reports_reason_without_promoting():
    refined, reason = refine_triple_ex(
        {"subject": "IA", "predicate": "descrever", "object": "dados"}
    )
    assert refined is None
    assert reason == "unmapped_predicate"


def test_utiliza_family_converges_to_single_predicate():
    # #044: usa/utiliza/aplica (+ flexões) devem colidir em UTILIZA.
    for predicate in ("usa", "utiliza", "UTILIZA", "aplica", "aplicou"):
        refined = refine_triple(
            {"subject": "Inteligência Artificial", "predicate": predicate, "object": "aprendizado profundo"}
        )
        assert refined is not None
        assert (refined["subject"], refined["predicate"], refined["object"]) == (
            "INTELIGÊNCIA ARTIFICIAL",
            "UTILIZA",
            "APRENDIZADO PROFUNDO",
        )


def test_possuir_family_converges_to_single_predicate():
    # #044: tem/possui/possuem devem colidir em POSSUIR.
    for predicate in ("tem", "possui", "possuem"):
        refined = refine_triple(
            {"subject": "Santos FC", "predicate": predicate, "object": "Estádio Urbano Caldeira"}
        )
        assert refined is not None
        # #047: aliases curados colapsam variantes PT/EN no canônico do YAML.
        assert (refined["subject"], refined["predicate"], refined["object"]) == (
            "SANTOS FUTEBOL CLUBE",
            "POSSUIR",
            "ESTÁDIO URBANO CALDEIRA",
        )


def test_modals_do_not_promote():
    # #044: modais/ambíguos nunca viram fato.
    for predicate, reason in (
        ("poder", "modal_predicate"),
        ("deve", "modal_predicate"),
        ("passar", "ambiguous_predicate"),
        ("aumentou", "ambiguous_predicate"),
    ):
        refined, got = refine_triple_ex(
            {"subject": "IA", "predicate": predicate, "object": "dados"}
        )
        assert refined is None
        assert got == reason


def test_garbage_predicate_reports_invalid_not_unmapped():
    refined, reason = refine_triple_ex(
        {"subject": "IA", "predicate": "zapearia", "object": "dados"}
    )
    assert refined is None
    assert reason == "invalid_predicate"
