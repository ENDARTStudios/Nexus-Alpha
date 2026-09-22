"""Testes do refinador determinístico de triplas (item 3-lite)."""
from src.cognition.triple_refiner import (
    RejectionQuarantine,
    filter_noisy_sentence,
    link_entity,
    normalize_predicate,
    refine_triple,
    refine_triple_ex,
    score_candidate_sentence,
)


DECLARATIVE = "A inteligência artificial utiliza redes neurais profundas para aprender."


def test_filter_keeps_declarative_sentence():
    assert filter_noisy_sentence(DECLARATIVE) == DECLARATIVE


def test_filter_rejects_tutorial_ui_and_questions():
    assert filter_noisy_sentence("Clique aqui para instalar o pacote") is None
    assert filter_noisy_sentence("Execute este código no terminal") is None
    assert filter_noisy_sentence("Instale o pacote com pip install numpy") is None
    assert filter_noisy_sentence("O que é aprendizado de máquina?") is None
    assert filter_noisy_sentence("curto") is None
    assert filter_noisy_sentence("") is None


def test_filter_collapses_whitespace():
    assert filter_noisy_sentence("A   IA   generativa   produz   conteúdo.") == (
        "A IA generativa produz conteúdo."
    )


def test_score_ranks_declarative_above_tutorial():
    assert score_candidate_sentence(DECLARATIVE) > score_candidate_sentence(
        "Clique aqui para instalar o pacote"
    )
    assert 0.0 <= score_candidate_sentence(DECLARATIVE) <= 1.0


def test_normalize_predicate_maps_to_controlled_vocabulary():
    assert normalize_predicate("usa") == "UTILIZA"
    assert normalize_predicate("emprega") == "UTILIZA"
    assert normalize_predicate("difundiu") == "DISTRIBUIR"
    assert normalize_predicate("fundou") == "FUNDOU"
    assert normalize_predicate("impactou") == "INFLUENCIA"


def test_normalize_predicate_rejects_unmapped_verb():
    assert normalize_predicate("zapearia") is None
    assert normalize_predicate("") is None


def test_link_entity_uses_dictionary_then_rejects_garbage():
    assert link_entity("AI") == "INTELIGÊNCIA ARTIFICIAL"
    assert link_entity("nlp") == "PROCESSAMENTO DE LINGUAGEM NATURAL"
    assert link_entity("clique aqui") is None
    assert link_entity("x") is None


def test_refine_triple_returns_raw_and_canonical():
    refined = refine_triple(
        {"subject": "AI", "predicate": "usa", "object": "redes_neurais", "confidence": 0.7},
    )
    assert refined is not None
    assert refined["subject"] == "INTELIGÊNCIA ARTIFICIAL"
    assert refined["predicate"] == "UTILIZA"
    assert refined["object"] == "REDES NEURAIS"
    assert refined["raw_subject"] == "AI"
    assert refined["raw_predicate"] == "usa"
    assert refined["extraction_confidence"] == 0.7


def test_refine_triple_rejects_noise_and_self_loops():
    assert refine_triple({"subject": "AI", "predicate": "zapearia", "object": "dados"}) is None
    assert refine_triple({"subject": "AI", "predicate": "usa", "object": ""}) is None
    assert refine_triple({"subject": "dados", "predicate": "usa", "object": "dados"}) is None


def test_refine_triple_ex_reports_reasons():
    refined, reason = refine_triple_ex({"subject": "AI", "predicate": "usa", "object": "redes_neurais"})
    assert refined is not None and reason == "ok"

    _, reason = refine_triple_ex({"subject": "AI", "predicate": "zapearia", "object": "dados"})
    assert reason == "unmapped_predicate"

    _, reason = refine_triple_ex({"subject": "", "predicate": "usa", "object": "dados"})
    assert reason == "missing_entity"

    _, reason = refine_triple_ex({"subject": "dados", "predicate": "usa", "object": "dados"})
    assert reason == "self_loop"


def test_refine_triple_maps_extended_predicates():
    refined = refine_triple({"subject": "regularização", "predicate": "preservir", "object": "generalização"})
    assert refined is not None
    assert refined["predicate"] == "PRESERVA"


def test_rejection_quarantine_caps_records(tmp_path):
    quarantine = RejectionQuarantine(path=tmp_path, max_records=5)
    for index in range(12):
        quarantine.record(
            {"subject": f"S{index}", "predicate": "PRESERVIR", "object": "X"},
            "unmapped_predicate",
        )
    lines = (tmp_path / "rejected_triples.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) <= 5
    stats = quarantine.stats()
    assert stats["total"] == 12
    assert stats["unmapped_predicate"] == 12
