"""Testes do mapeador determinístico de predicados (v1.13.0 item 3.1)."""
from src.cognition.predicate_mapper import (
    CONTROLLED_PREDICATES,
    MAX_CONTROLLED_PREDICATES,
    map_predicate,
    normalize_predicate_key,
    predicate_map,
)


def test_preservir_maps_to_preserva():
    assert map_predicate("PRESERVIR") == ("PRESERVA", "ok")
    assert map_predicate("Preservação") == ("PRESERVA", "ok")
    assert map_predicate("preserva") == ("PRESERVA", "ok")


def test_teoricar_maps_to_teoriza():
    assert map_predicate("TEÓRICAR") == ("TEORIZA", "ok")
    assert map_predicate("teorização") == ("TEORIZA", "ok")


def test_amigavel_maps_to_amigavel_canonical():
    assert map_predicate("Amigável") == ("É_AMIGÁVEL", "ok")
    assert map_predicate("user-friendly") == ("É_AMIGÁVEL", "ok")


def test_base_buckets_still_work():
    assert map_predicate("usa") == ("UTILIZA", "ok")
    assert map_predicate("difundiu") == ("DISTRIBUIR", "ok")
    assert map_predicate("fundou") == ("FUNDOU", "ok")


def test_unknown_predicate_is_rejected():
    assert map_predicate("zapearia") == (None, "unmapped_predicate")
    assert map_predicate("") == (None, "unmapped_predicate")
    assert map_predicate("   ") == (None, "unmapped_predicate")


def test_normalization_handles_accents_case_and_punctuation():
    assert normalize_predicate_key("  Preservação ") == "preservacao"
    assert normalize_predicate_key("TEÓRICAR") == "teoricar"
    assert normalize_predicate_key("user-friendly") == "user friendly"


def test_controlled_vocabulary_is_bounded_and_unique():
    assert len(CONTROLLED_PREDICATES) <= MAX_CONTROLLED_PREDICATES
    assert len(set(CONTROLLED_PREDICATES)) == len(CONTROLLED_PREDICATES)
    assert predicate_map()
