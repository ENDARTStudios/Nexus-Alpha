"""#048.10D Fase 2 — Atlas read-only de TERCEIRA família predical.

Famílias candidatas (não-VENCEU/DEFENDEU): CLUBE/ESTÁDIO --LOCALIZADO_EM-->
CIDADE; CLUBE --POSSUIR--> ESTÁDIO. Só elegível com colisão 3-domínios SEM junk
(cláusula/bairro/endereço/data/número/genérico). Read-only; nada grava Neo4j/Qdrant.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone
from urllib.parse import unquote

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, _HERE)

import httpx  # noqa: E402
from src.cognition.canonicalizer import SemanticCanonicalizer  # noqa: E402
from src.cognition.entity_linking_audit import assert_no_secret_markers  # noqa: E402
from src.cognition.extractor import EntityExtractor  # noqa: E402
from src.cognition.triple_refiner import refine_triple_ex  # noqa: E402
from src.miner.web_miner import WebMiner  # noqa: E402

AUDIT_ID = "third_predicate_family_atlas_048_10D"
P = "https://pt.wikipedia.org/wiki/"
E = "https://en.wikipedia.org/wiki/"

BANNED_OBJ = re.compile(r"\b(neighborhood|bairro|in the city|na cidade|endereço|street|avenue|rua|avenida)\b", re.I)

FAMILIES = [
    {
        "family_id": "club_located_in_city", "predicate": "LOCALIZADO_EM",
        "facts": [
            {"fact": "BOTAFOGO DE FUTEBOL E REGATAS --LOCALIZADO_EM--> RIO DE JANEIRO",
             "subj": ["BOTAFOGO"], "obj": ["RIO DE JANEIRO"],
             "urls": [P + "Botafogo_de_Futebol_e_Regatas", E + "Botafogo_de_Futebol_e_Regatas", P + "Rio_de_Janeiro", E + "Rio_de_Janeiro"]},
            {"fact": "SANTOS FUTEBOL CLUBE --LOCALIZADO_EM--> SANTOS",
             "subj": ["SANTOS"], "obj": ["SANTOS"], "urls": [P + "Santos_FC", E + "Santos_FC"]},
        ],
    },
    {
        "family_id": "stadium_located_in_city", "predicate": "LOCALIZADO_EM",
        "facts": [
            {"fact": "ESTÁDIO OLÍMPICO NILTON SANTOS --LOCALIZADO_EM--> RIO DE JANEIRO",
             "subj": ["NILTON SANTOS", "ENGENH"], "obj": ["RIO DE JANEIRO"],
             "urls": [P + "Est%C3%A1dio_Ol%C3%ADmpico_Nilton_Santos", E + "Est%C3%A1dio_Ol%C3%ADmpico_Nilton_Santos"]},
            {"fact": "ESTÁDIO URBANO CALDEIRA --LOCALIZADO_EM--> SANTOS",
             "subj": ["URBANO CALDEIRA", "VILA BELMIRO"], "obj": ["SANTOS"],
             "urls": [P + "Est%C3%A1dio_Urbano_Caldeira", E + "Est%C3%A1dio_Urbano_Caldeira"]},
        ],
    },
    {
        "family_id": "club_has_stadium", "predicate": "POSSUIR",
        "facts": [
            {"fact": "SANTOS FUTEBOL CLUBE --POSSUIR--> ESTÁDIO URBANO CALDEIRA",
             "subj": ["SANTOS"], "obj": ["URBANO CALDEIRA"],
             "urls": [P + "Santos_FC", E + "Santos_FC", P + "Est%C3%A1dio_Urbano_Caldeira"]},
            {"fact": "BOTAFOGO DE FUTEBOL E REGATAS --POSSUIR--> ESTÁDIO OLÍMPICO NILTON SANTOS",
             "subj": ["BOTAFOGO"], "obj": ["NILTON SANTOS"],
             "urls": [P + "Botafogo_de_Futebol_e_Regatas", E + "Botafogo_de_Futebol_e_Regatas", P + "Est%C3%A1dio_Ol%C3%ADmpico_Nilton_Santos"]},
        ],
    },
]


async def _fetch(url: str) -> dict:
    async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as c:
        try:
            r = await c.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200 and r.content:
                for enc in ("utf-8", "latin-1"):
                    try:
                        return {"status": 200, "text": r.content.decode(enc)}
                    except Exception:
                        continue
            return {"status": r.status_code, "text": "", "error": f"http_{r.status_code}"}
        except Exception as exc:
            return {"status": 0, "text": "", "error": type(exc).__name__}


def main() -> None:
    parser = argparse.ArgumentParser(description="#048.10D terceira família (read-only).")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    miner = WebMiner()
    canon = SemanticCanonicalizer()
    extractor = EntityExtractor(enable_fallback=True)

    all_urls = sorted({u for fam in FAMILIES for f in fam["facts"] for u in f["urls"]})
    fetched = asyncio.run(_run(all_urls))

    canon_by_url: dict[str, list[dict]] = {}
    for u in all_urls:
        text = (fetched.get(u) or {}).get("text") or ""
        cl: list[dict] = []
        if text:
            clean = miner.clean_html(text, source_url=u).get("content") or ""
            for t in extractor.extract(clean, max_triples=25):
                c, _r = refine_triple_ex(t.to_dict(), canon)
                if c is not None:
                    cl.append(c)
        canon_by_url[u] = cl

    families_out = []
    eligible_fams = 0
    full_total = 0
    for fam in FAMILIES:
        facts_out = []
        fam_ok = False
        for f in fam["facts"]:
            doms: set[str] = set()
            junk = 0
            for u in f["urls"]:
                for c in canon_by_url.get(u, []):
                    if str(c.get("predicate")).upper() != fam["predicate"]:
                        continue
                    s, o = str(c.get("subject", "")).upper(), str(c.get("object", "")).upper()
                    if any(t in s for t in f["subj"]) and any(t in o for t in f["obj"]) and not BANNED_OBJ.search(o):
                        doms.add(unquote(u).split("/")[2])
                        break
                    if any(t in s for t in f["subj"]) and any(t in o for t in f["obj"]):
                        junk += 1
            verified = len(doms) >= 3
            if verified:
                fam_ok = True
                full_total += 1
            facts_out.append({
                "fact": f["fact"], "predicted_domains": sorted(doms),
                "predicted_domain_count": len(doms), "junk_signals": junk,
                "collision_status": "full_collision" if verified else ("partial_collision" if len(doms) >= 2 else "no_collision"),
                "eligible_for_runtime": verified,
                "blocking_reason": None if verified else ("junk_signals" if junk else "dom<3"),
            })
        if fam_ok:
            eligible_fams += 1
        families_out.append({
            "family_id": fam["family_id"], "predicate": fam["predicate"],
            "candidate_facts": facts_out, "eligible_for_runtime": fam_ok,
            "blocking_reason": None if fam_ok else "sem colisao 3-dominios limpa",
        })

    payload = {
        "audit_id": AUDIT_ID, "generated_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True, "families": families_out,
        "summary": {
            "eligible_families": eligible_fams, "full_collision_facts": full_total,
            "predicted_new_verified": full_total, "predicted_unique_predicates": 2 + (1 if eligible_fams else 0),
            "recommended_next_step": "Fase 3 runtime 3a familia" if eligible_fams else "BLOCKED_THIRD_PREDICATE_FAMILY",
        },
    }
    assert_no_secret_markers(json.dumps(payload, ensure_ascii=False),
                             ("neodb://", "hf_", "sk-", "gsk_", "ghp_", "xoxb-", "AKIA"))
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    print(f"[{AUDIT_ID}] eligible_families={eligible_fams} full={full_total}")
    for fam in families_out:
        for f in fam["candidate_facts"]:
            print(f"  {fam['predicate']:14s} {f['collision_status']:16s} doms={f['predicted_domain_count']} junk={f['junk_signals']} | {f['fact'][:50]}")
    print(f"[salvo em] {args.out}")


async def _run(urls):
    return {u: await _fetch(u) for u in urls}


if __name__ == "__main__":
    main()
