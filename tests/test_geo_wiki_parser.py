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


# --- #048.10L.3: expected_city source-scoped + rejeicao de infobox cross-city ---

MINEIRAO_PT = "https://pt.wikipedia.org/wiki/Est%C3%A1dio_Governador_Magalh%C3%A3es_Pinto"
BEIRA_PT = "https://pt.wikipedia.org/wiki/Est%C3%A1dio_Beira-Rio"


def test_mineirao_cross_city_sentence_rejected():
    triples = extract_geo_localizado_from_wiki(
        MINEIRAO_PT, "O Mineirão está localizado no Rio de Janeiro.", expected_city="BELO HORIZONTE")
    assert triples == []


def test_mineirao_cross_city_infobox_rejected():
    triples = extract_geo_localizado_from_wiki(
        MINEIRAO_PT, "", "<tr><th>Localização</th><td>Rio de Janeiro</td></tr>", expected_city="BELO HORIZONTE")
    assert triples == []


def test_mineirao_expected_city_accepted():
    triples = extract_geo_localizado_from_wiki(
        MINEIRAO_PT, "O Mineirão está localizado em Belo Horizonte.", expected_city="BELO HORIZONTE")
    assert len(triples) == 1 and triples[0]["object"] == "BELO HORIZONTE"
    assert triples[0]["subject"] == "MINEIRÃO"


def test_infobox_municipio_label_accepted():
    # #048.10L.4: infobox PT do Mineirão usa "Município de Belo Horizonte".
    html = "<tr><th>Município</th><td>Belo Horizonte</td></tr>"
    triples = extract_geo_localizado_from_wiki(MINEIRAO_PT, "", html, expected_city="BELO HORIZONTE")
    assert len(triples) == 1 and triples[0]["object"] == "BELO HORIZONTE"


def test_beira_rio_infobox_porto_alegre():
    triples = extract_geo_localizado_from_wiki(
        BEIRA_PT, "", "<tr><th>Cidade</th><td>Porto Alegre</td></tr>", expected_city="PORTO ALEGRE")
    assert len(triples) == 1 and triples[0]["object"] == "PORTO ALEGRE"
    assert triples[0]["subject"] == "BEIRA-RIO"


def test_ambiguous_infobox_expected_only():
    html = "<tr><th>Localização</th><td>Belo Horizonte</td></tr><tr><th>Outro</th><td>Rio de Janeiro</td></tr>"
    triples = extract_geo_localizado_from_wiki(MINEIRAO_PT, "", html, expected_city="BELO HORIZONTE")
    assert len(triples) == 1 and triples[0]["object"] == "BELO HORIZONTE"


def test_forbidden_infobox_labels_rejected():
    # Janela de localizacao contendo token proibido (address/owner/estado) -> rejeitada.
    for bad in ("Address: Belo Horizonte", "Owner: Mineirão", "Estado de Minas Gerais"):
        html = f"<tr><th>Location</th><td>{bad}</td></tr>"
        assert extract_geo_localizado_from_wiki(MINEIRAO_PT, "", html, expected_city="BELO HORIZONTE") == [], bad
