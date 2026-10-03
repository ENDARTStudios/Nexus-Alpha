"""#048.10L — Dry-run OFFLINE da implementacao do next batch GEO (sem rede, sem worker).

Valida, sobre fixtures locais:
  * next batch (`tests/fixtures/geo_next_batch_parity_cases.json`): 5 estadios
    PT wiki + EN wiki + infobox + fallback OSM com `address.city` presente;
  * negativos do next batch (estado/bairro/pais/endereco/clube/pronome/cidade fora da allowlist);
  * regressao do lote atual (`tests/fixtures/geo_wiki_parity_cases.json`): 4/4 SAO PAULO intactos.

Compara chaves canonicas via o MESMO refinador do `/api/ingest` (`refine_triple_ex`).

Gera:
    reports/geo_next_batch_implementation_dry_run_048_10L.json
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

FIX_NEXT = ROOT / "tests" / "fixtures" / "geo_next_batch_parity_cases.json"
FIX_CURRENT = ROOT / "tests" / "fixtures" / "geo_wiki_parity_cases.json"
OUT = ROOT / "reports" / "geo_next_batch_implementation_dry_run_048_10L.json"

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search?format=json&addressdetails=1&limit=1&q={}"


def _key(t: dict, canon) -> str | None:
    r, _ = refine_triple_ex({**t, "confidence": t.get("confidence", 0.9)}, canon)
    return f"{r['subject']}|{r['predicate']}|{r['object']}" if r else None


def _osm_entry(subject: str, city: str) -> dict:
    return {
        "name": subject,
        "display_name": f"{subject}, {city}, Brazil",
        "address": {"city": city},
        "type": "stadium",
    }


def _evaluate_batch(fixtures: dict, canon, allow) -> tuple[list[dict], dict]:
    facts: list[dict] = []
    full = 0
    counts = {"osm": 0, "pt": 0, "en": 0, "infobox": 0}
    for case in fixtures["positives"]:
        subject = case["subject"]
        city = case["city"]
        osm = extract_geo_localizado_from_osm_json(
            [_osm_entry(subject, city)], NOMINATIM_URL, allow, expected_city=city
        )
        pt = extract_geo_localizado_from_wiki(case["pt_url"], case["pt_sentence"])
        en = extract_geo_localizado_from_wiki(case["en_url"], case["en_sentence"])
        box = extract_geo_localizado_from_wiki(case["pt_url"], "", case.get("infobox_html", ""))

        keys = {
            "osm": _key(osm[0], canon) if osm else None,
            "pt": _key(pt[0], canon) if pt else None,
            "en": _key(en[0], canon) if en else None,
            "infobox": _key(box[0], canon) if box else None,
        }
        for k, v in keys.items():
            counts[k] += 1 if v else 0
        ok = keys["osm"] and keys["osm"] == keys["pt"] == keys["en"] == keys["infobox"]
        if ok:
            full += 1
        facts.append({
            "fact": f"{subject} --LOCALIZADO_EM--> {city}",
            "expected_key": keys["osm"],
            "keys": keys,
            "collision_status": "full_collision" if ok else "no_collision",
        })

    negatives_rejected = 0
    negative_details = []
    for case in fixtures["negatives"]:
        rejected = extract_geo_localizado_from_wiki(case["url"], case["text"]) == []
        negatives_rejected += 1 if rejected else 0
        negative_details.append({"id": case["id"], "rejected": rejected})

    summary = {
        "expected_facts_total": len(fixtures["positives"]),
        "osm_canonical_triples": counts["osm"],
        "wiki_pt_canonical_triples": counts["pt"],
        "wiki_en_canonical_triples": counts["en"],
        "wiki_infobox_canonical_triples": counts["infobox"],
        "full_collision_facts": full,
        "canonical_key_mismatches": len(fixtures["positives"]) - full,
        "negatives_total": len(fixtures["negatives"]),
        "negatives_rejected": negatives_rejected,
        "forbidden_objects": len(fixtures["negatives"]) - negatives_rejected,
        "junk_objects": len(fixtures["negatives"]) - negatives_rejected,
    }
    return facts, {"summary": summary, "negatives": negative_details}


def main() -> int:
    canon = SemanticCanonicalizer()
    allow = default_geo_allowlist()
    next_fx = json.loads(FIX_NEXT.read_text(encoding="utf-8"))
    curr_fx = json.loads(FIX_CURRENT.read_text(encoding="utf-8"))

    next_facts, next_meta = _evaluate_batch(next_fx, canon, allow)
    curr_facts, curr_meta = _evaluate_batch(curr_fx, canon, allow)

    s = next_meta["summary"]
    c = curr_meta["summary"]
    gate = (
        s["expected_facts_total"] == 5
        and s["osm_canonical_triples"] == 5
        and s["wiki_pt_canonical_triples"] == 5
        and s["wiki_en_canonical_triples"] == 5
        and s["wiki_infobox_canonical_triples"] == 5
        and s["full_collision_facts"] == 5
        and s["canonical_key_mismatches"] == 0
        and s["negatives_rejected"] == s["negatives_total"]
        and c["full_collision_facts"] == 4
        and c["canonical_key_mismatches"] == 0
    )

    report = {
        "audit_id": "geo_next_batch_implementation_dry_run_048_10L",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "offline": True,
        "network_calls": 0,
        "worker_used": False,
        "neo4j_write": False,
        "qdrant_write": False,
        "next_batch": {**s, "facts": next_facts, "negatives": next_meta["negatives"]},
        "current_batch_regression": {**c, "facts": curr_facts},
        "predicted_new_verified": s["full_collision_facts"],
        "predicted_graph_scoped_gap": 0,
        "predicted_current_batch_verified": 15 + s["full_collision_facts"],
        "quorum": 3,
        "allowed_cities": ["SÃO PAULO", "RIO DE JANEIRO", "PORTO ALEGRE", "BELO HORIZONTE", "SALVADOR"],
        "homonym_state_city_allowlist": ["SAO PAULO", "RIO DE JANEIRO"],
        "top_invalid_predicates": [],
        "training_allowed": False,
    }
    report["gate_passed"] = bool(gate)
    report["classification"] = (
        "SUCCESS_048_10L_NEXT_BATCH_READY_FOR_WORKER" if gate else "PARTIAL_048_10L_NEXT_BATCH_EVIDENCE"
    )
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "next": s,
        "current_regression_full": c["full_collision_facts"],
        "gate_passed": report["gate_passed"],
        "classification": report["classification"],
    }, ensure_ascii=False, indent=2))
    for f in next_facts:
        print(f["fact"], "|", f["keys"], "|", f["collision_status"])
    print("WROTE", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
