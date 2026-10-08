"""#058.12.1 — política de extração por fonte (table-only vs narrativa).

Sem rede: payloads sintéticos + fixture RSSSF inline.
"""
from src.cognition.extractor import EntityExtractor
from src.cognition.table_extractor import (
    POLICY_NARRATIVE_DEFAULT,
    POLICY_NARRATIVE_PLUS_TABLE,
    POLICY_TABLE_ONLY,
    enrich_payload_with_tables,
    source_policy,
)

COPA_URL = "https://www.rsssf.org/sacups/copalib.html"
WIKI_URL = "https://pt.wikipedia.org/wiki/Garrincha"
OTHER_URL = "https://example.com/article"

RSSSF_PRE = """
<html><body><pre>
2024 Botafogo
</pre></body></html>
"""


def _junk_narrative_payload(url: str) -> dict:
    # Texto que a narrativa converte em SER junk (fallback: copula PT).
    return {
        "source_url": url,
        "title": "t",
        "content": "Copa de Campeones é held in Santiago. A parte é given to the author.",
        "extracted_entities": [],
    }


def test_source_policy_modes():
    assert source_policy(COPA_URL) == POLICY_TABLE_ONLY
    assert source_policy("https://rsssf.org/x") == POLICY_TABLE_ONLY
    assert source_policy(WIKI_URL) == POLICY_NARRATIVE_PLUS_TABLE
    assert source_policy("https://en.wikipedia.org/wiki/X") == POLICY_NARRATIVE_PLUS_TABLE
    assert source_policy(OTHER_URL) == POLICY_NARRATIVE_DEFAULT
    assert source_policy("") == POLICY_NARRATIVE_DEFAULT


def test_table_only_suppresses_narrative_junk():
    extractor = EntityExtractor()
    payload = _junk_narrative_payload(COPA_URL)
    before = dict(extractor.rejection_reasons)
    out = extractor.enrich_payload(payload)
    assert out["extracted_entities"] == []
    suppressed = extractor.rejection_reasons.get("narrative_suppressed_table_only_source", 0)
    assert suppressed > before.get("narrative_suppressed_table_only_source", 0)


def test_table_only_keeps_controlled_table_triple():
    from src.cognition.canonicalizer import SemanticCanonicalizer

    payload = _junk_narrative_payload(COPA_URL)
    payload["raw_html"] = RSSSF_PRE
    stats = enrich_payload_with_tables(payload, SemanticCanonicalizer())
    assert stats["emitted"] == 1
    table = [t for t in payload["extracted_entities"] if t.get("predicate") == "VENCEU"]
    assert len(table) == 1
    assert table[0]["subject"] == "BOTAFOGO DE FUTEBOL E REGATAS"
    assert table[0]["object"] == "COPA LIBERTADORES"


def test_wiki_narrative_not_suppressed():
    extractor = EntityExtractor()
    payload = {
        "source_url": WIKI_URL,
        "title": "t",
        "content": "Garrincha played for Botafogo for 12 years.",
        "extracted_entities": [
            {"subject": "Garrincha", "predicate": "DEFENDEU",
             "object": "Botafogo de Futebol e Regatas", "confidence": 0.8}
        ],
    }
    # enrich_payload re-extrai do content; o ponto é: nada suprimido por política.
    before = extractor.rejection_reasons.get("narrative_suppressed_table_only_source", 0)
    _out = extractor.enrich_payload(payload)
    after = extractor.rejection_reasons.get("narrative_suppressed_table_only_source", 0)
    assert after == before


def test_wiki_table_path_stays_gated_until_phase_c():
    # Wiki ainda NÃO está na whitelist tabular: raw_html wiki não gera VENCEU.
    from src.cognition.canonicalizer import SemanticCanonicalizer

    payload = _junk_narrative_payload(WIKI_URL)
    payload["raw_html"] = RSSSF_PRE
    stats = enrich_payload_with_tables(payload, SemanticCanonicalizer())
    assert stats["emitted"] == 0
    assert stats["skipped_not_whitelisted"] == 1


def test_default_domain_unchanged():
    extractor = EntityExtractor()
    payload = _junk_narrative_payload(OTHER_URL)
    before = extractor.rejection_reasons.get("narrative_suppressed_table_only_source", 0)
    extractor.enrich_payload(payload)
    after = extractor.rejection_reasons.get("narrative_suppressed_table_only_source", 0)
    assert after == before


def test_suppression_metric_increments_per_triple():
    extractor = EntityExtractor()
    payload = _junk_narrative_payload(COPA_URL)
    # conta quantas a narrativa geraria sem política
    narrative_count = len(extractor.extract(payload["content"]))
    before = extractor.rejection_reasons.get("narrative_suppressed_table_only_source", 0)
    extractor.enrich_payload(payload)
    after = extractor.rejection_reasons.get("narrative_suppressed_table_only_source", 0)
    assert after - before == narrative_count
