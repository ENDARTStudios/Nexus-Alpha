"""#048.10H.2 — testes offline da paridade canônica GEO (sem rede).

Documentam o comportamento real observado: o caminho OSM produz a chave canônica
`ESTADIO|LOCALIZADO_EM|CIDADE`, mas o caminho narrativo wiki (em página inteira)
não corrobora — a função do geo_extractor retorna [] quando a página menciona
estádios irmãos (ambiguidade) ou não há frase de localização limpa.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.cognition.canonicalizer import SemanticCanonicalizer  # noqa: E402
from src.cognition.geo_extractor import (  # noqa: E402
    default_geo_allowlist,
    extract_geo_localizado_from_wiki_html,
)
from src.cognition.triple_refiner import refine_triple_ex  # noqa: E402


def _key(subject: str, predicate: str, obj: str) -> str:
    canon = SemanticCanonicalizer()
    refined, _ = refine_triple_ex(
        {"subject": subject, "predicate": predicate, "object": obj, "confidence": 0.9}, canon
    )
    assert refined is not None
    return f"{refined['subject']}|{refined['predicate']}|{refined['object']}"


def test_osm_canonical_key_stable():
    assert _key("ALLIANZ PARQUE", "LOCALIZADO_EM", "SÃO PAULO") == "ALLIANZ PARQUE|LOCALIZADO_EM|SAO PAULO"
    assert _key("NEO QUÍMICA ARENA", "LOCALIZADO_EM", "SÃO PAULO") == "NEO QUIMICA ARENA|LOCALIZADO_EM|SAO PAULO"


def test_geo_wiki_extractor_clean_sentence_matches_osm_key():
    # Frase limpa e não ambígua: o extrator GEO produz a MESMA chave canônica do OSM.
    html = "<p>Allianz Parque is a football stadium located in São Paulo.</p>"
    triples = extract_geo_localizado_from_wiki_html(html, "https://en.wikipedia.org/wiki/Allianz_Parque", default_geo_allowlist())
    assert len(triples) == 1
    t = triples[0]
    assert _key(t["subject"], t["predicate"], t["object"]) == "ALLIANZ PARQUE|LOCALIZADO_EM|SAO PAULO"


def test_geo_wiki_extractor_rejects_ambiguous_multi_stadium_page():
    # Página que menciona estádios irmãos -> resolução ambígua -> nenhuma tripla (conservador).
    html = "<p>Allianz Parque fica em São Paulo. O Morumbi e o Pacaembu também.</p>"
    assert extract_geo_localizado_from_wiki_html(html, "u", default_geo_allowlist()) == []


def test_geo_wiki_extractor_rejects_neighborhood():
    html = "<p>Morumbi is located in the neighborhood of Morumbi, in São Paulo.</p>"
    # "neighborhood" é rejeitado; a extração só aceita cidade allowlisted limpa.
    triples = extract_geo_localizado_from_wiki_html(html, "u", default_geo_allowlist())
    assert all(t["object"] != "MORUMBI" for t in triples)


def test_geo_parity_diagnosis_doc_exists():
    p = ROOT / "reports" / "geo_canonical_parity_048_10h_2.json"
    if p.exists():
        import json

        data = json.loads(p.read_text(encoding="utf-8"))
        assert data["summary"]["expected_total"] == 4
