"""#048.10L — testes da implementacao do next batch GEO (offline, sem rede, sem worker)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.cognition.geo_extractor import (  # noqa: E402
    HOMONYM_STATE_CITY_ALLOWLIST,
    default_geo_allowlist,
    extract_geo_localizado_from_osm_json,
)
from src.cognition.geo_wiki_parser import (  # noqa: E402
    ALLOWED_CITIES,
    extract_geo_localizado_from_wiki,
)

FIX_NEXT = json.loads((ROOT / "tests" / "fixtures" / "geo_next_batch_parity_cases.json").read_text(encoding="utf-8"))
FIX_CURRENT = json.loads((ROOT / "tests" / "fixtures" / "geo_wiki_parity_cases.json").read_text(encoding="utf-8"))


def _osm_entry(subject: str, city: str) -> dict:
    return {"name": subject, "display_name": f"{subject}, {city}, Brazil", "address": {"city": city}, "type": "stadium"}


def test_allowed_cities_cover_next_batch():
    for city in ("SÃO PAULO", "RIO DE JANEIRO", "PORTO ALEGRE", "BELO HORIZONTE", "SALVADOR"):
        assert city in ALLOWED_CITIES.values()


def test_next_batch_positives_pt_en_infobox():
    for case in FIX_NEXT["positives"]:
        for url, text in ((case["pt_url"], case["pt_sentence"]), (case["en_url"], case["en_sentence"])):
            triples = extract_geo_localizado_from_wiki(url, text)
            assert len(triples) == 1, (case["id"], url, triples)
            t = triples[0]
            assert t["subject"] == case["subject"]
            assert t["predicate"] == "LOCALIZADO_EM"
            assert t["object"] == case["city"]
            assert 0.85 <= t["confidence"] <= 1.0
        infobox = extract_geo_localizado_from_wiki(case["pt_url"], "", case["infobox_html"])
        assert len(infobox) == 1, (case["id"], "infobox")
        assert infobox[0]["object"] == case["city"]


def test_next_batch_osm_with_structured_city():
    allow = default_geo_allowlist()
    for case in FIX_NEXT["positives"]:
        triples = extract_geo_localizado_from_osm_json(
            [_osm_entry(case["subject"], case["city"])],
            "https://nominatim.openstreetmap.org/search?format=json&addressdetails=1&limit=1&q=x",
            allow,
            expected_city=case["city"],
        )
        assert len(triples) == 1, (case["id"], triples)
        assert triples[0]["subject"] == case["subject"]
        assert triples[0]["object"] == case["city"]


def test_next_batch_negatives_rejected():
    for case in FIX_NEXT["negatives"]:
        assert extract_geo_localizado_from_wiki(case["url"], case["text"]) == [], case["id"]


def test_current_batch_regression():
    for case in FIX_CURRENT["positives"]:
        for url, text in ((case["pt_url"], case["pt_sentence"]), (case["en_url"], case["en_sentence"])):
            triples = extract_geo_localizado_from_wiki(url, text)
            assert len(triples) == 1, (case["id"], url, triples)
            assert triples[0]["subject"] == case["subject"]
            assert triples[0]["object"] == case["city"]


def test_rio_homonym_exception_is_source_scoped_only():
    assert "RIO DE JANEIRO" in HOMONYM_STATE_CITY_ALLOWLIST
    assert HOMONYM_STATE_CITY_ALLOWLIST["RIO DE JANEIRO"]["state"] == {"RIO DE JANEIRO"}
    assert "PORTO ALEGRE" not in HOMONYM_STATE_CITY_ALLOWLIST


def test_seed_clusters_next_batch_present_and_validated():
    data = yaml.safe_load((ROOT / "config" / "seed_clusters.yaml").read_text(encoding="utf-8"))
    clusters = {c["id"]: c for c in data.get("clusters", data if isinstance(data, list) else [])}
    expected = {
        "nilton_santos_localization": "RIO DE JANEIRO",
        "maracana_localization": "RIO DE JANEIRO",
        "beira_rio_localization": "PORTO ALEGRE",
        "mineirao_localization": "BELO HORIZONTE",
        "arena_fonte_nova_localization": "SALVADOR",
    }
    for cid, city in expected.items():
        assert cid in clusters, cid
        cluster = clusters[cid]
        assert cluster["expected_predicate"] == "LOCALIZADO_EM"
        assert len(cluster["sources"]) == 3
        domains = {s["domain"] for s in cluster["sources"]}
        assert {"pt.wikipedia.org", "en.wikipedia.org", "nominatim.openstreetmap.org"} <= domains
        for src in cluster["sources"]:
            assert "produtividade" not in src and src["productivity"] == "productive"
        assert city.lower() in cluster["topic"].lower()
