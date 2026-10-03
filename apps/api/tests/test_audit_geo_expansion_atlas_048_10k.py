"""#048.10K — testes sintéticos do atlas de expansão GEO (sem rede)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_geo_expansion_atlas_048_10k import (  # noqa: E402
    build_next_batch_expected_facts,
    count_forbidden_predicates,
    evaluate_geo_candidate,
    match_city,
    nominatim_city,
    select_osm_result,
    wiki_location_city,
)

STADIUM = {"canon": "TEST STADIUM", "city": "RIO DE JANEIRO"}
ALIASES = ["test stadium"]


def _osm(name="Test Stadium", city="Rio de Janeiro", **addr):
    address = dict(addr)
    if city is not None:
        address["city"] = city
    return {"name": name, "category": "leisure", "type": "stadium", "address": address, "display_name": f"{name}, {city}"}


# --- match/nominatim --------------------------------------------------------


def test_match_city_accepts_allowlisted():
    assert match_city("Rio de Janeiro") == "RIO DE JANEIRO"
    assert match_city("Porto Alegre") == "PORTO ALEGRE"


def test_match_city_rejects_neighborhood_state_country():
    assert match_city("Engenho de Dentro") is None
    assert match_city("State of Rio de Janeiro") is None
    assert match_city("Brazil") is None


def test_nominatim_city_rejects_suburb_country_state():
    assert nominatim_city({"suburb": "Perdizes"}, "X, Perdizes")[0] is None
    assert nominatim_city({"country": "Brazil"}, "X, Brazil")[0] is None
    assert nominatim_city({"state": "São Paulo"}, "X, State of São Paulo")[0] is None


def test_nominatim_city_display_fallback():
    assert nominatim_city({"suburb": "Centro"}, "X, Salvador, Brazil")[0] == "SALVADOR"


# --- select_osm_result ------------------------------------------------------


def test_select_osm_result_single_stadium():
    entries = [_osm()]
    assert select_osm_result(entries, ALIASES) is entries[0]


def test_select_osm_result_ambiguous_cities():
    entries = [_osm(city="Rio de Janeiro"), _osm(city="Salvador")]
    assert select_osm_result(entries, ALIASES) is None


def test_select_osm_result_non_stadium_name():
    entries = [_osm(name="Rua Test Stadium")]
    assert select_osm_result(entries, ALIASES) is None


def test_select_osm_result_empty_or_invalid():
    assert select_osm_result([], ALIASES) is None
    assert select_osm_result(None, ALIASES) is None


# --- wiki -------------------------------------------------------------------


def test_wiki_clean_city():
    html = "<p>Test Stadium is a football stadium located in Rio de Janeiro, Brazil.</p>"
    assert wiki_location_city(html, ALIASES) == "RIO DE JANEIRO"


def test_wiki_rejects_neighborhood_only():
    html = "<p>The stadium is located in the neighborhood of Engenho de Dentro.</p>"
    assert wiki_location_city(html, ALIASES) is None


# --- evaluate ---------------------------------------------------------------


def test_evaluate_full_collision():
    pt = "<p>Test Stadium é um estádio localizado no Rio de Janeiro.</p>"
    en = "<p>Test Stadium is located in Rio de Janeiro.</p>"
    result = evaluate_geo_candidate(STADIUM, pt, en, _osm())
    assert result["collision_status"] == "full_collision"
    assert result["eligible_for_runtime"] is True
    assert result["predicted_domain_count"] == 3


def test_evaluate_partial_when_osm_missing():
    pt = "<p>Test Stadium é um estádio localizado no Rio de Janeiro.</p>"
    en = "<p>Test Stadium is located in Rio de Janeiro.</p>"
    result = evaluate_geo_candidate(STADIUM, pt, en, None)
    assert result["collision_status"] == "partial_collision"
    assert result["eligible_for_runtime"] is False


# --- forbidden predicates / registry ----------------------------------------


def test_forbidden_predicates_counted():
    facts = [{"predicate": "LOCALIZADO_EM"}, {"predicate": "SER"}]
    assert count_forbidden_predicates(facts, ["SER", "RESULTS"]) == 1


def test_build_next_batch_registry():
    full = {"stadium": "TEST STADIUM", "collision_status": "full_collision",
            "osm": {"resolved_city": "RIO DE JANEIRO"}, "wiki_sources": {"pt": "RIO DE JANEIRO", "en": "RIO DE JANEIRO"}}
    registry = build_next_batch_expected_facts([full])
    assert len(registry["expected_facts"]) == 1
    assert registry["expected_facts"][0]["object"] == "RIO DE JANEIRO"


def test_current_batch_registry_unchanged():
    current = ROOT / "reports" / "geo_expected_facts_048_10H.json"
    if current.exists():
        data = json.loads(current.read_text(encoding="utf-8"))
        assert len(data["expected_facts"]) == 4
