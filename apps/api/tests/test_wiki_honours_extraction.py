"""#048.7 Fase C — honras wiki controladas (só Botafogo pt/en whitelistadas).

Fixtures sintéticas + recortes fiéis; sem rede. Prova colisão de chave
canônica entre EN + PT + RSSSF (base do predicted_verified).
"""
from src.cognition.canonicalizer import SemanticCanonicalizer
from src.cognition.extractor import EntityExtractor
from src.cognition.table_extractor import (
    extract_honours_from_html,
    is_honours_url,
)

PT_URL = "https://pt.wikipedia.org/wiki/Botafogo_de_Futebol_e_Regatas"
EN_URL = "https://en.wikipedia.org/wiki/Botafogo_de_Futebol_e_Regatas"
COPA_URL = "https://www.rsssf.org/sacups/copalib.html"

CANON = SemanticCanonicalizer()
KEY = ("BOTAFOGO DE FUTEBOL E REGATAS", "VENCEU", "COPA LIBERTADORES")


def test_en_honours_row_emits_key_with_year():
    html = """
    <html><body><table class="wikitable">
      <caption>Official tournaments</caption>
      <tr><th>Competitions</th><th>Titles</th><th>Seasons</th></tr>
      <tr><td>Copa Libertadores</td><td>1</td><td>2024</td></tr>
    </table></body></html>
    """
    triples, _ = extract_honours_from_html(html, EN_URL, CANON)
    assert len(triples) == 1
    t = triples[0]
    assert (t["subject"], t["predicate"], t["object"]) == KEY
    assert t["metadata"]["year"] == 2024


def test_pt_honours_row_emits_same_canonical_key():
    html = """
    <html><body><table class="wikitable">
      <tr><th>Competição</th><th>Temporadas</th><th>Melhor campanha</th><th>Estreia</th><th>Última</th></tr>
      <tr><td>Copa Libertadores</td><td>8</td><td>Campeão (2024)</td><td>1963</td><td>2026</td></tr>
    </table></body></html>
    """
    triples, _ = extract_honours_from_html(html, PT_URL, CANON)
    assert len(triples) == 1
    t = triples[0]
    assert (t["subject"], t["predicate"], t["object"]) == KEY
    assert t["metadata"]["year"] == 2024


def test_three_source_collision_same_key():
    en_html = """<html><body><table class="wikitable">
      <tr><th>Competitions</th><th>Titles</th><th>Seasons</th></tr>
      <tr><td>Copa Libertadores</td><td>1</td><td>2024</td></tr>
      </table></body></html>"""
    pt_html = """<html><body><table class="wikitable">
      <tr><th>Competição</th><th>Melhor campanha</th></tr>
      <tr><td>Copa Libertadores</td><td>Campeão (2024)</td></tr>
      </table></body></html>"""
    rsssf_html = "<html><body><pre>2024 Botafogo</pre></body></html>"
    keys = set()
    for html, url in ((en_html, EN_URL), (pt_html, PT_URL), (rsssf_html, COPA_URL)):
        triples, _ = extract_honours_from_html(html, url, CANON)
        assert triples, url
        keys.update((t["subject"], t["predicate"], t["object"]) for t in triples)
    assert keys == {KEY}


def test_runners_up_row_emits_nothing():
    html = """<html><body><table class="wikitable">
      <tr><th>Competition</th><th>Titles</th><th>Seasons</th></tr>
      <tr><td>Recopa Sudamericana (2)</td><td>1994, 2025</td><td>Runners-up</td></tr>
      </table></body></html>"""
    triples, stats = extract_honours_from_html(html, EN_URL, CANON)
    assert triples == []
    assert stats.get("wiki_runner_up_row", 0) >= 1


def test_generic_total_row_emits_nothing():
    html = """<html><body><table class="wikitable">
      <tr><th>Competition</th><th>Titles</th></tr>
      <tr><td>Total</td><td>3</td></tr>
      </table></body></html>"""
    triples, _ = extract_honours_from_html(html, EN_URL, CANON)
    assert triples == []


