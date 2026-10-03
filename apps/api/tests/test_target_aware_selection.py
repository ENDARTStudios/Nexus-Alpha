"""#048.10B — target-aware selection (prioriza JOGADOR--DEFENDEU-->CLUBE).

Helpers puros (sempre) + integração spaCy (pula sem modelo).
"""
import pytest

from src.cognition.extractor import (
    EntityExtractor,
    _is_target_defendeu_triple,
    _is_target_player_club_sentence,
)


def test_target_sentence_detection_pt_en():
    assert _is_target_player_club_sentence("Garrincha defendeu o Botafogo por 12 anos.")
    assert _is_target_player_club_sentence("Pelé jogou no Santos.")
    assert _is_target_player_club_sentence("Garrincha played for Botafogo.")
    assert _is_target_player_club_sentence("Didi represented Botafogo.")
    # sem indício de defesa ou sem par jogador+clube
    assert not _is_target_player_club_sentence("Garrincha was born in 1933.")
    assert not _is_target_player_club_sentence("The club won the title in 2024.")
    assert not _is_target_player_club_sentence("He played for some team.")


def test_target_defendeu_triple_detection():
    from src.cognition.extractor import Triple
    assert _is_target_defendeu_triple(Triple("Garrincha", "DEFENDEU", "Botafogo", 0.8))
    assert _is_target_defendeu_triple(Triple("Pelé", "DEFENDEU", "Santos", 0.8))
    # não-DEFENDEU ou clube fora da allowlist
    assert not _is_target_defendeu_triple(Triple("Garrincha", "VENCEU", "Botafogo", 0.8))
    assert not _is_target_defendeu_triple(Triple("Garrincha", "DEFENDEU", "Flamengo", 0.8))


def test_target_aware_spacy_prioritizes_player_club():
    extractor = EntityExtractor(enable_fallback=True)
    if extractor._nlp is None:
        pytest.skip("spaCy indisponível")
    # página longa: ~30 frases genéricas antes do fato-alvo
    filler = " ".join(f"O clube disputou a temporada {y}." for y in range(1900, 1930))
    text = filler + " Pelé jogou no Santos."
    triples = [t for t in extractor.extract(text, max_triples=25) if t.predicate == "DEFENDEU"]
    assert any("santos" in t.object.casefold() for t in triples), triples


def test_target_aware_rejects_anaphora_and_national_team():
    extractor = EntityExtractor(enable_fallback=True)
    if extractor._nlp is None:
        pytest.skip("spaCy indisponível")
    for text in ("He played for Botafogo.", "Garrincha played for Brazil."):
        triples = [t for t in extractor.extract(text, max_triples=25) if t.predicate == "DEFENDEU"]
        assert not any(
            t.subject.strip().casefold() in ("he", "ele")
            or "brazil" in t.object.casefold() or "brasil" in t.object.casefold()
            for t in triples
        ), (text, [(t.subject, t.object) for t in triples])


def test_target_aware_does_not_break_honours():
    # não regressão: a priorização não afeta o caminho VENCEU/honras.
    from src.cognition.table_extractor import extract_honours_from_html
    from src.cognition.canonicalizer import SemanticCanonicalizer

    html = ("<html><body><table class=wikitable>"
            "<tr><th>Competitions</th><th>Titles</th><th>Seasons</th></tr>"
            "<tr><td>Copa Libertadores</td><td>1</td><td>2024</td></tr>"
            "</table></body></html>")
    triples, _ = extract_honours_from_html(
        html, "https://en.wikipedia.org/wiki/Botafogo_de_Futebol_e_Regatas", SemanticCanonicalizer())
    assert any(t["object"] == "COPA LIBERTADORES" for t in triples)
