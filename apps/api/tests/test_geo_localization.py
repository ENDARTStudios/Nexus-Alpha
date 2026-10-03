"""#048.10G - testes da extração GEO controlada (OSM/Nominatim + wiki). Sem rede."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.cognition.geo_extractor import (
    PREDICATE,
    build_geo_allowlist_from_atlas,
    default_geo_allowlist,
    extract_geo_localizado_from_osm_json,
    extract_geo_localizado_from_wiki_html,
    fetch_nominatim_json,
)

ROOT = Path(__file__).resolve().parents[1]
ALLOW = default_geo_allowlist()


def _osm(address: dict, name: str = "Allianz Parque", display: str | None = None) -> dict:
    return {
        "place_id": 123,
        "osm_type": "way",
        "osm_id": 456,
        "display_name": display or f"{name}, Rua Palestra Itália, Perdizes, Brazil",
        "name": name,
        "namedetails": {"name": name},
        "address": address,
    }


# --- OSM positivos ----------------------------------------------------------


def test_osm_allianz_parque_sao_paulo():
    triples = extract_geo_localizado_from_osm_json(
        [_osm({"suburb": "Perdizes", "city": "São Paulo", "state": "São Paulo", "country": "Brazil"})],
        "https://nominatim.openstreetmap.org/search?q=Allianz",
        ALLOW,
    )
    assert len(triples) == 1
    t = triples[0]
    assert t["subject"] == "ALLIANZ PARQUE"
    assert t["predicate"] == PREDICATE
    assert t["object"] == "SÃO PAULO"
    assert t["metadata"]["license"] == "ODbL"
    assert t["metadata"]["attribution"]
    assert t["metadata"]["city_tag_key"] == "address.city"


@pytest.mark.parametrize(
    "name,city",
    [("Morumbi", "São Paulo"), ("Pacaembu", "São Paulo"), ("Neo Química Arena", "São Paulo")],
)
def test_osm_other_stadiums(name, city):
    triples = extract_geo_localizado_from_osm_json(
        [_osm({"city": city, "state": "São Paulo", "country": "Brazil"}, name=name)],
        "https://nominatim.openstreetmap.org/search?q=x",
        ALLOW,
    )
    assert len(triples) == 1
    assert triples[0]["object"] == "SÃO PAULO"


# --- OSM negativos ----------------------------------------------------------


def test_osm_rejects_missing_city():
    assert extract_geo_localizado_from_osm_json(
        [_osm({"suburb": "Perdizes", "state": "São Paulo", "country": "Brazil"})], "u", ALLOW
    ) == []


def test_osm_rejects_suburb_only():
    assert extract_geo_localizado_from_osm_json([_osm({"suburb": "Perdizes"})], "u", ALLOW) == []


def test_osm_rejects_state_country_postcode():
    assert extract_geo_localizado_from_osm_json(
        [_osm({"state": "São Paulo", "country": "Brazil", "postcode": "05005-030"})], "u", ALLOW
    ) == []


def test_osm_rejects_non_stadium_poi():
    entry = _osm({"city": "São Paulo"})
    entry["name"] = "Rua Palestra Itália"
    entry["display_name"] = "Rua Palestra Itália, São Paulo, Brazil"
    entry["namedetails"] = {"name": "Rua Palestra Itália"}
    assert extract_geo_localizado_from_osm_json([entry], "u", ALLOW) == []


def test_osm_rejects_non_allowlisted_city():
    assert extract_geo_localizado_from_osm_json([_osm({"city": "Campinas"})], "u", ALLOW) == []


def test_osm_rejects_ambiguous_multiple_cities():
    entries = [
        _osm({"city": "São Paulo"}),
        _osm({"city": "Santos"}, display="Allianz Parque, Santos, Brazil"),
    ]
    assert extract_geo_localizado_from_osm_json(entries, "u", ALLOW) == []


def test_osm_rejects_invalid_and_empty_json():
    assert extract_geo_localizado_from_osm_json({}, "u", ALLOW) == []
    assert extract_geo_localizado_from_osm_json([], "u", ALLOW) == []
    assert extract_geo_localizado_from_osm_json("not-json", "u", ALLOW) == []


# --- Wiki positivos ---------------------------------------------------------


@pytest.mark.parametrize(
    "html",
    [
        "<p>Allianz Parque is located in São Paulo, Brazil.</p>",
        "<p>O Allianz Parque está localizado em São Paulo.</p>",
        "<p>Morumbi Stadium is situated in São Paulo.</p>",
        "<p>O Estádio do Morumbi fica em São Paulo.</p>",
    ],
)
def test_wiki_positive(html):
    triples = extract_geo_localizado_from_wiki_html(html, "https://pt.wikipedia.org/wiki/x", ALLOW)
    assert len(triples) == 1
    assert triples[0]["object"] == "SÃO PAULO"
    assert triples[0]["predicate"] == PREDICATE


# --- Wiki negativos ---------------------------------------------------------


def test_wiki_rejects_neighborhood_only():
    html = "<p>The stadium, in the neighbourhood of Engenho de Dentro, is old.</p>"
    assert extract_geo_localizado_from_wiki_html(html, "u", ALLOW) == []


def test_wiki_rejects_country_only():
    assert extract_geo_localizado_from_wiki_html("<p>Allianz Parque is located in Brazil.</p>", "u", ALLOW) == []


def test_wiki_rejects_without_stadium():
    assert extract_geo_localizado_from_wiki_html("<p>Uma cidade localizada em São Paulo.</p>", "u", ALLOW) == []


# --- fetch seguro -----------------------------------------------------------


def test_fetch_rejects_disallowed_host():
    with pytest.raises(ValueError):
        fetch_nominatim_json("https://evil.example.com/search?format=json")


def test_fetch_requires_format_json():
    with pytest.raises(ValueError):
        fetch_nominatim_json("https://nominatim.openstreetmap.org/search?q=x")


# --- allowlist from atlas ---------------------------------------------------


def test_build_allowlist_from_atlas():
    atlas = ROOT / "reports" / "geo_localizado_osm_atlas_059e.json"
    if not atlas.exists():
        pytest.skip("atlas #059E ausente")
    allow = build_geo_allowlist_from_atlas(atlas)
    triples = extract_geo_localizado_from_osm_json(
        [_osm({"city": "São Paulo"})], "https://nominatim.openstreetmap.org/search?format=json", allow
    )
    assert len(triples) == 1


def test_osm_extractor_does_not_write_graph():
    source = (ROOT / "src" / "cognition" / "geo_extractor.py").read_text(encoding="utf-8")
    for forbidden in ("from src.database", "get_graph_connector(", "get_vector_connector(", "import neo4j", "QdrantClient", '"/api/ingest"'):
        assert forbidden not in source


def test_osm_source_scoped_city_fallback():
    # Sem address.city; expected_city do cluster confirma a cidade esperada (source-scoped).
    entry = {"name": "Allianz Parque", "display_name": "Allianz Parque, Setor X, Campinas, Brazil", "address": {}}
    triples = extract_geo_localizado_from_osm_json(
        [entry], "https://nominatim.openstreetmap.org/search?format=json", default_geo_allowlist(), expected_city="CAMPINAS"
    )
    assert len(triples) == 1
    assert triples[0]["object"] == "CAMPINAS"
    assert triples[0]["metadata"]["city_tag_key"] == "display_name_expected_context"


def test_osm_no_fallback_without_expected_city():
    entry = {"name": "Allianz Parque", "display_name": "Allianz Parque, Setor X, Campinas, Brazil", "address": {}}
    triples = extract_geo_localizado_from_osm_json(
        [entry], "https://nominatim.openstreetmap.org/search?format=json", default_geo_allowlist()
    )
    assert triples == []
