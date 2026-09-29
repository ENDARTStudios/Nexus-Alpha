"""#048.10H.2 — Diagnostico read-only da paridade canonica GEO (OSM vs wiki PT/EN).

Reproduz o caminho real: refino via ``refine_triple_ex`` (mesmo do /api/ingest) e
extracao narrativa via ``EntityExtractor``. Nao escreve em Neo4j/Qdrant.

Uso:
    python scripts/audit_geo_canonical_parity.py
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.cognition.canonicalizer import SemanticCanonicalizer  # noqa: E402
from src.cognition.extractor import EntityExtractor  # noqa: E402
from src.cognition.triple_refiner import refine_triple_ex  # noqa: E402

OUT = ROOT / "reports" / "geo_canonical_parity_048_10h_2.json"
UA = "Nexus-Alpha/1.0 (read-only parity audit)"
TIMEOUT = 20

STADIUMS = [
    {"fact": "ALLIANZ PARQUE --LOCALIZADO_EM--> SÃO PAULO", "subject": "ALLIANZ PARQUE", "object": "SÃO PAULO",
     "pt": "https://pt.wikipedia.org/wiki/Allianz_Parque", "en": "https://en.wikipedia.org/wiki/Allianz_Parque"},
    {"fact": "MORUMBI --LOCALIZADO_EM--> SÃO PAULO", "subject": "MORUMBI", "object": "SÃO PAULO",
     "pt": "https://pt.wikipedia.org/wiki/Est%C3%A1dio_do_Morumbi", "en": "https://en.wikipedia.org/wiki/Morumbi_Stadium"},
    {"fact": "PACAEMBU --LOCALIZADO_EM--> SÃO PAULO", "subject": "PACAEMBU", "object": "SÃO PAULO",
     "pt": "https://pt.wikipedia.org/wiki/Est%C3%A1dio_do_Pacaembu", "en": "https://en.wikipedia.org/wiki/Pacaembu_Stadium"},
    {"fact": "NEO QUÍMICA ARENA --LOCALIZADO_EM--> SÃO PAULO", "subject": "NEO QUÍMICA ARENA", "object": "SÃO PAULO",
     "pt": "https://pt.wikipedia.org/wiki/Neo_Qu%C3%ADmica_Arena", "en": "https://en.wikipedia.org/wiki/Neo_Qu%C3%ADmica_Arena"},
]

LOCATION_HINTS = [
    "localizado", "localizada", "situado", "situada", "fica em", "localiza-se",
    "located in", "situated in", "stadium in", "is in",
]


def http_get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:  # noqa: S310 (fixed host)
            return response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError:
        return ""
    except Exception:
        return ""


def clean_html(html: str) -> str:
    html = re.sub(r"(?is)<(script|style|table\.infobox).*?</\1>", " ", html or "")
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()


def canonical_key(t: dict) -> str:
    return f"{t.get('subject')}|{t.get('predicate')}|{t.get('object')}"


def refine(raw: dict, canon: SemanticCanonicalizer):
    refined, reason = refine_triple_ex(raw, canon)
    return refined, reason


def main() -> int:
    canon = SemanticCanonicalizer()
    extractor = EntityExtractor(enable_fallback=True)
    generated = datetime.now(timezone.utc).isoformat()

    facts = []
    summary = {
        "expected_total": len(STADIUMS),
        "osm_persisted_total": 0, "wiki_pt_canonical_total": 0, "wiki_en_canonical_total": 0,
        "full_collision_total": 0, "partial_collision_total": 0,
        "canonical_key_mismatches": 0, "predicate_mapping_failures": 0,
        "subject_canonicalization_failures": 0, "object_canonicalization_failures": 0,
        "target_aware_misses": 0, "extraction_cap_misses": 0, "source_routing_misses": 0,
        "junk_objects": 0, "forbidden_objects": 0, "root_causes": [],
    }

    for s in STADIUMS:
        osm_refined, osm_reason = refine(
            {"subject": s["subject"], "predicate": "LOCALIZADO_EM", "object": s["object"], "confidence": 0.9}, canon
        )
        osm_key = canonical_key(osm_refined) if osm_refined else None
        if osm_refined:
            summary["osm_persisted_total"] += 1

        wiki = {}
        for lang in ("pt", "en"):
            html = http_get(s[lang])
            text = clean_html(html)
            triples = extractor.extract(text) if text else []
            localizado = []
            for t in triples:
                d = t.to_dict()
                r, reason = refine(d, canon)
                if r and r.get("predicate") == "LOCALIZADO_EM":
                    localizado.append({"raw": d, "canonical": r, "key": canonical_key(r)})
            has_hint = any(h in text.lower() for h in LOCATION_HINTS)
            wiki[lang] = {
                "url": s[lang], "processed": bool(html), "text_len": len(text),
                "location_hint": has_hint, "total_triples": len(triples),
                "localizado_triples": localizado,
                "canonical_keys": [x["key"] for x in localizado],
            }
            if localizado:
                summary[f"wiki_{lang}_canonical_total"] += 1
            time.sleep(2)

        pt_keys = set(wiki["pt"]["canonical_keys"])
        en_keys = set(wiki["en"]["canonical_keys"])
        if osm_key and osm_key in pt_keys and osm_key in en_keys:
            status = "full_collision"
            summary["full_collision_total"] += 1
        elif osm_key and (osm_key in pt_keys or osm_key in en_keys):
            status = "partial_collision"
            summary["partial_collision_total"] += 1
        else:
            status = "no_collision"

        reasons = []
        if not osm_refined:
            reasons.append("R8_OSM_RESULT_SELECTION_MISS")
        if not wiki["pt"]["localizado_triples"] and not wiki["en"]["localizado_triples"]:
            reasons.append("R3_PREDICATE_MAPPING_FAILURE_OR_NO_LOCALIZADO")
        elif osm_key and osm_key not in pt_keys and osm_key not in en_keys:
            reasons.append("R1_R2_CANONICAL_KEY_MISMATCH")
        if not wiki["pt"]["processed"] or not wiki["en"]["processed"]:
            reasons.append("R7_SOURCE_ROUTING_MISS")
        for r in reasons:
            if r not in summary["root_causes"]:
                summary["root_causes"].append(r)

        facts.append({
            "fact": s["fact"],
            "canonical_key_expected": osm_key,
            "osm": {"persisted": bool(osm_refined), "canonical": osm_refined, "canonical_key": osm_key,
                    "reason": osm_reason, "domain": "nominatim.openstreetmap.org", "publisher_family": "OpenStreetMap"},
            "wiki_pt": wiki["pt"],
            "wiki_en": wiki["en"],
            "collision_status": status,
            "root_causes": reasons,
        })

    atlas = {"audit_id": "geo_canonical_parity_048_10h_2", "generated_at": generated,
             "expected_facts": facts, "summary": summary}
    OUT.write_text(json.dumps(atlas, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({**summary, "details": [
        {"fact": f["fact"], "osm_key": f["osm"]["canonical_key"],
         "pt_keys": f["wiki_pt"]["canonical_keys"], "en_keys": f["wiki_en"]["canonical_keys"],
         "pt_hint": f["wiki_pt"]["location_hint"], "en_hint": f["wiki_en"]["location_hint"],
         "pt_triples": f["wiki_pt"]["total_triples"], "en_triples": f["wiki_en"]["total_triples"],
         "status": f["collision_status"]} for f in facts]}, ensure_ascii=False, indent=2))
    print("WROTE", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
