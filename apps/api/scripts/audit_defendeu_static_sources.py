"""#048.10B Fase 0/4 — Atlas + dry-run read-only de fontes para DEFENDEU.

Testa `JOGADOR --DEFENDEU--> CLUBE` (allowlists conservadoras) em páginas
estáticas (wiki pt/en + clubes), com o extractor de produção (cap=25,
target-aware). Verificação real: `confs>=3 AND doms>=2`.

Read-only: 1 GET por URL. Nada grava Neo4j/Qdrant. Anti-leak: sem corpo no relatório.
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

AUDIT_ID = "defendeu_static_sources_atlas_048_10B"
P = "https://pt.wikipedia.org/wiki/"
E = "https://en.wikipedia.org/wiki/"

PLAYER_ALLOWED = ["GARRINCHA", "MANUEL FRANCISCO DOS SANTOS", "PELÉ", "PELE",
                  "EDSON ARANTES DO NASCIMENTO", "NILTON SANTOS", "DIDI",
                  "JAIRZINHO", "HELENO DE FREITAS"]
CLUB_ALLOWED = ["BOTAFOGO DE FUTEBOL E REGATAS", "SANTOS FUTEBOL CLUBE"]

FACTS = [
    {"fact": "GARRINCHA --DEFENDEU--> BOTAFOGO DE FUTEBOL E REGATAS",
     "subject_any": ["GARRINCHA", "MANUEL FRANCISCO DOS SANTOS"],
     "object_any": ["BOTAFOGO"],
     "urls": [P + "Garrincha", E + "Garrincha",
              P + "Botafogo_de_Futebol_e_Regatas", E + "Botafogo_de_Futebol_e_Regatas"]},
    {"fact": "PELÉ --DEFENDEU--> SANTOS FUTEBOL CLUBE",
     "subject_any": ["PELÉ", "PELE", "EDSON ARANTES"],
     "object_any": ["SANTOS"],
     "urls": [P + "Pel%C3%A9", E + "Pel%C3%A9", P + "Santos_FC", E + "Santos_FC"]},
    {"fact": "NILTON SANTOS --DEFENDEU--> BOTAFOGO DE FUTEBOL E REGATAS",
     "subject_any": ["NILTON SANTOS", "NÍLTON SANTOS"],
     "object_any": ["BOTAFOGO"],
     "urls": [P + "Nilton_Santos", E + "Nilton_Santos"]},
    {"fact": "DIDI --DEFENDEU--> BOTAFOGO DE FUTEBOL E REGATAS",
     "subject_any": ["DIDI"], "object_any": ["BOTAFOGO"],
     "urls": [P + "Didi", E + "Didi_(footballer)"]},
    {"fact": "JAIRZINHO --DEFENDEU--> BOTAFOGO DE FUTEBOL E REGATAS",
     "subject_any": ["JAIRZINHO"], "object_any": ["BOTAFOGO"],
     "urls": [P + "Jairzinho", E + "Jairzinho"]},
    {"fact": "HELENO DE FREITAS --DEFENDEU--> BOTAFOGO DE FUTEBOL E REGATAS",
     "subject_any": ["HELENO DE FREITAS", "HELENO"], "object_any": ["BOTAFOGO"],
     "urls": [P + "Heleno_de_Freitas", E + "Heleno_de_Freitas"]},
]

FORBIDDEN_OBJECTS = ["SELEÇÃO BRASILEIRA", "BRAZIL", "BRASIL", "COPA DO MUNDO",
                     "WORLD CUP", "NATIONAL TEAM"]


def _fold(v: object) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip().casefold()


def _norm(v: object) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip().upper()


def _publisher(domain: str) -> str:
    return "Wikimedia" if "wikipedia.org" in domain else ("RSSSF" if "rsssf.org" in domain else domain)


def _matches(triple: dict, fact: dict) -> bool:
    s, o = _norm(triple.get("subject")), _norm(triple.get("object"))
    if _norm(triple.get("predicate")) != "DEFENDEU":
        return False
    if any(fb in o for fb in FORBIDDEN_OBJECTS):
        return False
    return any(tok in s for tok in fact["subject_any"]) and any(tok in o for tok in fact["object_any"])


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
                    out[url] = {"status": 200, "final_url": str(r.url),
                                "html": html or raw.decode("utf-8", errors="replace")}
                else:
                    out[url] = {"status": r.status_code, "final_url": str(r.url), "html": "",
                                "error": f"http_{r.status_code}"}
            except Exception as exc:
                out[url] = {"status": 0, "final_url": url, "html": "", "error": type(exc).__name__}
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="#048.10B atlas DEFENDEU (read-only).")
    parser.add_argument("--out", required=True)
    parser.add_argument("--cap", type=int, default=25)
    args = parser.parse_args()

    miner = WebMiner()
    headers = miner.anti_block.generate_headers()
    canon = SemanticCanonicalizer()
    extractor = EntityExtractor(enable_fallback=True)

    urls = sorted({u for f in FACTS for u in f["urls"]})
    fetched = asyncio.run(_fetch(urls, headers))

    per_url: dict[str, dict] = {}
    url_canon: dict[str, list[dict]] = {}
    for url in urls:
        entry = fetched.get(url) or {}
        html = entry.get("html") or ""
        rec = {"url": url, "final_url": entry.get("final_url", url),
               "domain": unquote(url).split("/")[2] if "://" in url else "",
               "publisher": _publisher(unquote(url).split("/")[2] if "://" in url else ""),
               "http_status": int(entry.get("status") or 0), "canonical_triples": 0,
               "raw_triples": 0, "error": entry.get("error", "")}
        if not html:
            per_url[url] = rec
            url_canon[url] = []
            continue
        text = miner.clean_html(html, source_url=url).get("content") or ""
        raw = [t.to_dict() for t in extractor.extract(text, max_triples=args.cap)]
        cl = []
        for t in raw:
            c, _r = refine_triple_ex(t, canon)
            if c is not None:
                cl.append(c)
        rec["raw_triples"] = len(raw)
        rec["canonical_triples"] = len(cl)
        per_url[url] = rec
        url_canon[url] = cl

    facts_out = []
    full = partial = 0
    for fact in FACTS:
        hit = [u for u in fact["urls"] if any(_matches(c, fact) for c in url_canon.get(u, []))]
        domains = sorted({per_url[u]["domain"] for u in hit})
        publishers = sorted({per_url[u]["publisher"] for u in hit})
        confs = len(hit)
        verified = confs >= 3 and len(domains) >= 2
        cross = ("full_collision" if {"pt.wikipedia.org", "en.wikipedia.org"}.issubset(domains)
                 else "partial_collision" if len(domains) >= 2 else "no_collision")
        if cross == "full_collision":
            full += 1
        elif cross == "partial_collision":
            partial += 1
        facts_out.append({
            "fact": fact["fact"],
            "sources": [{"url": u, "final_url": per_url[u]["final_url"], "domain": per_url[u]["domain"],
                         "publisher": per_url[u]["publisher"], "source_type": "wiki_narrative",
                         "http_status": per_url[u]["http_status"], "canonical_triples": per_url[u]["canonical_triples"],
                         "target_fact_hits": 1 if u in hit else 0, "matched_fact": u in hit,
                         "would_persist": u in hit} for u in fact["urls"]],
            "predicted_domains": domains, "predicted_domain_count": len(domains),
            "predicted_publishers": publishers, "predicted_publisher_count": len(publishers),
            "predicted_confirmations": confs, "predicted_verified": verified,
            "collision_status": cross, "eligible_for_runtime": verified,
            "blocking_reason": None if verified else ("dom<2" if len(domains) < 2 else "confs<3"),
        })

    payload = {
        "audit_id": AUDIT_ID, "generated_at": datetime.now(timezone.utc).isoformat(),
        "family": "player_defended_club", "read_only": True, "extraction_cap": args.cap,
        "verification_rule": "confirmed >= 3 AND distinct_domains >= 2",
        "policy": {"allowed_players": PLAYER_ALLOWED, "allowed_clubs": CLUB_ALLOWED,
                   "allowed_predicates": ["DEFENDEU"], "forbidden_objects": FORBIDDEN_OBJECTS},
        "facts": facts_out, "per_url": per_url,
        "summary": {"facts_evaluated": len(FACTS), "full_collision_facts": full,
                    "partial_collision_facts": partial,
                    "predicted_new_verified": sum(1 for f in facts_out if f["predicted_verified"]),
                    "eligible_for_runtime": any(f["predicted_verified"] for f in facts_out),
                    "recommended_next_step": "Fase 2 runtime DEFENDEU" if any(f["predicted_verified"] for f in facts_out) else "BLOCKED_THIRD_DOMAIN_FOR_DEFENDEU"},
    }
    assert_no_secret_markers(json.dumps(payload, ensure_ascii=False),
                             ("neodb://", "hf_", "sk-", "gsk_", "ghp_", "xoxb-", "AKIA"))
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    print(f"[{AUDIT_ID}] full={full} partial={partial} predicted_verified={payload['summary']['predicted_new_verified']}")
    for f in facts_out:
        print(f"  {f['collision_status']:16s} confs={f['predicted_confirmations']} doms={f['predicted_domain_count']} verified={f['predicted_verified']} | {f['fact'][:58]}")
    print(f"[salvo em] {args.out}")


if __name__ == "__main__":
    main()