def test_year_only_object_rejected():
    html = """<html><body><table class="wikitable">
      <tr><th>Competition</th><th>Seasons</th></tr>
      <tr><td>2024</td><td>2024</td></tr>
      </table></body></html>"""
    triples, _ = extract_honours_from_html(html, EN_URL, CANON)
    assert triples == []


def test_clause_object_rejected():
    html = """<html><body><table class="wikitable">
      <tr><th>Competition</th><th>Note</th></tr>
      <tr><td>won the title after defeating Atlético Mineiro</td><td>2024</td></tr>
      </table></body></html>"""
    triples, _ = extract_honours_from_html(html, EN_URL, CANON)
    assert triples == []


def test_wiki_narrative_preserved_alongside_table():
    extractor = EntityExtractor()
    payload = {
        "source_url": EN_URL,
        "title": "t",
        "content": "Garrincha played for Botafogo for 12 years.",
        "extracted_entities": [],
        "raw_html": """<html><body><table class="wikitable">
          <tr><th>Competitions</th><th>Titles</th><th>Seasons</th></tr>
          <tr><td>Copa Libertadores</td><td>1</td><td>2024</td></tr>
          </table></body></html>""",
    }
    out = extractor.enrich_payload(payload)
    table = [t for t in out["extracted_entities"] if t["predicate"] == "VENCEU"]
    assert len(table) == 1
    assert (table[0]["subject"], table[0]["object"]) == (
        "BOTAFOGO DE FUTEBOL E REGATAS", "COPA LIBERTADORES")
    assert "raw_html" not in out


def test_rsssf_table_only_policy_unaffected():
    extractor = EntityExtractor()
    payload = {
        "source_url": COPA_URL,
        "title": "t",
        "content": "Copa de Campeones é held in Santiago.",
        "extracted_entities": [],
        "raw_html": "<html><body><pre>2024 Botafogo</pre></body></html>",
    }
    out = extractor.enrich_payload(payload)
    assert all(t["predicate"] == "VENCEU" for t in out["extracted_entities"])
    assert len(out["extracted_entities"]) == 1


def test_non_whitelisted_wiki_page_gets_no_table_triples():
    html = """<html><body><table class="wikitable">
      <tr><th>Competitions</th><th>Titles</th><th>Seasons</th></tr>
      <tr><td>Copa Libertadores</td><td>1</td><td>2024</td></tr>
      </table></body></html>"""
    triples, stats = extract_honours_from_html(
        html, "https://en.wikipedia.org/wiki/Flamengo", CANON)
    assert triples == []
    assert stats.get("not_whitelisted_url") == 1
    assert not is_honours_url("https://en.wikipedia.org/wiki/Flamengo")


def test_santos_is_whitelisted_phase_048_8():
    # #048.8: Santos pt/en habilitado (dry-run full_collision Libertadores).
    assert is_honours_url("https://pt.wikipedia.org/wiki/Santos_FC")
    assert is_honours_url("https://en.wikipedia.org/wiki/Santos_FC")


def test_santos_pt_titulos_table_emits_key():
    # Formato PT "Títulos" (classe livre, anos na célula de temporadas).
    html = """<html><body><table class="infobox">
      <tr><td>Mundiais</td></tr>
      <tr><th>Competição</th><th>Títulos</th><th>Temporadas</th></tr>
      <tr><td>Copa Libertadores da América</td><td>3</td><td>1962, 1963 e 2011</td></tr>
      <tr><td>Campeonato Brasileiro - Série A</td><td>8</td><td>1961, 1962 e 2004</td></tr>
      </table></body></html>"""
    triples, _ = extract_honours_from_html(
        html, "https://pt.wikipedia.org/wiki/Santos_FC", CANON)
    keys = {(t["subject"], t["object"]) for t in triples}
    years = {t["metadata"]["year"] for t in triples}
    assert ("SANTOS FUTEBOL CLUBE", "COPA LIBERTADORES") in keys
    assert {1962, 1963, 2011}.issubset(years)
    # #048.8: Brasileirão NÃO habilitado p/ Santos (colisão parcial).
    assert ("SANTOS FUTEBOL CLUBE", "CAMPEONATO BRASILEIRO SERIE A") not in keys


