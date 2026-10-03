"""#048.10H.4 — testes do fallback OSM (alias Nubank + homonimo estado/cidade). Sem rede."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.cognition.geo_extractor import (  # noqa: E402
    default_geo_allowlist,
    extract_geo_localizado_from_osm_json,
)

URL = "https://nominatim.openstreetmap.org/search?format=json&q=Allianz%20Parque"


def _entry(**over):
    base = {"name": "Nubank Parque", "type": "stadium", "category": "leisure",
            "display_name": "Nubank Parque, Rua Palestra Itália, Perdizes, São Paulo, Brasil",
            "address": {"state": "São Paulo", "country": "Brasil"}}
    base.update(over)
    return base


def test_alias_nubank_parque_resolves_allianz():
    e = _entry(address={"city": "São Paulo", "state": "São Paulo", "country": "Brasil"})
    r = extract_geo_localizado_from_osm_json([e], URL, default_geo_allowlist(), expected_city="SÃO PAULO")
    assert len(r) == 1
    assert r[0]["subject"] == "ALLIANZ PARQUE"
    assert r[0]["object"] == "SÃO PAULO"


def test_homonym_state_city_exception_sao_paulo():
    r = extract_geo_localizado_from_osm_json([_entry()], URL, default_geo_allowlist(), expected_city="SÃO PAULO")
    assert len(r) == 1
    assert r[0]["object"] == "SÃO PAULO"
    assert r[0]["metadata"]["city_source"] == "homonym_state_city_exception"
    assert r[0]["confidence"] <= 0.85


def test_homonym_rejected_for_other_city():
    r = extract_geo_localizado_from_osm_json([_entry()], URL, default_geo_allowlist(), expected_city="RIO DE JANEIRO")
    assert r == []


def test_homonym_rejected_without_country():
    e = _entry(address={"state": "São Paulo", "country": "Portugal"})
    assert extract_geo_localizado_from_osm_json([e], URL, default_geo_allowlist(), expected_city="SÃO PAULO") == []


def test_homonym_rejected_without_expected_city():
    assert extract_geo_localizado_from_osm_json([_entry()], URL, default_geo_allowlist()) == []


# --- #048.10L.3: fallback source-scoped por fato (Porto Alegre / Belo Horizonte) ---

def _venue(name: str, display: str, **over) -> dict:
    base = {"name": name, "display_name": display, "class": "leisure", "type": "stadium", "address": {}}
    base.update(over)
    return base


def test_source_scoped_fallback_porto_alegre():
    e = _venue("Estádio Beira-Rio", "Estádio Beira-Rio, Porto Alegre, Brazil")
    r = extract_geo_localizado_from_osm_json([e], URL, default_geo_allowlist(), expected_city="PORTO ALEGRE")
    assert len(r) == 1 and r[0]["object"] == "PORTO ALEGRE"
    assert r[0]["metadata"]["city_source"] == "display_name_expected_context"


def test_source_scoped_fallback_belo_horizonte():
    e = _venue("Estádio Mineirão", "Estádio Mineirão, Belo Horizonte, Brazil")
    r = extract_geo_localizado_from_osm_json([e], URL, default_geo_allowlist(), expected_city="BELO HORIZONTE")
    assert len(r) == 1 and r[0]["object"] == "BELO HORIZONTE"


def test_source_scoped_rejects_state_only():
    assert extract_geo_localizado_from_osm_json(
        [_venue("Estádio Beira-Rio", "Estádio Beira-Rio, Rio Grande do Sul, Brazil")],
        URL, default_geo_allowlist(), expected_city="PORTO ALEGRE") == []
    assert extract_geo_localizado_from_osm_json(
        [_venue("Estádio Mineirão", "Estádio Mineirão, Minas Gerais, Brazil")],
        URL, default_geo_allowlist(), expected_city="BELO HORIZONTE") == []


def test_source_scoped_rejects_cross_city():
    assert extract_geo_localizado_from_osm_json(
        [_venue("Estádio Mineirão", "Estádio Mineirão, Rio de Janeiro, Brazil")],
        URL, default_geo_allowlist(), expected_city="BELO HORIZONTE") == []


def test_source_scoped_rejects_conflicting_second_city():
    assert extract_geo_localizado_from_osm_json(
        [_venue("Estádio Beira-Rio", "Estádio Beira-Rio, Porto Alegre, Rio de Janeiro, Brazil")],
        URL, default_geo_allowlist(), expected_city="PORTO ALEGRE") == []


def test_non_venue_type_rejected():
    e = _venue("Estádio Beira-Rio", "Estádio Beira-Rio, Porto Alegre, Brazil", **{"class": "highway", "type": "residential"})
    assert extract_geo_localizado_from_osm_json([e], URL, default_geo_allowlist(), expected_city="PORTO ALEGRE") == []


def test_structured_city_conflicting_with_expected_rejected():
    e = _venue("Estádio Mineirão", "Estádio Mineirão, Belo Horizonte, Brazil", address={"city": "Rio de Janeiro"})
    assert extract_geo_localizado_from_osm_json([e], URL, default_geo_allowlist(), expected_city="BELO HORIZONTE") == []
