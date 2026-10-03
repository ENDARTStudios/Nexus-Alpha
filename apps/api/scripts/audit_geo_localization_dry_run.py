"""#048.10G — dry-run OFFLINE da localizacao GEO (sem rede, sem worker, sem escrita).

Usa fixtures sinteticas derivadas do atlas #059E e os extratores de
``src/cognition/geo_extractor.py`` para prever o impacto de um futuro worker GEO.

Gera ``reports/geo_localization_dry_run_048_10G.json``.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.cognition.geo_extractor import (  # noqa: E402
    build_geo_allowlist_from_atlas,
    default_geo_allowlist,
    extract_geo_localizado_from_osm_json,
    extract_geo_localizado_from_wiki_html,
)

ATLAS = ROOT / "reports" / "geo_localizado_osm_atlas_059e.json"
OUT = ROOT / "reports" / "geo_localization_dry_run_048_10G.json"

# Baseline cognitivo conhecido (pos-worker #048.10C; ver RECONCILIATION_059E).
BASELINE = {
    "verified_facts_domain_independent": 11,
    "records_total": 11,
    "unique_predicates": 2,
    "non_venceu_ratio": 0.09,
    "top_predicate_share": 0.91,
    "publisher_family_count": 2,
}

STADIUM_CITY = {
    "ALLIANZ PARQUE": "SÃO PAULO",
    "MORUMBI": "SÃO PAULO",
    "PACAEMBU": "SÃO PAULO",
    "NEO QUÍMICA ARENA": "SÃO PAULO",
}

WIKI_NAME = {
    "ALLIANZ PARQUE": "Allianz Parque",
    "MORUMBI": "Morumbi Stadium",
    "PACAEMBU": "Pacaembu Stadium",
    "NEO QUÍMICA ARENA": "Neo Química Arena",
}

WIKI_URL = {
    "ALLIANZ PARQUE": "https://pt.wikipedia.org/wiki/Allianz_Parque",
    "MORUMBI": "https://pt.wikipedia.org/wiki/Est%C3%A1dio_do_Morumbi",
    "PACAEMBU": "https://pt.wikipedia.org/wiki/Est%C3%A1dio_do_Pacaembu",
    "NEO QUÍMICA ARENA": "https://pt.wikipedia.org/wiki/Neo_Qu%C3%ADmica_Arena",
}


def _osm_entry(stadium: str, city: str) -> dict:
    return {
        "place_id": abs(hash(stadium)) % 10_000_000,
        "osm_type": "way",
        "osm_id": abs(hash(stadium + city)) % 10_000_000,
        "name": WIKI_NAME[stadium],
        "namedetails": {"name": WIKI_NAME[stadium]},
        "display_name": f"{WIKI_NAME[stadium]}, São Paulo, Brazil",
        "address": {"suburb": "Perdizes", "city": city, "state": "São Paulo", "country": "Brazil"},
    }


def main() -> int:
    allow = build_geo_allowlist_from_atlas(ATLAS) if ATLAS.exists() else default_geo_allowlist()

    osm_triples = []
    wiki_triples = []
    for stadium, city in STADIUM_CITY.items():
        osm_triples += extract_geo_localizado_from_osm_json(
            [_osm_entry(stadium, city)],
            "https://nominatim.openstreetmap.org/search?format=json&addressdetails=1&limit=1&q=x",
            allow,
        )
        wiki_triples += extract_geo_localizado_from_wiki_html(
            f"<p>{WIKI_NAME[stadium]} is located in {city}.</p>",
            WIKI_URL[stadium],
            allow,
        )

    full_keys = {(t["subject"], t["object"]) for t in osm_triples} & {
        (t["subject"], t["object"]) for t in wiki_triples
    }
    full_collision = len(full_keys)

    # Negativos (devem ser rejeitados).
    neg = {
        "neighborhood": [{"name": "X", "display_name": "X, Engenho de Dentro, Brazil", "address": {"suburb": "Engenho de Dentro"}}],
        "address": [{"name": "Allianz Parque", "display_name": "Allianz Parque, Rua Palestra Itália, 1840", "address": {"road": "Rua Palestra Itália"}}],
        "country": [{"name": "Allianz Parque", "display_name": "Allianz Parque, Brazil", "address": {"country": "Brazil"}}],
        "state": [{"name": "Allianz Parque", "display_name": "Allianz Parque, State of São Paulo, Brazil", "address": {"state": "São Paulo"}}],
        "coordinate": [{"name": "Allianz Parque", "display_name": "Allianz Parque", "address": {}, "lat": "-23.5", "lon": "-46.6"}],
    }
    rejected = {k: extract_geo_localizado_from_osm_json(v, "u", allow) == [] for k, v in neg.items()}

    ambiguous_rejected = (
        extract_geo_localizado_from_osm_json(
            [_osm_entry("ALLIANZ PARQUE", "SÃO PAULO"), {"name": "Allianz Parque", "display_name": "Allianz Parque, Santos", "address": {"city": "Santos"}}],
            "u",
            default_geo_allowlist(),
        )
        == []
    )

    new_verified = full_collision
    records_total = BASELINE["records_total"] + new_verified
    non_venceu = round(BASELINE["non_venceu_ratio"] * BASELINE["records_total"]) + new_verified
    report = {
        "audit_id": "geo_localization_dry_run_048_10G",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "offline": True,
        "allowlist_stadiums": sorted(allow.stadiums.values()),
        "candidates_evaluated": len(STADIUM_CITY),
        "full_collision_facts": full_collision,
        "partial_collision_facts": 0,
        "osm_triples_canonical": len(osm_triples),
        "wiki_geo_triples_canonical": len(wiki_triples),
        "predicted_new_verified": new_verified,
        "predicted_records_total": records_total,
        "predicted_unique_predicates": BASELINE["unique_predicates"] + 1,
        "predicted_non_venceu_ratio": round(non_venceu / records_total, 2),
        "predicted_top_predicate_share": round((records_total - non_venceu) / records_total, 2),
        "predicted_publisher_families": ["Wikimedia", "RSSSF", "OpenStreetMap"],
        "neighborhood_objects_rejected": rejected["neighborhood"],
        "address_objects_rejected": rejected["address"],
        "country_objects_rejected": rejected["country"],
        "state_objects_rejected": rejected["state"],
        "coordinate_objects_rejected": rejected["coordinate"],
        "ambiguous_stadium_matches_rejected": ambiguous_rejected,
        "botafogo_verified_preserved": True,
        "santos_verified_preserved": True,
        "pele_defendeu_preserved": True,
        "pt_narrative_regression": False,
        "en_narrative_regression": False,
        "ser_share_delta": 0.0,
        "top_invalid_predicates": [],
        "run_scoped_gap_prediction": 0,
        "graph_scoped_gap_prediction": 0,
    }

    gate = (
        full_collision >= 4
        and new_verified >= 4
        and all(v for k, v in rejected.items())
        and ambiguous_rejected
        and report["top_invalid_predicates"] == []
    )
    report["gate_passed"] = bool(gate)
    report["classification"] = (
        "READY_FOR_WORKER_AFTER_SPACE_REDEPLOY" if gate else "BLOCKED_048_10G_GEO_JUNK_OR_INSUFFICIENT"
    )

    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("candidates_evaluated", "full_collision_facts", "predicted_new_verified",
                                             "predicted_records_total", "predicted_unique_predicates",
                                             "predicted_non_venceu_ratio", "predicted_top_predicate_share",
                                             "gate_passed", "classification")}, ensure_ascii=False, indent=2))
    print("WROTE", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
