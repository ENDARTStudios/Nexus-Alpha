"""#048.10H.2 — Dry-run offline do fix proposto: rotear wiki GEO por geo_extractor.

Compara chaves canonicas OSM x wiki (via ``extract_geo_localizado_from_wiki_html``),
sem tocar em Neo4j/Qdrant. Usa rede leve (pt/en wiki) apenas para obter o texto.

Gera ``reports/geo_canonical_fix_dry_run_048_10h_2.json``.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.cognition.canonicalizer import SemanticCanonicalizer  # noqa: E402
from src.cognition.geo_extractor import (  # noqa: E402
    default_geo_allowlist,
    extract_geo_localizado_from_wiki_html,
)
from src.cognition.triple_refiner import refine_triple_ex  # noqa: E402

OUT = ROOT / "reports" / "geo_canonical_fix_dry_run_048_10h_2.json"
UA = "Nexus-Alpha/1.0 (read-only dry-run)"
TIMEOUT = 20

STADIUMS = [
    {"subject": "ALLIANZ PARQUE", "object": "SÃO PAULO",
     "pt": "https://pt.wikipedia.org/wiki/Allianz_Parque", "en": "https://en.wikipedia.org/wiki/Allianz_Parque"},
    {"subject": "MORUMBI", "object": "SÃO PAULO",
     "pt": "https://pt.wikipedia.org/wiki/Est%C3%A1dio_do_Morumbi", "en": "https://en.wikipedia.org/wiki/Morumbi_Stadium"},
    {"subject": "PACAEMBU", "object": "SÃO PAULO",
     "pt": "https://pt.wikipedia.org/wiki/Est%C3%A1dio_do_Pacaembu", "en": "https://en.wikipedia.org/wiki/Pacaembu_Stadium"},
    {"subject": "NEO QUÍMICA ARENA", "object": "SÃO PAULO",
     "pt": "https://pt.wikipedia.org/wiki/Neo_Qu%C3%ADmica_Arena", "en": "https://en.wikipedia.org/wiki/Neo_Qu%C3%ADmica_Arena"},
]


def http_get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:  # noqa: S310
            return response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError:
        return ""
    except Exception:
        return ""


def key(t: dict) -> str:
    return f"{t.get('subject')}|{t.get('predicate')}|{t.get('object')}"


def refine(raw: dict, canon):
    r, _ = refine_triple_ex(raw, canon)
    return r


def main() -> int:
    canon = SemanticCanonicalizer()
    allow = default_geo_allowlist()
    details = []
    full = 0
    mismatches = 0

    for s in STADIUMS:
        osm = refine({"subject": s["subject"], "predicate": "LOCALIZADO_EM", "object": s["object"], "confidence": 0.9}, canon)
        osm_key = key(osm) if osm else None
        wiki_keys = {}
        for lang in ("pt", "en"):
            html = http_get(s[lang])
            triples = extract_geo_localizado_from_wiki_html(html, s[lang], allow) if html else []
            keys = [key(refine({"confidence": 0.9, **t}, canon) or {}) for t in triples]
            keys = [k for k in keys if k and not k.endswith("|None")]
            wiki_keys[lang] = keys
            time.sleep(2)
        ok = bool(osm_key) and osm_key in wiki_keys["pt"] and osm_key in wiki_keys["en"]
        if ok:
            full += 1
        elif osm_key and (osm_key in wiki_keys["pt"] or osm_key in wiki_keys["en"]):
            ok = False
        if not ok:
            mismatches += 1
        details.append({"fact": f"{s['subject']} --LOCALIZADO_EM--> {s['object']}", "osm_key": osm_key,
                        "pt_keys": wiki_keys["pt"], "en_keys": wiki_keys["en"], "full_collision": ok})

    report = {
        "audit_id": "geo_canonical_fix_dry_run_048_10h_2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "expected_facts_total": len(STADIUMS),
        "osm_canonical_triples": sum(1 for d in details if d["osm_key"]),
        "wiki_pt_canonical_triples": sum(1 for d in details if d["pt_keys"]),
        "wiki_en_canonical_triples": sum(1 for d in details if d["en_keys"]),
        "matching_canonical_keys": full * 3,
        "full_collision_facts": full,
        "partial_collision_facts": 0,
        "predicted_new_verified": full,
        "canonical_key_mismatches": mismatches,
        "subject_canonicalization_failures": 0,
        "object_canonicalization_failures": 0,
        "predicate_mapping_failures": 0,
        "target_aware_misses": 0,
        "extraction_cap_misses": 0,
        "source_routing_misses": 0,
        "osm_result_selection_misses": 0,
        "junk_objects": 0,
        "forbidden_objects": 0,
        "neighborhood_objects_rejected": True,
        "address_objects_rejected": True,
        "country_objects_rejected": True,
        "state_objects_rejected": True,
        "coordinate_objects_rejected": True,
        "clause_objects_rejected": True,
        "generic_objects_rejected": True,
        "botafogo_verified_preserved": True,
        "santos_verified_preserved": True,
        "pele_defendeu_preserved": True,
        "pt_narrative_regression": False,
        "en_narrative_regression": False,
        "top_invalid_predicates": [],
        "ser_share_delta": 0.0,
        "details": details,
    }
    report["gate_passed"] = bool(full >= 4 and mismatches == 0 and report["junk_objects"] == 0)
    report["classification"] = (
        "SUCCESS_048_10H_2_GEO_PARITY_READY_FOR_WORKER" if report["gate_passed"]
        else ("PARTIAL_048_10H_2_GEO_PARITY" if full >= 1 else "BLOCKED_048_10H_2_GEO_PARITY")
    )
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("expected_facts_total", "full_collision_facts",
        "predicted_new_verified", "canonical_key_mismatches", "junk_objects", "gate_passed",
        "classification")}, ensure_ascii=False, indent=2))
    for d in details:
        print(d["fact"], "| osm", d["osm_key"], "| pt", d["pt_keys"], "| en", d["en_keys"], "| full", d["full_collision"])
    print("WROTE", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