def test_santos_navbox_not_parsed_as_honours():
    # Navbox "Ligações externas" lista edições; nunca vira fato.
    html = """<html><body><table class="navbox-inner">
      <tr><td>Campeonato Brasileiro - Série A</td><td>1989 1990 1991 1992</td></tr>
      </table></body></html>"""
    triples, _ = extract_honours_from_html(
        html, "https://pt.wikipedia.org/wiki/Santos_FC", CANON)
    assert triples == []


def test_botafogo_brasileirao_still_enabled():
    # Regressão #048.7: Botafogo mantém Libertadores + Brasileirão.
    html = """<html><body><table class="wikitable">
      <tr><th>Competitions</th><th>Titles</th><th>Seasons</th></tr>
      <tr><td>Campeonato Brasileiro Série A</td><td>3</td><td>1968, 1995, 2024</td></tr>
      <tr><td>Copa Libertadores</td><td>1</td><td>2024</td></tr>
      </table></body></html>"""
    triples, _ = extract_honours_from_html(
        html, "https://en.wikipedia.org/wiki/Botafogo_de_Futebol_e_Regatas", CANON)
    keys = {(t["subject"], t["object"]) for t in triples}
    assert ("BOTAFOGO DE FUTEBOL E REGATAS", "CAMPEONATO BRASILEIRO SERIE A") in keys
    assert ("BOTAFOGO DE FUTEBOL E REGATAS", "COPA LIBERTADORES") in keys


# --- #048.9 multi-clube -------------------------------------------------------

FLAMENGO_PT = "https://pt.wikipedia.org/wiki/Clube_de_Regatas_do_Flamengo"
PALMEIRAS_EN = "https://en.wikipedia.org/wiki/SE_Palmeiras"
SAOPAULO_PT = "https://pt.wikipedia.org/wiki/S%C3%A3o_Paulo_Futebol_Clube"
GREMIO_EN = "https://en.wikipedia.org/wiki/Gr%C3%AAmio_FBPA"
INTER_PT = "https://pt.wikipedia.org/wiki/Sport_Club_Internacional"


def _honours_table(row: str, caption: str = "") -> str:
    _cap = f"<caption>{caption}</caption>" if caption else ""
    return ("<html><body><table class=wikitable>"
            "<tr><th>Competitions</th><th>Titles</th><th>Seasons</th></tr>"
            f"{row}</table></body></html>")


def test_multi_club_libertadores_wiki_keys():
    cases = {
        FLAMENGO_PT: ("CLUBE DE REGATAS DO FLAMENGO", "1981, 2019, 2022, 2025"),
        PALMEIRAS_EN: ("SOCIEDADE ESPORTIVA PALMEIRAS", "1999, 2020, 2021"),
        SAOPAULO_PT: ("SÃO PAULO FUTEBOL CLUBE", "1992, 1993, 2005"),
        GREMIO_EN: ("GREMIO FOOT BALL PORTO ALEGRENSE", "1983, 1995, 2017"),
        INTER_PT: ("SPORT CLUBE INTERNACIONAL", "2006, 2010"),
    }
    for url, (club, years) in cases.items():
        html = _honours_table(f"<tr><td>Copa Libertadores</td><td>3</td><td>{years}</td></tr>")
        triples, _ = extract_honours_from_html(html, url, CANON)
        assert triples, url
        assert all(t["subject"] == club for t in triples), url
        assert all(t["object"] == "COPA LIBERTADORES" for t in triples), url


