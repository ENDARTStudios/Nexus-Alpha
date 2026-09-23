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
    assert validate_predicate("publicar") == ("PRODUZ", "ok")
    assert validate_predicate("ter") == ("POSSUIR", "ok")
    assert validate_predicate("descrever") == (None, "unmapped_predicate")
    assert validate_predicate("zapearia") == (None, "invalid_predicate")
    assert validate_predicate("") == (None, "invalid_predicate")


def test_high_confidence_pt_aliases_map_to_controlled():
    assert map_predicate("TER") == ("POSSUIR", "ok")
    assert map_predicate("tem") == ("POSSUIR", "ok")
    assert map_predicate("tinha") == ("POSSUIR", "ok")
    assert map_predicate("INCLUIR") == ("CONTIENE", "ok")
    assert map_predicate("inclui") == ("CONTIENE", "ok")
    assert map_predicate("APLICAR") == ("UTILIZA", "ok")
    assert map_predicate("aplicou") == ("UTILIZA", "ok")
    assert map_predicate("PUBLICAR") == ("PRODUZ", "ok")
    assert map_predicate("publicou") == ("PRODUZ", "ok")
    assert map_predicate("DESENVOLVER") == ("PRODUZ", "ok")
    assert map_predicate("desenvolveu") == ("PRODUZ", "ok")


def test_modals_and_ambiguous_are_rejected_with_specific_reason():
    assert map_predicate("PODER") == (None, "modal_predicate")
    assert map_predicate("pode") == (None, "modal_predicate")
    assert map_predicate("DEVER") == (None, "modal_predicate")
    assert map_predicate("deve") == (None, "modal_predicate")
    assert map_predicate("PASSAR") == (None, "ambiguous_predicate")
    assert map_predicate("passou") == (None, "ambiguous_predicate")
    assert map_predicate("AUMENTAR") == (None, "ambiguous_predicate")
    assert map_predicate("aumentou") == (None, "ambiguous_predicate")
    assert map_predicate("DESCREVER") == (None, "unmapped_predicate")
    assert validate_predicate("poder") == (None, "modal_predicate")
    assert validate_predicate("passar") == (None, "ambiguous_predicate")


def test_valid_controlled_predicates_stay_valid():
    for predicate in (
        "UTILIZA", "CONECTA_A", "DISTRIBUIR", "PRESERVA",
        "TEORIZA", "É_AMIGÁVEL", "INFLUENCIA", "FUNDOU",
    ):
        assert validate_predicate(predicate) == (predicate, "ok")


def test_controlled_names_with_underscore_survive_guard():
    # Regressão de produção: nomes canônicos com "_" eram rejeitados como código.
    assert validate_predicate("CONECTA_A") == ("CONECTA_A", "ok")
    assert validate_predicate("PERTENCE_A") == ("PERTENCE_A", "ok")
    assert validate_predicate("DERIVA_DE") == ("DERIVA_DE", "ok")
    assert validate_predicate("É_AMIGÁVEL") == ("É_AMIGÁVEL", "ok")


def test_reflexive_voice_maps_to_controlled():
    # #042: voz reflexiva ("-se") é a forma dominante em texto minerado PT.
    assert map_predicate("conecta-se a") == ("CONECTA_A", "ok")
    assert map_predicate("conecta se") == ("CONECTA_A", "ok")
    assert map_predicate("utiliza-se") == ("UTILIZA", "ok")
    assert validate_predicate("conecta-se a") == ("CONECTA_A", "ok")
    assert validate_predicate("utiliza-se") == ("UTILIZA", "ok")


# --- #045.1 — vocabulário esportivo (lista fechada) -------------------------

def test_sport_vocabulary_is_bounded_and_unique():
    from src.cognition.predicate_mapper import EXTRA_PREDICATES
    assert "DEFENDEU" in EXTRA_PREDICATES
    assert "VENCEU" in EXTRA_PREDICATES
    assert "LOCALIZADO_EM" in EXTRA_PREDICATES
    assert "DISPUTOU" in EXTRA_PREDICATES
    assert "TREINOU" in EXTRA_PREDICATES
    assert len(CONTROLLED_PREDICATES) <= MAX_CONTROLLED_PREDICATES
    assert len(set(CONTROLLED_PREDICATES)) == len(CONTROLLED_PREDICATES)


def test_sport_verbs_map_to_controlled():
    assert map_predicate("defendeu") == ("DEFENDEU", "ok")
    assert map_predicate("jogou por") == ("DEFENDEU", "ok")
    assert map_predicate("vestiu") == ("DEFENDEU", "ok")
    assert map_predicate("venceu") == ("VENCEU", "ok")
    assert map_predicate("conquistou") == ("VENCEU", "ok")
    assert map_predicate("ganhou") == ("VENCEU", "ok")
    assert map_predicate("fica em") == ("LOCALIZADO_EM", "ok")
    assert map_predicate("localiza-se em") == ("LOCALIZADO_EM", "ok")
    assert map_predicate("sediado em") == ("LOCALIZADO_EM", "ok")
    assert map_predicate("disputou") == ("DISPUTOU", "ok")
    assert map_predicate("participou") == ("DISPUTOU", "ok")
    assert map_predicate("treinou") == ("TREINOU", "ok")
    assert map_predicate("comandou") == ("TREINOU", "ok")


def test_sport_verbs_en_map_to_controlled():
    assert map_predicate("played for") == ("DEFENDEU", "ok")
    assert map_predicate("joined") == ("DEFENDEU", "ok")
    assert map_predicate("won") == ("VENCEU", "ok")
    assert map_predicate("located in") == ("LOCALIZADO_EM", "ok")
    assert map_predicate("competed") == ("DISPUTOU", "ok")
    assert map_predicate("coached") == ("TREINOU", "ok")


def test_guard_accepts_sport_verbs_and_default_predicates():
    assert validate_predicate("defendeu") == ("DEFENDEU", "ok")
    assert validate_predicate("jogou por") == ("DEFENDEU", "ok")
    assert validate_predicate("foi") == ("SER", "ok")
    assert validate_predicate("was") == ("SER", "ok")
    assert validate_predicate("processa") == ("EXECUTA", "ok")
    assert validate_predicate("connects") == ("CONECTA_A", "ok")


def test_golden_cross_domain_sport_verbs_collapse_to_same_predicate():
    # #045.1: mesma relação expressa por verbos/idiomas diferentes colapsa.
    from src.cognition.triple_refiner import refine_triple_ex

    a, reason_a = refine_triple_ex(
        {"subject": "Pelé", "predicate": "defendeu", "object": "Santos FC"}
    )
    b, reason_b = refine_triple_ex(
        {"subject": "Pelé", "predicate": "jogou por", "object": "Santos Futebol Clube"}
    )
    assert reason_a == "ok" and reason_b == "ok"
    assert a["predicate"] == b["predicate"] == "DEFENDEU"
    assert a["subject"] == b["subject"] == "PELE"

    c, reason_c = refine_triple_ex(
        {"subject": "Pele", "predicate": "played for", "object": "Santos FC"}
    )
    assert reason_c == "ok"
    assert c["predicate"] == "DEFENDEU"


def test_unmapped_sport_verbs_quarantine_as_unmapped_not_invalid():
    # Verbos esportivos legítimos sem mapeamento claro → quarentena (#044/#045),
    # nunca lixo (#043 invalid_predicate).
    for verb in ("contratou", "liderou", "atuou", "scored", "captained", "causa", "resulta"):
        canonical, reason = validate_predicate(verb)
        assert canonical is None, verb
        assert reason == "unmapped_predicate", (verb, reason)
