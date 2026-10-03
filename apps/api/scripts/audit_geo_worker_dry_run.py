"""#048.10G.1 (refrescado em #048.10L.3) — dry-run OFFLINE do caminho GEO do worker.

Simula o roteamento do worker com o contrato atual de ``_split_geo_urls`` (3 vias:
Nominatim / wiki GEO / HTML) e o fetcher GEO ``(url, allowlist, expected_city)``.

Cobre lote atual (4) + next batch (5), Nominatim + wiki GEO, incluindo o fallback
source-scoped ``display_name_expected_context``. Sem rede, sem worker, sem escrita.

Gera ``reports/geo_worker_dry_run_048_10l_3.json``.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import scripts.worker_cycle as worker  # noqa: E402
from src.cognition.geo_extractor import (  # noqa: E402
    default_geo_allowlist,
    extract_geo_localizado_from_osm_json,
)
from src.miner.seed_loader import cluster_to_seeds, load_seed_clusters  # noqa: E402

OUT = ROOT / "reports" / "geo_worker_dry_run_048_10l_3.json"

ALLOW = default_geo_allowlist()

# (nome OSM/estadio, cidade esperada, url Nominatim, tem address.city?)
STADIUMS = {
    "ALLIANZ PARQUE": ("Allianz Parque", "São Paulo", "https://nominatim.openstreetmap.org/search?format=json&addressdetails=1&limit=1&q=Allianz%20Parque", True),
    "MORUMBI": ("Morumbi Stadium", "São Paulo", "https://nominatim.openstreetmap.org/search?format=json&addressdetails=1&limit=1&q=Estadio%20do%20Morumbi", True),
    "PACAEMBU": ("Pacaembu Stadium", "São Paulo", "https://nominatim.openstreetmap.org/search?format=json&addressdetails=1&limit=1&q=Estadio%20do%20Pacaembu", True),
    "NEO QUÍMICA ARENA": ("Neo Química Arena", "São Paulo", "https://nominatim.openstreetmap.org/search?format=json&addressdetails=1&limit=1&q=Neo%20Quimica%20Arena", True),
    "ESTÁDIO OLÍMPICO NILTON SANTOS": ("Estádio Olímpico Nilton Santos", "Rio de Janeiro", "https://nominatim.openstreetmap.org/search?format=json&addressdetails=1&limit=1&q=Est%C3%A1dio%20Ol%C3%ADmpico%20Nilton%20Santos", True),
    "MARACANÃ": ("Estádio do Maracanã", "Rio de Janeiro", "https://nominatim.openstreetmap.org/search?format=json&addressdetails=1&limit=1&q=Est%C3%A1dio%20do%20Maracan%C3%A3", True),
    "BEIRA-RIO": ("Estádio Beira-Rio", "Porto Alegre", "https://nominatim.openstreetmap.org/search?format=json&addressdetails=1&limit=1&q=Est%C3%A1dio%20Beira-Rio", False),
    "MINEIRÃO": ("Estádio Mineirão", "Belo Horizonte", "https://nominatim.openstreetmap.org/search?format=json&addressdetails=1&limit=1&q=Est%C3%A1dio%20Mineir%C3%A3o", False),
    "ARENA FONTE NOVA": ("Arena Fonte Nova", "Salvador", "https://nominatim.openstreetmap.org/search?format=json&addressdetails=1&limit=1&q=Arena%20Fonte%20Nova", True),
}

WIKI = {
    "ALLIANZ PARQUE": "https://pt.wikipedia.org/wiki/Allianz_Parque",
    "MORUMBI": "https://pt.wikipedia.org/wiki/Est%C3%A1dio_do_Morumbi",
    "PACAEMBU": "https://pt.wikipedia.org/wiki/Est%C3%A1dio_do_Pacaembu",
    "NEO QUÍMICA ARENA": "https://pt.wikipedia.org/wiki/Neo_Qu%C3%ADmica_Arena",
    "ESTÁDIO OLÍMPICO NILTON SANTOS": "https://pt.wikipedia.org/wiki/Est%C3%A1dio_Ol%C3%ADmpico_Nilton_Santos",
    "MARACANÃ": "https://pt.wikipedia.org/wiki/Est%C3%A1dio_do_Maracan%C3%A3",
    "BEIRA-RIO": "https://pt.wikipedia.org/wiki/Est%C3%A1dio_Beira-Rio",
    "MINEIRÃO": "https://pt.wikipedia.org/wiki/Est%C3%A1dio_Governador_Magalh%C3%A3es_Pinto",
    "ARENA FONTE NOVA": "https://pt.wikipedia.org/wiki/Arena_Fonte_Nova",
}

_NOMINATIM_BY_URL = {v[2]: k for k, v in STADIUMS.items()}
_WIKI_BY_URL = {v: k for k, v in WIKI.items()}


def _fake_fetcher(url, allow=None, expected_city=None):
    """Fetcher offline: resolve o estádio pela URL e devolve a tripla canônica."""
    allow = allow or ALLOW
    stadium = _NOMINATIM_BY_URL.get(url)
    if not stadium:
        return [], {"osm_json_parsed": 0, "geo_triples_raw": 0, "rejection_reasons": {"unknown_seed": 1}}
    name, city, _url, has_city = STADIUMS[stadium]
    entry = {
        "place_id": abs(hash(stadium)) % 10_000_000,
        "name": name,
        "namedetails": {"name": name},
        "class": "leisure",
        "type": "stadium",
        "display_name": f"{name}, {city}, Brazil",
        "address": ({"city": city, "state": city, "country": "Brazil"} if has_city else {"state": city, "country": "Brazil"}),
    }
    triples = extract_geo_localizado_from_osm_json([entry], url, allow, expected_city=expected_city)
    return triples, {"osm_json_parsed": 1, "geo_triples_raw": len(triples), "rejection_reasons": {}}


def build_report() -> dict:
    nominatim_urls = [v[2] for v in STADIUMS.values()]
    wiki_urls = list(WIKI.values())
    html_seed = "https://pt.wikipedia.org/wiki/Santos_FC"
    target_urls = nominatim_urls + wiki_urls + [html_seed]

    geo_urls, geo_wiki_urls, html_urls = worker._split_geo_urls(target_urls)
    payloads, telemetry = worker._build_geo_payloads(geo_urls, allowlist=ALLOW, fetcher=_fake_fetcher)
    wiki_payloads, wiki_telemetry = worker._build_geo_wiki_payloads(
        geo_wiki_urls,
        fetcher=lambda u: f"<p>O estádio está localizado em {STADIUMS[_WIKI_BY_URL[u]][1]}.</p>",
    )

    def _reject_osm(entry, expected):
        return extract_geo_localizado_from_osm_json([entry], "u", ALLOW, expected_city=expected) == []

    negatives_ok = (
        _reject_osm({"name": "X", "display_name": "X, Engenho de Dentro", "address": {"suburb": "Engenho de Dentro"}}, None)
        and _reject_osm({"name": "Estádio Beira-Rio", "display_name": "Estádio Beira-Rio, Rio Grande do Sul, Brazil", "address": {}}, "PORTO ALEGRE")
        and _reject_osm({"name": "Estádio Mineirão", "display_name": "Estádio Mineirão, Minas Gerais, Brazil", "address": {}}, "BELO HORIZONTE")
        and _reject_osm({"name": "Estádio Mineirão", "display_name": "Estádio Mineirão, Rio de Janeiro, Brazil", "address": {}}, "BELO HORIZONTE")
        and _reject_osm({"name": "Estádio Beira-Rio", "display_name": "Estádio Beira-Rio, Porto Alegre, Rio de Janeiro, Brazil", "address": {}}, "PORTO ALEGRE")
        and _reject_osm({"name": "Estádio Beira-Rio", "display_name": "Estádio Beira-Rio, Porto Alegre, Brazil", "address": {}, "class": "highway", "type": "residential"}, "PORTO ALEGRE")
    )

    active_seed_urls = len(cluster_to_seeds(load_seed_clusters(ROOT / "config" / "seed_clusters.yaml")))
    truncation_risk = worker.WORKER_TOP_K < len(worker.SEED_QUERIES) + active_seed_urls + 10

    report = {
        "audit_id": "geo_worker_dry_run_048_10l_3",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "offline": True,
        "split_three_way": True,
        "nominatim_urls_routed": len(geo_urls),
        "geo_wiki_urls_routed": len(geo_wiki_urls),
        "html_urls_routed": len(html_urls),
        "osm_json_parsed": telemetry["osm_json_parsed"],
        "geo_triples_raw": telemetry["geo_triples_raw"],
        "geo_triples_canonical": telemetry["geo_triples_canonical"],
        "wiki_geo_triples_canonical": wiki_telemetry["geo_wiki_triples_canonical"],
        "full_collision_facts_predicted": telemetry["geo_triples_canonical"],
        "rejection_reasons": telemetry["rejection_reasons"],
        "neighborhood_objects_rejected": negatives_ok,
        "state_objects_rejected": negatives_ok,
        "cross_city_rejected": negatives_ok,
        "non_venue_type_rejected": negatives_ok,
        "audit_stale": False,
        "worker_top_k": worker.WORKER_TOP_K,
        "active_seed_url_count": active_seed_urls,
        "truncation_risk": truncation_risk,
    }

    gate = (
        report["nominatim_urls_routed"] == len(STADIUMS)
        and report["geo_wiki_urls_routed"] == len(WIKI)
        and report["html_urls_routed"] == 1
        and report["full_collision_facts_predicted"] == len(STADIUMS)
        and report["wiki_geo_triples_canonical"] == len(WIKI)
        and negatives_ok
        and not truncation_risk
    )
    report["gate_passed"] = bool(gate)
    report["classification"] = (
        "SUCCESS_048_10L_3_WORKER_PATH_READY" if gate else "BLOCKED_048_10L_3_WORKER_PATH"
    )
    return report


def main() -> int:
    report = build_report()
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in (
        "nominatim_urls_routed", "geo_wiki_urls_routed", "html_urls_routed",
        "full_collision_facts_predicted", "wiki_geo_triples_canonical",
        "worker_top_k", "truncation_risk", "gate_passed", "classification")}, ensure_ascii=False, indent=2))
    print("WROTE", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