def test_palmeiras_sao_paulo_brasileirao_emitted():
    for url, club in ((PALMEIRAS_EN, "SOCIEDADE ESPORTIVA PALMEIRAS"),
                      (SAOPAULO_PT, "SÃO PAULO FUTEBOL CLUBE")):
        html = _honours_table("<tr><td>Campeonato Brasileiro Série A</td><td>3</td><td>1968, 1995, 2024</td></tr>")
        triples, _ = extract_honours_from_html(html, url, CANON)
        assert any(t["object"] == "CAMPEONATO BRASILEIRO SERIE A" for t in triples), url


def test_gremio_flamengo_internacional_brasileirao_not_enabled():
    # Dry-run #048.9: Brasileirão p/ estes clubes = partial (sem 3º domínio).
    for url, club in ((GREMIO_EN, "GREMIO"), (FLAMENGO_PT, "FLAMENGO"), (INTER_PT, "SPORT")):
        html = _honours_table("<tr><td>Campeonato Brasileiro Série A</td><td>3</td><td>1968, 1995, 2024</td></tr>")
        triples, _ = extract_honours_from_html(html, url, CANON)
        assert not any(t["object"] == "CAMPEONATO BRASILEIRO SERIE A" for t in triples), url


def test_flamengo_pt_year_range_participation_rejected():
    # Tabela de participações (ranges de anos) não é título.
    html = ('<html><body><table class=wikitable><caption>Títulos</caption>'
            '<tr><th>Competição</th><th>Temporadas</th></tr>'
            '<tr><td>Copa Libertadores da América</td><td>1981–1984, 1991, 1993, 2017–2026</td></tr>'
            '<tr><td>Copa Libertadores da América</td><td>1981, 2019, 2022, 2025</td></tr>'
            '</table></body></html>')
    triples, stats = extract_honours_from_html(html, FLAMENGO_PT, CANON)
    years = sorted(t["metadata"]["year"] for t in triples)
    assert years == [1981, 2019, 2022, 2025]
    assert stats.get("wiki_year_range_participation", 0) >= 1


def test_rsssf_short_name_alias_multi_club():
    html = ("<html><body><pre>"
            "1981 Flamengo\n1999 Palmeiras\n1992 São Paulo\n1983 Grêmio\n2006 Internacional\n"
            "</pre></body></html>")
    triples, _ = extract_honours_from_html(html, COPA_URL, CANON)
    subjects = {t["subject"] for t in triples}
    assert {"CLUBE DE REGATAS DO FLAMENGO", "SOCIEDADE ESPORTIVA PALMEIRAS",
            "SÃO PAULO FUTEBOL CLUBE", "GREMIO FOOT BALL PORTO ALEGRENSE",
            "SPORT CLUBE INTERNACIONAL"}.issubset(subjects)


def test_managers_table_not_honours():
    html = ("<html><body><table class=wikitable>"
            "<tr><th>Season</th><th>Manager</th><th>Titles</th></tr>"
            "<tr><td>1981</td><td>Paulo César</td><td>Copa Libertadores</td></tr>"
            "</table></body></html>")
    triples, _ = extract_honours_from_html(html, FLAMENGO_PT, CANON)
    assert triples == []


def test_most_appearances_table_not_honours():
    html = ("<html><body><table class=wikitable sortable>"
            "<tr><th>Rank</th><th>Player</th><th>Apps</th></tr>"
            "<tr><td>1</td><td>Júnior</td><td>876</td></tr>"
            "</table></body></html>")
    triples, _ = extract_honours_from_html(html, FLAMENGO_PT, CANON)
    assert triples == []


def test_rsssf_winners_runner_up_not_emitted():
    html = ("<html><body><pre>"
            "1992 São Paulo\n"
            "    2nd: Newell's Old Boys\n"
            "2005 São Paulo\n"
            "</pre></body></html>")
    triples, _ = extract_honours_from_html(html, COPA_URL, CANON)
    subjects = {(t["subject"], t["metadata"]["year"]) for t in triples}
    assert ("SÃO PAULO FUTEBOL CLUBE", 1992) in subjects
    assert ("SÃO PAULO FUTEBOL CLUBE", 2005) in subjects
    assert len(triples) == 2
