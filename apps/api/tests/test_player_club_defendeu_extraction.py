"""#059C — extração controlada player-club DEFENDEU (fonte club-context).

Schema: RSSSF Brasil `jogclub.htm` — padrão `NOME (N jogos ... como jogador do CLUBE)`.
Sem rede: fixtures sintéticas inline.
"""
from src.cognition.canonicalizer import SemanticCanonicalizer
from src.cognition.table_extractor import (
    extract_player_club_from_html,
    is_honours_url,
)

JOGCLUB = "https://www.rsssfbrasil.com/sel/jogclub.htm"
CANON = SemanticCanonicalizer()


def _html(pre_text: str) -> str:
    return f"<html><body><pre>{pre_text}</pre></body></html>"


def test_emits_player_club_defendeu_pt():
    html = _html(
        "são:\n"
        "        Pelé (112 jogos disputados como jogador do Santos);\n"
        "        Jairzinho (101 jogos como jogador do Botafogo)."
    )
    triples, stats = extract_player_club_from_html(html, JOGCLUB, CANON)
    keys = {(t["subject"], t["predicate"], t["object"]) for t in triples}
    assert ("EDSON ARANTES DO NASCIMENTO", "DEFENDEU", "SANTOS FUTEBOL CLUBE") in keys
    assert ("JAIRZINHO", "DEFENDEU", "BOTAFOGO DE FUTEBOL E REGATAS") in keys
    assert stats["emitted"] == 2
    assert all(t["metadata"]["table_schema"] == "club_context_player_records" for t in triples)


def test_garrincha_botafogo_context():
    html = _html("Garrincha (612 jogos como jogador do Botafogo);")
    triples, _ = extract_player_club_from_html(html, JOGCLUB, CANON)
    assert any(t["subject"] == "MANUEL FRANCISCO DOS SANTOS" and t["object"] == "BOTAFOGO DE FUTEBOL E REGATAS"
               for t in triples)


def test_rejects_non_allowlisted_club():
    html = _html("Pelé (112 jogos como jogador do Real Madrid);")
    triples, stats = extract_player_club_from_html(html, JOGCLUB, CANON)
    assert triples == []
    assert stats.get("club_not_allowlisted", 0) >= 1


def test_rejects_non_allowlisted_player():
    html = _html("Marquinhos (109 jogos como jogador do Botafogo);")
    triples, stats = extract_player_club_from_html(html, JOGCLUB, CANON)
    assert triples == []
    assert stats.get("player_not_allowlisted", 0) >= 1


def test_non_whitelisted_url_yields_nothing():
    html = _html("Pelé (112 jogos como jogador do Santos);")
    triples, stats = extract_player_club_from_html(html, "https://example.com/x", CANON)
    assert triples == []
    assert stats.get("not_whitelisted_url") == 1


def test_year_or_number_never_object():
    html = _html(
        "Pelé (112 jogos como jogador do Santos);\n"
        "Garrincha (1953);\nGarrincha (243);"
    )
    triples, _ = extract_player_club_from_html(html, JOGCLUB, CANON)
    assert all(not t["object"].isdigit() for t in triples)
    assert all(t["object"] not in ("1953", "243") for t in triples)


def test_is_controlled_url_includes_jogclub():
    assert is_honours_url(JOGCLUB)
    assert is_honours_url("http://www.rsssfbrasil.com/sel/jogclub.htm")
    assert not is_honours_url("https://www.rsssfbrasil.com/sel/other.htm")


def test_honours_not_regressed():
    from src.cognition.table_extractor import extract_honours_from_html
    html = ("<html><body><table class=wikitable>"
            "<tr><th>Competitions</th><th>Titles</th><th>Seasons</th></tr>"
            "<tr><td>Copa Libertadores</td><td>1</td><td>2024</td></tr>"
            "</table></body></html>")
    triples, _ = extract_honours_from_html(
        html, "https://en.wikipedia.org/wiki/Botafogo_de_Futebol_e_Regatas", CANON)
    assert any(t["object"] == "COPA LIBERTADORES" for t in triples)
