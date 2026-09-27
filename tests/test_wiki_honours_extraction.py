"""#048.7 Fase C — honras wiki controladas (só Botafogo pt/en whitelistadas).

Fixtures sintéticas + recortes fiéis; sem rede. Prova colisão de chave
canônica entre EN + PT + RSSSF (base do predicted_verified).
"""
from src.cognition.canonicalizer import SemanticCanonicalizer
from src.cognition.extractor import EntityExtractor
from src.cognition.table_extractor import (
    TABLE_PREDICATE,
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
