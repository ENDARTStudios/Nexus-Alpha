"""#058.12 — testes da extração tabular controlada (schema honours_competition_year).

Fixtures sintéticas + excerto real do formato RSSSF (<pre>). Sem rede.
"""
from src.cognition.canonicalizer import SemanticCanonicalizer
from src.cognition.table_extractor import (
    CLUB_ALLOWLIST,
    TABLE_PREDICATE,
    extract_honours_from_html,
)

COPA_URL = "https://www.rsssf.org/sacups/copalib.html"
BRAZ_URL = "https://www.rsssf.org/tablesb/brazchamp.html"

CANON = SemanticCanonicalizer()


def _extract(html: str, url: str):
    triples, stats = extract_honours_from_html(html, url, CANON)
    return triples, stats


def test_honours_table_single_title():
    html = """
    <html><body><table class="honours">
      <caption>Botafogo de Futebol e Regatas</caption>
      <tr><th>Competition</th><th>Titles</th><th>Years</th></tr>
      <tr><td>Copa Libertadores</td><td>1</td><td>2024</td></tr>
    </table></body></html>
    """
    triples, _ = _extract(html, COPA_URL)
    assert len(triples) == 1
    t = triples[0]
    assert t["subject"] == "BOTAFOGO DE FUTEBOL E REGATAS"
    assert t["predicate"] == "VENCEU"
    assert t["object"] == "COPA LIBERTADORES"
    assert t["metadata"]["year"] == 2024
    assert t["metadata"]["table_schema"] == "honours_competition_year"
    assert t["metadata"]["source_type"] == "table"


def test_honours_table_multiple_years_one_row():
    html = """
    <html><body><table>
      <caption>Botafogo de Futebol e Regatas</caption>
      <tr><th>Competition</th><th>Years</th></tr>
      <tr><td>Campeonato Brasileiro Série A</td><td>1968, 1995, 2024</td></tr>
    </table></body></html>
    """
    triples, _ = _extract(html, BRAZ_URL)
    assert len(triples) == 3
    years = sorted(t["metadata"]["year"] for t in triples)
    assert years == [1968, 1995, 2024]
    assert {t["object"] for t in triples} == {"CAMPEONATO BRASILEIRO SERIE A"}
    assert all(t["subject"] == "BOTAFOGO DE FUTEBOL E REGATAS" for t in triples)


def test_total_row_rejected():
    html = """
    <html><body><table>
      <caption>Botafogo de Futebol e Regatas</caption>
      <tr><th>Competition</th><th>Titles</th></tr>
      <tr><td>Total</td><td>3</td></tr>
    </table></body></html>
    """
    triples, stats = _extract(html, COPA_URL)
    assert triples == []
    assert stats.get("table_competition_missing", 0) >= 1


def test_year_only_and_numeric_rows_rejected():
    html = """
    <html><body><pre>
    2024
    3
    Founded 1894
    </pre></body></html>
    """
    triples, _ = _extract(html, COPA_URL)
    assert triples == []


def test_non_whitelisted_url_yields_nothing():
    html = "<html><body><pre>2024 Botafogo</pre></body></html>"
    triples, stats = _extract(html, "https://example.com/honours")
    assert triples == []
    assert stats.get("not_whitelisted_url") == 1


def test_predicate_is_never_ser():
    html = """
    <html><body>
    <pre>
    2024 Botafogo
    1995 Botafogo de Futebol e Regatas
    1962 Santos
    </pre>
    <table>
      <caption>Santos Futebol Clube</caption>
      <tr><th>Competition</th><th>Years</th></tr>
      <tr><td>Copa Libertadores</td><td>1962, 1963</td></tr>
    </table>
    </body></html>
    """
    triples, _ = _extract(html, COPA_URL)
    assert triples, "esperava ao menos 1 tripla"
    assert all(t["predicate"] == TABLE_PREDICATE == "VENCEU" for t in triples)
    assert all(t["predicate"] != "SER" for t in triples)


def test_rsssf_pre_winners_list_botafogo_2024():
    # Excerto fiel ao formato real de rsssf.org/sacups/copalib.html (<pre>).
    html = """
    <html><body><pre>
    2016 Penarol
    2017 Nacional
    2024 Botafogo
    </pre>
    <pre>
    2024 Botafogo            3-1 Atletico Mineiro
    </pre></body></html>
    """
    triples, stats = _extract(html, COPA_URL)
    # Linha de winners conta; linha de final (placar) é descartada.
    assert len(triples) == 1
    t = triples[0]
    assert (t["subject"], t["predicate"], t["object"]) == (
        "BOTAFOGO DE FUTEBOL E REGATAS", "VENCEU", "COPA LIBERTADORES")
    assert t["metadata"]["year"] == 2024
    assert stats.get("pre_score_line_skipped", 0) >= 1


def test_runner_up_lines_skipped():
    html = """
    <html><body><pre>
    1968     Botafogo de Futebol e Regatas (Rio de Janeiro)
                2nd: Santos Futebol Clube (Santos)
    1995     Botafogo de Futebol e Regatas (Rio de Janeiro)
    </pre></body></html>
    """
    triples, _ = _extract(html, BRAZ_URL)
    assert len(triples) == 2
    assert all(t["subject"] == "BOTAFOGO DE FUTEBOL E REGATAS" for t in triples)
    assert sorted(t["metadata"]["year"] for t in triples) == [1968, 1995]


def test_club_outside_allowlist_rejected():
    html = "<html><body><pre>1982 Penarol\n1983 Nacional\n</pre></body></html>"
    triples, stats = _extract(html, COPA_URL)
    assert triples == []
    assert stats.get("club_not_allowlisted", 0) >= 1


def test_year_is_metadata_never_object():
    html = "<html><body><pre>2024 Botafogo\n1995 Botafogo\n</pre></body></html>"
    triples, _ = _extract(html, COPA_URL)
    assert len(triples) == 2
    for t in triples:
        assert t["object"] == "COPA LIBERTADORES"
        assert t["object"] != "2024" and t["object"] != "1995"
        assert isinstance(t["metadata"]["year"], int)


def test_subjects_are_allowlisted_clubs_only():
    assert CLUB_ALLOWLIST == frozenset({
        "BOTAFOGO DE FUTEBOL E REGATAS",
        "SANTOS FUTEBOL CLUBE",
        "CLUBE DE REGATAS DO FLAMENGO",
        "SOCIEDADE ESPORTIVA PALMEIRAS",
        "SÃO PAULO FUTEBOL CLUBE",
        "GREMIO FOOT BALL PORTO ALEGRENSE",
        "SPORT CLUBE INTERNACIONAL",
    })
