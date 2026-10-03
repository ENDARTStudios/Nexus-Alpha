"""#048.10G.1 — testes do caminho GEO isolado no worker (sem rede)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scripts.worker_cycle as worker  # noqa: E402
from src.cognition.geo_extractor import fetch_and_extract_geo  # noqa: E402
from src.miner.seed_loader import cluster_to_seeds, load_seed_clusters  # noqa: E402

NOMINATIM = (
    "https://nominatim.openstreetmap.org/search?format=json&q=Allianz%20Parque"
    "&addressdetails=1&limit=1"
)
WIKI = "https://pt.wikipedia.org/wiki/Allianz_Parque"


def _fake_triple():
    return {
        "subject": "ALLIANZ PARQUE",
        "predicate": "LOCALIZADO_EM",
        "object": "SÃO PAULO",
        "metadata": {"license": "ODbL", "attribution": "(c) OpenStreetMap contributors"},
    }


# --- roteamento -------------------------------------------------------------


def test_split_routes_nominatim_and_geo_wiki_and_html():
    nominatim, geo_wiki, html = worker._split_geo_urls([NOMINATIM, WIKI, "https://pt.wikipedia.org/wiki/Santos_FC"])
    assert nominatim == [NOMINATIM]
    assert geo_wiki == [WIKI]
    assert html == ["https://pt.wikipedia.org/wiki/Santos_FC"]


def test_split_nominatim_without_format_json_is_html():
    nominatim, geo_wiki, html = worker._split_geo_urls(["https://nominatim.openstreetmap.org/search?q=x"])
    assert nominatim == []
    assert geo_wiki == []
    assert html


def test_split_non_allowlisted_json_is_html():
    nominatim, _, html = worker._split_geo_urls(["https://evil.example.com/search?format=json"])
    assert nominatim == []
    assert html


# --- build payloads ---------------------------------------------------------


def test_build_geo_payloads_with_fake_fetcher():
    def fake(url, allow, expected_city=None):
        return ([_fake_triple()], {"osm_json_parsed": 1, "geo_triples_raw": 1, "rejection_reasons": {}})

    payloads, telemetry = worker._build_geo_payloads([NOMINATIM], fetcher=fake)
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["source_url"] == NOMINATIM
    assert payload["extracted_entities"][0]["predicate"] == "LOCALIZADO_EM"
    assert 0.0 <= payload["extracted_entities"][0]["confidence"] <= 1.0
    assert payload["metadata"]["license"] == "ODbL"
    assert payload["metadata"]["publisher_family"] == "OpenStreetMap"
    assert telemetry["geo_triples_canonical"] == 1
    assert telemetry["osm_json_parsed"] == 1
    assert telemetry["osm_urls_seen"] == 1


def test_build_geo_payloads_default_rejects_non_geo_without_network():
    payloads, telemetry = worker._build_geo_payloads(["https://evil.example.com/search?format=json"])
    assert payloads == []
    assert telemetry["rejection_reasons"].get("not_geo_nominatim_url") == 1


def test_build_geo_wiki_payloads_uses_dedicated_parser():
    html = "<p>O Allianz Parque é um estádio de futebol localizado em São Paulo.</p>"
    payloads, telemetry = worker._build_geo_wiki_payloads([WIKI], fetcher=lambda url: html)
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["extracted_entities"][0]["predicate"] == "LOCALIZADO_EM"
    assert payload["extracted_entities"][0]["object"] == "SÃO PAULO"
    assert payload["extracted_entities"][0]["confidence"] > 0
    assert telemetry["generic_wiki_noise_suppressed"] is True


def test_build_geo_wiki_payloads_empty_html():
    payloads, _ = worker._build_geo_wiki_payloads([WIKI], fetcher=lambda url: "")
    assert payloads == []


def test_fetch_and_extract_geo_rejects_html_url_without_network():
    triples, telemetry = fetch_and_extract_geo(WIKI)
    assert triples == []
    assert telemetry["rejection_reasons"].get("not_geo_nominatim_url") == 1


# --- top_k guard ------------------------------------------------------------


def test_worker_top_k_is_seed_aware():
    seeds = len(cluster_to_seeds(load_seed_clusters(ROOT / "config" / "seed_clusters.yaml")))
    assert worker.WORKER_TOP_K >= len(worker.SEED_QUERIES) + seeds + 10
    assert worker.WORKER_TOP_K >= 64


# --- #048.10L.3: expected_city resolvido POR URL ---

BEIRA = "https://nominatim.openstreetmap.org/search?format=json&q=Est%C3%A1dio%20Beira-Rio"
WIKI_BEIRA = "https://pt.wikipedia.org/wiki/Est%C3%A1dio_Beira-Rio"


def test_build_geo_payloads_resolves_expected_city_per_url():
    seen = {}

    def fake(url, allow, expected_city=None):
        seen[url] = expected_city
        return ([_fake_triple()], {"osm_json_parsed": 1, "geo_triples_raw": 1, "rejection_reasons": {}})

    worker._build_geo_payloads([NOMINATIM, BEIRA], fetcher=fake)
    assert seen[NOMINATIM] == "SÃO PAULO"
    assert seen[BEIRA] == "PORTO ALEGRE"


def test_build_geo_wiki_payloads_passes_expected_city():
    captured = {}

    def parser(url, text, html, expected_city=None):
        captured[url] = expected_city
        return [{"subject": "BEIRA-RIO", "predicate": "LOCALIZADO_EM", "object": "PORTO ALEGRE",
                 "confidence": 0.9, "metadata": {}}]

    worker._build_geo_wiki_payloads([WIKI_BEIRA], parser=parser, fetcher=lambda u: "<html/>")
    assert captured[WIKI_BEIRA] == "PORTO ALEGRE"
