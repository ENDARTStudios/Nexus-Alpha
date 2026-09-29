"""#048.10H.2.1 — testes do parser wiki GEO dedicado (offline, sem rede)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.cognition.geo_wiki_parser import (  # noqa: E402
    extract_geo_localizado_from_wiki,
    _is_geo_wiki_url,
    _pin_subject_by_url,
)

FIXTURES = json.loads((ROOT / "tests" / "fixtures" / "geo_wiki_parity_cases.json").read_text(encoding="utf-8"))


def test_url_allowlist_and_subject_pin():
    assert _is_geo_wiki_url("https://pt.wikipedia.org/wiki/Allianz_Parque")
    assert _is_geo_wiki_url("https://en.wikipedia.org/wiki/Morumbi_Stadium")
    assert not _is_geo_wiki_url("https://pt.wikipedia.org/wiki/Clube_de_Regatas_do_Flamengo")
    assert _pin_subject_by_url("https://pt.wikipedia.org/wiki/Neo_Qu%C3%ADmica_Arena") == "NEO QUÍMICA ARENA"


def test_positives_pt_en_infobox():
    for case in FIXTURES["positives"]:
        for url, text in ((case["pt_url"], case["pt_sentence"]), (case["en_url"], case["en_sentence"])):
            triples = extract_geo_localizado_from_wiki(url, text)
            assert len(triples) == 1, (case["id"], url, triples)
            t = triples[0]
            assert t["subject"] == case["subject"]
            assert t["predicate"] == "LOCALIZADO_EM"
            assert t["object"] == case["city"]
            assert 0.85 <= t["confidence"] <= 1.0
            assert t["metadata"]["extraction_method"] == "geo_wiki_dedicated_parser"
        infobox = extract_geo_localizado_from_wiki(case["pt_url"], "", case["infobox_html"])
        assert len(infobox) == 1, (case["id"], "infobox")
        assert infobox[0]["metadata"]["evidence_type"] == "infobox"


def test_negatives_rejected():
    for case in FIXTURES["negatives"]:
        assert extract_geo_localizado_from_wiki(case["url"], case["text"]) == [], case["id"]


def test_non_geo_url_returns_empty():
    assert extract_geo_localizado_from_wiki("https://pt.wikipedia.org/wiki/Clube_de_Regatas_do_Flamengo", "O Flamengo fica no Rio de Janeiro.") == []


def test_no_network_no_crash_on_empty():
    assert extract_geo_localizado_from_wiki("https://en.wikipedia.org/wiki/Allianz_Parque", "") == []
    assert extract_geo_localizado_from_wiki("", "Allianz Parque is located in São Paulo.") == []
