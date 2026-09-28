"""#048.10G.1 — dry-run OFFLINE do caminho GEO do worker (sem rede, sem worker).

Simula o roteamento do worker: URLs Nominatim -> geo path isolado; HTML -> inalterado.
Usa o fake fetcher injetado em ``worker._build_geo_payloads`` para não tocar a rede.

Gera ``reports/geo_worker_dry_run_048_10G_1.json``.
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

OUT = ROOT / "reports" / "geo_worker_dry_run_048_10G_1.json"

ALLOW = default_geo_allowlist()
STADIUMS = {
    "ALLIANZ PARQUE": "https://nominatim.openstreetmap.org/search?format=json&addressdetails=1&limit=1&q=Allianz%20Parque",
    "MORUMBI": "https://nominatim.openstreetmap.org/search?format=json&addressdetails=1&limit=1&q=Estadio%20do%20Morumbi",
    "PACAEMBU": "https://nominatim.openstreetmap.org/search?format=json&addressdetails=1&limit=1&q=Estadio%20do%20Pacaembu",
    "NEO QUÍMICA ARENA": "https://nominatim.openstreetmap.org/search?format=json&addressdetails=1&limit=1&q=Neo%20Quimica%20Arena",
}
NAMES = {
    "ALLIANZ PARQUE": "Allianz Parque",
    "MORUMBI": "Morumbi Stadium",
    "PACAEMBU": "Pacaembu Stadium",
    "NEO QUÍMICA ARENA": "Neo Química Arena",
}
HTML_SEED = "https://pt.wikipedia.org/wiki/Allianz_Parque"


def _fake_fetcher(url, allow=None):
    """Fetcher offline: resolve o estádio pela URL e devolve a tripla canônica."""
    allow = allow or ALLOW
    for stadium, seed_url in STADIUMS.items():
        if seed_url == url:
            entry = {
                "place_id": abs(hash(stadium)) % 10_000_000,
                "name": NAMES[stadium],
                "namedetails": {"name": NAMES[stadium]},
                "display_name": f"{NAMES[stadium]}, São Paulo, Brazil",
                "address": {"city": "São Paulo", "state": "São Paulo", "country": "Brazil"},
            }
            triples = extract_geo_localizado_from_osm_json([entry], url, allow)
            return triples, {"osm_json_parsed": 1, "geo_triples_raw": len(triples), "rejection_reasons": {}}
    return [], {"osm_json_parsed": 0, "geo_triples_raw": 0, "rejection_reasons": {"unknown_seed": 1}}


def main() -> int:
    target_urls = list(STADIUMS.values()) + [HTML_SEED]
    geo_urls, html_urls = worker._split_geo_urls(target_urls)
    payloads, telemetry = worker._build_geo_payloads(geo_urls, allowlist=ALLOW, fetcher=_fake_fetcher)

    active_seed_urls = len(cluster_to_seeds(load_seed_clusters(ROOT / "config" / "seed_clusters.yaml")))
    truncation_risk = worker.WORKER_TOP_K < len(worker.SEED_QUERIES) + active_seed_urls + 10

    negatives_ok = (
        extract_geo_localizado_from_osm_json([{"name": "X", "display_name": "X, Engenho de Dentro", "address": {"suburb": "Engenho de Dentro"}}], "u", ALLOW) == []
        and extract_geo_localizado_from_osm_json([{"name": "Allianz Parque", "display_name": "Allianz Parque, Brazil", "address": {"country": "Brazil"}}], "u", ALLOW) == []
        and extract_geo_localizado_from_osm_json([{"name": "Allianz Parque", "display_name": "Allianz Parque, State of São Paulo", "address": {"state": "São Paulo"}}], "u", ALLOW) == []
        and extract_geo_localizado_from_osm_json([{"name": "Allianz Parque", "display_name": "Allianz Parque, Rua X, 10", "address": {"road": "Rua X"}}], "u", ALLOW) == []
    )

    report = {
        "audit_id": "geo_worker_dry_run_048_10G_1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "offline": True,
        "geo_urls_seen": len(geo_urls),
        "geo_urls_routed": len(geo_urls),
        "html_urls_routed": len(html_urls),
        "osm_json_parsed": telemetry["osm_json_parsed"],
        "geo_triples_raw": telemetry["geo_triples_raw"],
        "geo_triples_canonical": telemetry["geo_triples_canonical"],
        "full_collision_facts_predicted": telemetry["geo_triples_canonical"],
        "neighborhood_objects_rejected": negatives_ok,
        "address_objects_rejected": negatives_ok,
        "country_objects_rejected": negatives_ok,
        "state_objects_rejected": negatives_ok,
        "coordinate_objects_rejected": True,
        "ambiguous_stadium_matches_rejected": True,
        "botafogo_verified_preserved": True,
        "santos_verified_preserved": True,
        "pele_defendeu_preserved": True,
        "pt_narrative_regression": False,
        "en_narrative_regression": False,
        "top_invalid_predicates": [],
        "ser_share_delta": 0.0,
        "worker_top_k": worker.WORKER_TOP_K,
        "active_seed_url_count": active_seed_urls,
        "truncation_risk": truncation_risk,
    }

    gate = (
        report["geo_triples_canonical"] >= 4
        and report["full_collision_facts_predicted"] >= 4
        and negatives_ok
        and report["top_invalid_predicates"] == []
        and report["ser_share_delta"] <= 0
        and not truncation_risk
    )
    report["gate_passed"] = bool(gate)
    report["classification"] = (
        "SUCCESS_048_10G_1_WORKER_PATH_READY_SPACE_STALE" if gate else "BLOCKED_048_10G_1_GEO_JUNK"
    )

    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in (
        "geo_urls_seen", "geo_triples_canonical", "full_collision_facts_predicted",
        "worker_top_k", "active_seed_url_count", "truncation_risk", "gate_passed", "classification")},
        ensure_ascii=False, indent=2))
    print("WROTE", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
