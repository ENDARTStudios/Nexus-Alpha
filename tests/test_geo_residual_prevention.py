"""#048.10L.5 — prevenção de recriação do resíduo GEO MINEIRAO -> RIO DE JANEIRO."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.cognition.geo_extractor import (  # noqa: E402
    extract_geo_localizado_from_osm_json,
    resolve_expected_geo_city,
)
from src.cognition.geo_wiki_parser import extract_geo_localizado_from_wiki  # noqa: E402

MINEIRAO_PT = "https://pt.wikipedia.org/wiki/Est%C3%A1dio_Governador_Magalh%C3%A3es_Pinto"


def _is_wrong_rio(triples: list[dict]) -> bool:
    return any(
        t["predicate"] == "LOCALIZADO_EM" and "MINEIRA" in t["subject"].upper() and t["object"].upper() == "RIO DE JANEIRO"
        for t in triples
    )


def test_expected_city_for_mineirao_is_belo_horizonte():
    assert resolve_expected_geo_city(MINEIRAO_PT) == "BELO HORIZONTE"


def test_mineirao_infobox_rio_rejected():
    html = "<tr><th>Localização</th><td>Rio de Janeiro</td></tr>"
    assert not _is_wrong_rio(extract_geo_localizado_from_wiki(MINEIRAO_PT, "", html, expected_city="BELO HORIZONTE"))


def test_mineirao_sentence_rio_rejected():
    text = "O Mineirão está localizado no Rio de Janeiro."
    assert not _is_wrong_rio(extract_geo_localizado_from_wiki(MINEIRAO_PT, text, expected_city="BELO HORIZONTE"))


def test_mineirao_municipio_label_belo_horizonte_accepted():
    html = "<tr><th>Município</th><td>Belo Horizonte</td></tr>"
    triples = extract_geo_localizado_from_wiki(MINEIRAO_PT, "", html, expected_city="BELO HORIZONTE")
    assert len(triples) == 1 and triples[0]["object"] == "BELO HORIZONTE"


def test_mineirao_osm_cross_city_rejected():
    entry = {"name": "Estádio Mineirão", "display_name": "Estádio Mineirão, Rio de Janeiro, Brazil",
             "address": {"city": "Rio de Janeiro"}, "class": "leisure", "type": "stadium"}
    from src.cognition.geo_extractor import default_geo_allowlist

    assert extract_geo_localizado_from_osm_json([entry], "u", default_geo_allowlist(), expected_city="BELO HORIZONTE") == []
