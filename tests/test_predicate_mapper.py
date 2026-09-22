"""Testes do mapeador determinístico de predicados (v1.13.0 item 3.1)."""
from src.cognition.predicate_mapper import (
    CONTROLLED_PREDICATES,
    MAX_CONTROLLED_PREDICATES,
    map_predicate,
    normalize_predicate_key,
    predicate_map,
    validate_predicate,
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


def test_guard_rejects_numeric_url_stopword_and_nonverbal():
    assert validate_predicate("1912") == (None, "numeric_predicate")
    assert validate_predicate("século XX") == (None, "numeric_predicate")
    assert validate_predicate("https://exemplo.com/artigo") == (None, "url_or_code_predicate")
    assert validate_predicate("github.com") == (None, "url_or_code_predicate")
    assert validate_predicate("the") == (None, "stopword_predicate")
    assert validate_predicate("de") == (None, "stopword_predicate")
    assert validate_predicate("YEAR") == (None, "nonverbal_predicate")
    assert validate_predicate("THROUGH") == (None, "nonverbal_predicate")
    assert validate_predicate("STORY") == (None, "nonverbal_predicate")
    assert validate_predicate("CODER") == (None, "nonverbal_predicate")
    assert validate_predicate("DEEPR") == (None, "nonverbal_predicate")


def test_guard_accepts_mapped_and_classifies_valid_verbs():
    assert validate_predicate("utiliza") == ("UTILIZA", "ok")
    assert validate_predicate("preservir") == ("PRESERVA", "ok")
    assert validate_predicate("publicar") == (None, "unmapped_predicate")
    assert validate_predicate("descrever") == (None, "unmapped_predicate")
    assert validate_predicate("ter") == (None, "unmapped_predicate")
    assert validate_predicate("zapearia") == (None, "invalid_predicate")
    assert validate_predicate("") == (None, "invalid_predicate")
