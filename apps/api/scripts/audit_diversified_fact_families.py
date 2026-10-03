"""#048.10 Fase 0 — Atlas read-only de famílias de fatos diversificadas.

Testa colisão de chave canônica entre domínios independentes para famílias
NÃO-VENCEU (F2 DEFENDEU, F3/F4 LOCALIZADO_EM, F5 POSSUIR), sem alterar runtime.

Verificação real = `confs >= 3 AND doms >= 2` (URLs independentes contam;
2 URLs do MESMO domínio ainda contam para confirmations). `full_collision`
(3 domínios) é reportado separadamente do `predicted_verified` (métrica real).

Read-only: 1 GET por URL. Nada grava Neo4j/Qdrant. Anti-leak: sem corpo no relatório.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from collections import Counter
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
from src.miner.web_miner import WebMiner  # noqa: E402

AUDIT_ID = "diversified_fact_families_atlas_048_10"

P = "https://pt.wikipedia.org/wiki/"
E = "https://en.wikipedia.org/wiki/"

FAMILIES = [
    {
        "family_id": "player_defended_club",
        "predicate": "DEFENDEU",
        "subject_type": "PLAYER",
        "object_type": "CLUB",
        "candidate_facts": [
            {
                "fact": "GARRINCHA --DEFENDEU--> BOTAFOGO DE FUTEBOL E REGATAS",
                "subject_any": ["GARRINCHA", "MANUEL FRANCISCO DOS SANTOS"],
                "object_any": ["BOTAFOGO"],
                "urls": [
                    P + "Garrincha", E + "Garrincha",
                    P + "Botafogo_de_Futebol_e_Regatas", E + "Botafogo_de_Futebol_e_Regatas",
                ],
            },
            {
                "fact": "PELÉ --DEFENDEU--> SANTOS FUTEBOL CLUBE",
                "subject_any": ["PELÉ", "PELE", "EDSON ARANTES"],
                "object_any": ["SANTOS"],
                "urls": [
                    P + "Pel%C3%A9", E + "Pel%C3%A9",
                    P + "Santos_FC", E + "Santos_FC",
                ],
            },
        ],
    },
    {
        "family_id": "club_located_in_city",
        "predicate": "LOCALIZADO_EM",
        "subject_type": "CLUB",
        "object_type": "CITY",
        "candidate_facts": [
            {
                "fact": "BOTAFOGO DE FUTEBOL E REGATAS --LOCALIZADO_EM--> RIO DE JANEIRO",
                "subject_any": ["BOTAFOGO"],
                "object_any": ["RIO DE JANEIRO"],
                "urls": [
                    P + "Botafogo_de_Futebol_e_Regatas", E + "Botafogo_de_Futebol_e_Regatas",
                    P + "Rio_de_Janeiro", E + "Rio_de_Janeiro",
                ],
            },
            {
                "fact": "SANTOS FUTEBOL CLUBE --LOCALIZADO_EM--> SANTOS",
                "subject_any": ["SANTOS"],
                "object_any": ["SANTOS"],
                "urls": [P + "Santos_FC", E + "Santos_FC"],
            },
        ],
    },
    {
        "family_id": "stadium_located_in_city",
        "predicate": "LOCALIZADO_EM",
        "subject_type": "STADIUM",
        "object_type": "CITY",
        "candidate_facts": [
            {
                "fact": "ESTÁDIO OLÍMPICO NILTON SANTOS --LOCALIZADO_EM--> RIO DE JANEIRO",
                "subject_any": ["NILTON SANTOS", "ENGENHÃO", "ENGENHAO"],
                "object_any": ["RIO DE JANEIRO"],
                "urls": [
                    P + "Est%C3%A1dio_Ol%C3%ADmpico_Nilton_Santos",
                    E + "Est%C3%A1dio_Ol%C3%ADmpico_Nilton_Santos",
                ],
            },
            {
                "fact": "ESTÁDIO URBANO CALDEIRA --LOCALIZADO_EM--> SANTOS",
                "subject_any": ["URBANO CALDEIRA", "VILA BELMIRO"],
                "object_any": ["SANTOS"],
                "urls": [
                    P + "Est%C3%A1dio_Urbano_Caldeira", E + "Est%C3%A1dio_Urbano_Caldeira",
                ],
            },
        ],
    },
    {
        "family_id": "club_owns_stadium",
        "predicate": "POSSUIR",
        "subject_type": "CLUB",
        "object_type": "STADIUM",
        "candidate_facts": [
            {
                "fact": "SANTOS FUTEBOL CLUBE --POSSUIR--> ESTÁDIO URBANO CALDEIRA",
                "subject_any": ["SANTOS"],
                "object_any": ["URBANO CALDEIRA"],
                "urls": [P + "Santos_FC", E + "Santos_FC", P + "Est%C3%A1dio_Urbano_Caldeira"],
            },
            {
                "fact": "BOTAFOGO DE FUTEBOL E REGATAS --POSSUIR--> ESTÁDIO OLÍMPICO NILTON SANTOS",
                "subject_any": ["BOTAFOGO"],
                "object_any": ["NILTON SANTOS"],
                "urls": [
                    P + "Botafogo_de_Futebol_e_Regatas", E + "Botafogo_de_Futebol_e_Regatas",
                    P + "Est%C3%A1dio_Ol%C3%ADmpico_Nilton_Santos",
                ],
            },
        ],
    },
]


def _norm(v: object) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip().upper()


def _fold(v: object) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip().casefold()


def _publisher(domain: str) -> str:
    return "Wikimedia" if "wikipedia.org" in domain else ("RSSSF" if "rsssf.org" in domain else domain)


def _matches(triple: dict, fact: dict) -> bool:
    s, p, o = _norm(triple.get("subject")), _norm(triple.get("predicate")), _norm(triple.get("object"))
    if p != fact.get("_predicate"):
        return False
    subj_ok = any(tok in s for tok in fact["subject_any"])
    obj_ok = any(tok in o for tok in fact["object_any"])
    return subj_ok and obj_ok


async def _fetch(urls: list[str], headers: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    async with httpx.AsyncClient(follow_redirects=True, timeout=25.0) as client:
        for url in urls:
            try:
                r = await client.get(url, headers=headers)
                if r.status_code == 200 and r.content:
                    raw = r.content
                    html = None
                    for enc in ("utf-8", "latin-1"):
                        try:
                            html = raw.decode(enc)
                            break
                        except Exception:
                            continue
                    if html is None:
                        html = raw.decode("utf-8", errors="replace")
                    out[url] = {"status": 200, "final_url": str(r.url), "html": html}
                else:
                    out[url] = {"status": r.status_code, "final_url": str(r.url), "html": "", "error": f"http_{r.status_code}"}
            except Exception as exc:
                out[url] = {"status": 0, "final_url": url, "html": "", "error": type(exc).__name__}
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="#048.10 atlas de famílias (read-only).")
    parser.add_argument("--out", required=True)
    parser.add_argument("--cap", type=int, default=25, help="cap de triplas por página (produção=25)")
    args = parser.parse_args()

    miner = WebMiner()
    headers = miner.anti_block.generate_headers()
    canon = SemanticCanonicalizer()
    extractor = EntityExtractor(enable_fallback=True)

    # marca predicado esperado em cada fato p/ o matcher
    for fam in FAMILIES:
        for fact in fam["candidate_facts"]:
            fact["_predicate"] = fam["predicate"]

    all_urls = sorted({u for fam in FAMILIES for fact in fam["candidate_facts"] for u in fact["urls"]})
    fetched = asyncio.run(_fetch(all_urls, headers))

    # extrai uma vez por URL
    per_url: dict[str, dict] = {}
    url_canon: dict[str, list[dict]] = {}
    for url in all_urls:
        entry = fetched.get(url) or {}
        html = entry.get("html") or ""
        status = int(entry.get("status") or 0)
        rec = {"url": url, "final_url": entry.get("final_url", url),
               "domain": unquote(url).split("/")[2] if "://" in url else "",
               "http_status": status, "canonical_triples": 0, "error": entry.get("error", "")}
        rec["publisher"] = _publisher(rec["domain"])
        if not html:
            per_url[url] = rec
            url_canon[url] = []
            continue
        text = miner.clean_html(html, source_url=url).get("content") or ""
        raw = [t.to_dict() for t in extractor.extract(text, max_triples=args.cap)]
        from src.cognition.triple_refiner import refine_triple_ex
        canon_list = []
        for t in raw:
            c, _reason = refine_triple_ex(t, canon)
            if c is not None:
                canon_list.append(c)
        rec["canonical_triples"] = len(canon_list)
        per_url[url] = rec
        url_canon[url] = canon_list

    families_out = []
    total_predicted = 0
    pred_counts: Counter = Counter()
    obj_counts: Counter = Counter()
    subj_counts: Counter = Counter()
    eligible_families = 0
    for fam in FAMILIES:
        facts_out = []
        fam_eligible = False
        for fact in fam["candidate_facts"]:
            hit_urls: list[str] = []
            for url in fact["urls"]:
                if any(_matches(c, fact) for c in url_canon.get(url, [])):
                    hit_urls.append(url)
            domains = sorted({per_url[u]["domain"] for u in hit_urls})
            publishers = sorted({per_url[u]["publisher"] for u in hit_urls})
            confs = len(hit_urls)
            predicted_verified = confs >= 3 and len(domains) >= 2
            if {"pt.wikipedia.org", "en.wikipedia.org", "rsssf.org"}.issubset(domains):
                collision = "full_collision"
            elif len(domains) >= 2:
                collision = "partial_collision"
            else:
                collision = "no_collision"
            eligible = predicted_verified and collision in ("full_collision", "partial_collision")
            if eligible:
                fam_eligible = True
                total_predicted += 1
                pred_counts[fam["predicate"]] += 1
                obj_counts[fact["object_any"][0]] += 1
                subj_counts[fact["subject_any"][0]] += 1
            facts_out.append({
                "fact": fact["fact"],
                "sources": [
                    {"url": u, "final_url": per_url[u]["final_url"], "domain": per_url[u]["domain"],
                     "publisher": per_url[u]["publisher"], "http_status": per_url[u]["http_status"],
                     "canonical_triples": per_url[u]["canonical_triples"],
                     "matched_fact": u in hit_urls, "would_persist": u in hit_urls}
                    for u in fact["urls"]
                ],
                "predicted_domains": domains,
                "predicted_domain_count": len(domains),
                "predicted_publishers": publishers,
                "predicted_publisher_count": len(publishers),
                "predicted_confirmations": confs,
                "predicted_verified": predicted_verified,
                "collision_status": collision,
                "eligible_for_runtime": eligible,
                "blocking_reason": None if eligible else ("dominios<2" if len(domains) < 2 else "confs<3"),
            })
        if fam_eligible:
            eligible_families += 1
        families_out.append({
            "family_id": fam["family_id"], "predicate": fam["predicate"],
            "subject_type": fam["subject_type"], "object_type": fam["object_type"],
            "candidate_facts": facts_out, "family_eligible": fam_eligible,
        })

    payload = {
        "audit_id": AUDIT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "extraction_cap": args.cap,
        "verification_rule": "confirmed >= 3 AND distinct_domains >= 2",
        "families": families_out,
        "per_url": per_url,
        "summary": {
            "families_evaluated": len(FAMILIES),
            "eligible_families": eligible_families,
            "predicted_new_verified": total_predicted,
            "predicted_records_total": total_predicted + 10,  # + F1 VENCEU existente
            "predicted_unique_predicates": 1 + len(pred_counts),
            "predicted_non_venceu_ratio": round(total_predicted / (total_predicted + 10), 4) if total_predicted else 0.0,
            "predicted_publisher_count": 2,
            "eligible_for_runtime": eligible_families > 0,
            "recommended_next_step": ("Fase 1 runtime famílias elegíveis" if eligible_families else
                                      "parar; evidência para #053/#059"),
        },
    }
    assert_no_secret_markers(json.dumps(payload, ensure_ascii=False),
                             ("neodb://", "hf_", "sk-", "gsk_", "ghp_", "xoxb-", "AKIA"))
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    print(f"[{AUDIT_ID}] eligible_families={eligible_families} predicted_new_verified={total_predicted} "
          f"cap={args.cap}")
    for fam in families_out:
        for f in fam["candidate_facts"]:
            print(f"  {fam['predicate']:14s} {f['collision_status']:16s} confs={f['predicted_confirmations']} "
                  f"doms={f['predicted_domain_count']} verified={f['predicted_verified']} | {f['fact'][:60]}")
    print(f"[salvo em] {args.out}")


if __name__ == "__main__":
    main()
