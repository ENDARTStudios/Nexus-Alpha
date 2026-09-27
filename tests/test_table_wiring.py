"""#048.6 batch 3 — wiring da extração tabular no path do worker/extractor.

Prova que fixture RSSSF/honours gera tripla canônica quando processada por
``EntityExtractor.enrich_payload`` (path real do worker via
``RAGEngine.fetch_and_verify``), não apenas pelo script de auditoria.
Sem rede: HTML inline + miner real só para whitelist check.
"""
from src.cognition.extractor import EntityExtractor
from src.cognition.table_extractor import is_honours_url

COPA_URL = "https://www.rsssf.org/sacups/copalib.html"

RSSSF_PRE = """
<html><body><pre>
2022 Flamengo
2023 Fluminense
2024 Botafogo
</pre>
<pre>
2024 Botafogo            3-1 Atletico Mineiro
</pre></body></html>
"""


def _payload(url: str, text: str = "Botafogo venceu.", html: str | None = None) -> dict:
    payload = {
        "source_url": url,
        "title": "t",
        "content": text,
        "extracted_entities": [],
    }
    if html is not None:
        payload["raw_html"] = html
    return payload


def _table_triples(payload: dict) -> list[dict]:
    return [t for t in payload.get("extracted_entities", []) if t.get("predicate") == "VENCEU"]


def test_enrich_payload_emits_table_triple_for_whitelisted_url():
    extractor = EntityExtractor()
    payload = _payload(COPA_URL, html=RSSSF_PRE)
    out = extractor.enrich_payload(payload)
    table = _table_triples(out)
    assert len(table) == 1
    assert (table[0]["subject"], table[0]["predicate"], table[0]["object"]) == (
        "BOTAFOGO DE FUTEBOL E REGATAS", "VENCEU", "COPA LIBERTADORES")
    assert set(table[0]) == {"subject", "predicate", "object", "confidence"}
    assert "raw_html" not in out, "raw_html deve ser consumido antes do POST"


def test_enrich_payload_ignores_raw_html_for_non_whitelisted_url():
    extractor = EntityExtractor()
    payload = _payload("https://example.com/honours", html=RSSSF_PRE)
    out = extractor.enrich_payload(payload)
    assert _table_triples(out) == []
    assert "raw_html" not in out


def test_enrich_payload_without_raw_html_is_narrative_only():
    extractor = EntityExtractor()
    payload = _payload(COPA_URL, text="Botafogo venceu a final.")
    out = extractor.enrich_payload(payload)
    assert _table_triples(out) == []
    assert "raw_html" not in out


def test_enrich_payload_preserves_narrative_triples():
    extractor = EntityExtractor()
    payload = _payload(COPA_URL, text="Botafogo venceu a final.", html=RSSSF_PRE)
    out = extractor.enrich_payload(payload)
    narrative = [t for t in out["extracted_entities"] if t.get("predicate") != "VENCEU"]
    table = _table_triples(out)
    assert len(table) == 1
    # narrativa segue seu caminho (pode ser 0 via fallback); o tabular soma.
    assert len(out["extracted_entities"]) == len(narrative) + len(table)


def test_is_honours_url_gating():
    assert is_honours_url(COPA_URL)
    assert is_honours_url("https://www.rsssf.org/tablesb/brazchamp.html")
    assert not is_honours_url("https://www.rsssf.org/index.html")
    assert not is_honours_url("https://pt.wikipedia.org/wiki/Botafogo_de_Futebol_e_Regatas")
    assert not is_honours_url("")


def test_miner_stashes_raw_html_only_for_whitelisted_urls():
    from src.miner.web_miner import WebMiner

    miner = WebMiner()
    html = "<html><body><p>texto</p></body></html>"
    data = miner.clean_html(html, source_url=COPA_URL)
    assert data.get("payload") is not None
    # clean_html sozinho NÃO anexa raw_html (só _mine_with_client faz isso).
    assert "raw_html" not in (data.get("payload") or {})
