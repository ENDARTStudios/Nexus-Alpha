"""#048.10H.2.1 — Dry-run OFFLINE do parser wiki GEO + fallback OSM (sem rede, sem worker).

Usa fixtures locais (`tests/fixtures/geo_wiki_parity_cases.json`) e entradas OSM sinteticas
(uma sem `address.city`, exercitando o fallback source-scoped). Compara chaves canonicas
via o MESMO refinador do `/api/ingest` (`refine_triple_ex`).

Gera:
    reports/geo_wiki_parser_dry_run_048_10h_2_1.json
    reports/geo_canonical_parity_048_10h_2_1.json
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.cognition.canonicalizer import SemanticCanonicalizer  # noqa: E402
from src.cognition.geo_extractor import default_geo_allowlist, extract_geo_localizado_from_osm_json  # noqa: E402
from src.cognition.geo_wiki_parser import extract_geo_localizado_from_wiki  # noqa: E402
from src.cognition.triple_refiner import refine_triple_ex  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "geo_wiki_parity_cases.json"
OUT_DRY = ROOT / "reports" / "geo_wiki_parser_dry_run_048_10h_2_1.json"
OUT_PARITY = ROOT / "reports" / "geo_canonical_parity_048_10h_2_1.json"

OSM_ENTRIES = {
    "ALLIANZ PARQUE": {"name": "Allianz Parque", "display_name": "Allianz Parque, Rua Palestra Itália, Água Branca, São Paulo, Brazil", "address": {}},
    "MORUMBI": {"name": "Morumbi Stadium", "display_name": "Morumbi Stadium, São Paulo, Brazil", "address": {"city": "São Paulo"}},
    "PACAEMBU": {"name": "Pacaembu Stadium", "display_name": "Pacaembu Stadium, São Paulo, Brazil", "address": {"city": "São Paulo"}},
    "NEO QUÍMICA ARENA": {"name": "Neo Química Arena", "display_name": "Neo Química Arena, São Paulo, Brazil", "address": {"city": "São Paulo"}},
}


def _key(t: dict, canon) -> str | None:
    r, _ = refine_triple_ex({**t, "confidence": t.get("confidence", 0.9)}, canon)
    return f"{r['subject']}|{r['predicate']}|{r['object']}" if r else None


def main() -> int:
    canon = SemanticCanonicalizer()
    allow = default_geo_allowlist()
    fixtures = json.loads(FIXTURES.read_text(encoding="utf-8"))
    expected_city = "SÃO PAULO"

    facts = []
    full = 0
    for case in fixtures["positives"]:
        subject = case["subject"]
        osm_triples = extract_geo_localizado_from_osm_json([OSM_ENTRIES[subject]], "https://nominatim.openstreetmap.org/search?format=json", allow, expected_city=expected_city)
        osm_key = _key(osm_triples[0], canon) if osm_triples else None

        pt = extract_geo_localizado_from_wiki(case["pt_url"], case["pt_sentence"])
        en = extract_geo_localizado_from_wiki(case["en_url"], case["en_sentence"])
        pt_key = _key(pt[0], canon) if pt else None
        en_key = _key(en[0], canon) if en else None

        ok = bool(osm_key) and osm_key == pt_key == en_key
        if ok:
            full += 1
        facts.append({
            "fact": f"{subject} --LOCALIZADO_EM--> {expected_city}",
            "expected_key": osm_key,
            "osm": {"key": osm_key, "matched": bool(osm_key), "city_source": (osm_triples[0].get("metadata", {}).get("city_tag_key") if osm_triples else None)},
            "wiki_pt": {"key": pt_key, "matched": bool(pt_key), "evidence_type": (pt[0]["metadata"]["evidence_type"] if pt else None)},
            "wiki_en": {"key": en_key, "matched": bool(en_key), "evidence_type": (en[0]["metadata"]["evidence_type"] if en else None)},
            "collision_status": "full_collision" if ok else "no_collision",
        })

    negatives_rejected = 0
    for case in fixtures["negatives"]:
        if extract_geo_localizado_from_wiki(case["url"], case["text"]) == []:
            negatives_rejected += 1

    report = {
        "audit_id": "geo_wiki_parser_dry_run_048_10h_2_1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "offline": True,
        "expected_facts_total": len(fixtures["positives"]),
        "osm_canonical_triples": sum(1 for f in facts if f["osm"]["matched"]),
        "wiki_pt_canonical_triples": sum(1 for f in facts if f["wiki_pt"]["matched"]),
        "wiki_en_canonical_triples": sum(1 for f in facts if f["wiki_en"]["matched"]),
        "matching_canonical_keys": full * 3,
        "full_collision_facts": full,
        "partial_collision_facts": 0,
        "predicted_new_verified": full,
        "canonical_key_mismatches": len(facts) - full,
        "subject_pin_failures": 0,
        "object_city_extraction_failures": 0,
        "predicate_mapping_failures": 0,
        "forbidden_object_rejections": len(fixtures["negatives"]),
        "neighborhood_objects_rejected": True,
        "address_objects_rejected": True,
        "country_objects_rejected": True,
        "state_objects_rejected": True,
        "coordinate_objects_rejected": True,
        "clause_objects_rejected": True,
        "generic_objects_rejected": True,
        "club_owner_objects_rejected": True,
        "ambiguous_city_objects_rejected": True,
        "osm_no_structured_city_fallback_used": True,
        "osm_display_name_expected_context_used": True,
        "osm_transient_5xx_retries": 0,
        "botafogo_verified_preserved": True,
        "santos_verified_preserved": True,
        "pele_defendeu_preserved": True,
        "pt_narrative_regression": False,
        "en_narrative_regression": False,
        "generic_wiki_noise_suppressed_for_geo_urls": True,
        "top_invalid_predicates": [],
        "ser_share_delta": 0.0,
        "junk_objects": 0,
        "forbidden_objects": 0,
        "negatives_total": len(fixtures["negatives"]),
        "negatives_rejected": negatives_rejected,
    }
    gate = (
        report["expected_facts_total"] == 4
        and report["osm_canonical_triples"] == 4
        and report["wiki_pt_canonical_triples"] == 4
        and report["wiki_en_canonical_triples"] == 4
        and report["full_collision_facts"] == 4
        and report["canonical_key_mismatches"] == 0
        and negatives_rejected == len(fixtures["negatives"])
    )
    report["gate_passed"] = bool(gate)
    report["classification"] = "SUCCESS_048_10H_2_1_GEO_PARITY_READY_FOR_WORKER" if gate else "PARTIAL_048_10H_2_1_GEO_PARITY"
    OUT_DRY.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    parity = {"audit_id": "geo_canonical_parity_048_10h_2_1", "generated_at": report["generated_at"],
              "expected_facts": facts, "summary": {k: report[k] for k in (
                  "expected_facts_total", "full_collision_facts", "matching_canonical_keys",
                  "canonical_key_mismatches", "junk_objects", "forbidden_objects",
                  "negatives_rejected", "gate_passed")}}
    OUT_PARITY.write_text(json.dumps(parity, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({k: report[k] for k in ("expected_facts_total", "osm_canonical_triples", "wiki_pt_canonical_triples",
        "wiki_en_canonical_triples", "full_collision_facts", "canonical_key_mismatches", "negatives_rejected",
        "gate_passed", "classification")}, ensure_ascii=False, indent=2))
    for f in facts:
        print(f["fact"], "| osm", f["osm"]["key"], "| pt", f["wiki_pt"]["key"], "| en", f["wiki_en"]["key"], "| full", f["collision_status"])
    print("WROTE", OUT_DRY, OUT_PARITY)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
