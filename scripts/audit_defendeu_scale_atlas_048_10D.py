"""#048.10D Fase 0 — Atlas read-only de ESCALA do DEFENDEU.

Testa fontes estáticas (RSSSF/RSSSF Brasil/estatísticas) para novos fatos
`JOGADOR --DEFENDEU--> CLUBE` verificáveis por 3 domínios. Read-only.

Fontes de terceira parte são NON-Wikimedia; pt/en Wikipedia contam como 2
domínios (1 família editorial Wikimedia). Nada grava Neo4j/Qdrant.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
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
from src.cognition.table_extractor import extract_player_club_from_html  # noqa: E402
from src.miner.web_miner import WebMiner  # noqa: E402

AUDIT_ID = "defendeu_scale_atlas_048_10D"
P = "https://pt.wikipedia.org/wiki/"
E = "https://en.wikipedia.org/wiki/"

PLAYERS = ["GARRINCHA", "MANUEL FRANCISCO DOS SANTOS", "PELÉ", "PELE",
           "EDSON ARANTES DO NASCIMENTO", "NILTON SANTOS", "DIDI", "JAIRZINHO",
           "HELENO DE FREITAS", "ZAGALLO", "AMARILDO", "MANGA", "GENINHO"]
CLUBS = ["BOTAFOGO DE FUTEBOL E REGATAS", "SANTOS FUTEBOL CLUBE",
         "CLUBE DE REGATAS DO FLAMENGO", "SOCIEDADE ESPORTIVA PALMEIRAS",
         "SÃO PAULO FUTEBOL CLUBE", "GRÊMIO FOOT-BALL PORTO ALEGRENSE",
         "SPORT CLUBE INTERNACIONAL"]

# fatos-alvo: (player tokens, club tokens, wiki pt/en)
FACTS = [
    ("GARRINCHA", ["GARRINCHA", "MANUEL FRANCISCO DOS SANTOS"], ["BOTAFOGO"], [P + "Garrincha", E + "Garrincha"]),
    ("PELÉ", ["PELÉ", "PELE", "EDSON ARANTES"], ["SANTOS"], [P + "Pel%C3%A9", E + "Pel%C3%A9"]),
    ("NILTON SANTOS", ["NILTON"], ["BOTAFOGO"], [P + "Nilton_Santos", E + "Nilton_Santos"]),
    ("DIDI", ["DIDI"], ["BOTAFOGO"], [P + "Didi", E + "Didi_(footballer)"]),
    ("JAIRZINHO", ["JAIRZINHO"], ["BOTAFOGO"], [P + "Jairzinho", E + "Jairzinho"]),
    ("HELENO DE FREITAS", ["HELENO"], ["BOTAFOGO"], [P + "Heleno_de_Freitas", E + "Heleno_de_Freitas"]),
]

THIRD_PARTY = [
    ("https://www.rsssfbrasil.com/sel/jogclub.htm", "rsssfbrasil.com", "RSSSF Brasil", "rsssf_club_records"),
    ("https://www.rsssf.org/tables/58full.html", "rsssf.org", "RSSSF", "rsssf_squad"),
    ("https://www.rsssf.org/tables/62full.html", "rsssf.org", "RSSSF", "rsssf_squad"),
    ("https://www.rsssf.org/tables/70full.html", "rsssf.org", "RSSSF", "rsssf_squad"),
    ("https://www.rsssf.org/miscellaneous/torre-sac-best.html", "rsssf.org", "RSSSF", "rsssf_squad"),
]


def _fact_match(subject: str, obj: str, fact) -> bool:
    s, o = subject.upper(), obj.upper()
    return any(t in s for t in fact[1]) and any(c in o for c in fact[2])


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
    parser = argparse.ArgumentParser(description="#048.10D DEFENDEU scale atlas (read-only).")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    miner = WebMiner()
    canon = SemanticCanonicalizer()
    extractor = EntityExtractor(enable_fallback=True)

    async def run() -> dict:
        urls = sorted({u for f in FACTS for u in f[3]}) + [u for u, *_ in THIRD_PARTY]
        return {u: await _fetch(u) for u in urls}

    fetched = asyncio.run(run())

    # wiki DEFENDEU keys por URL
    wiki_keys: dict[str, set[tuple[str, str]]] = {}
    for f in FACTS:
        for u in f[3]:
            text = (fetched.get(u) or {}).get("text") or ""
            keys = set()
            if text:
                clean = miner.clean_html(text, source_url=u).get("content") or ""
                for t in extractor.extract(clean, max_triples=25):
                    if t.predicate == "DEFENDEU":
                        keys.add((t.subject.upper(), t.object.upper()))
            wiki_keys[u] = keys

    # third-party DEFENDEU keys
    third_keys: dict[str, set[tuple[str, str]]] = {}
    third_meta = {}
    for url, domain, pub, stype in THIRD_PARTY:
        text = (fetched.get(url) or {}).get("text") or ""
        keys = set()
        if text:
            if "jogclub" in url:
                triples, _ = extract_player_club_from_html(text, url, canon)
                keys = {(t["subject"], t["object"]) for t in triples}
            else:
                clean = miner.clean_html(text, source_url=url).get("content") or ""
                for t in extractor.extract(clean, max_triples=25):
                    if t.predicate == "DEFENDEU":
                        keys.add((t.subject.upper(), t.object.upper()))
        third_keys[url] = keys
        third_meta[url] = {"domain": domain, "publisher": pub, "source_type": stype,
                           "http_status": (fetched.get(url) or {}).get("status", 0), "keys": len(keys)}

    facts_out = []
    full = 0
    for f in FACTS:
        doms: set[str] = set()
        for u in f[3]:
            for (s, o) in wiki_keys.get(u, set()):
                if _fact_match(s, o, f):
                    doms.add(unquote(u).split("/")[2])
                    break
        third_hit_urls = []
        for url, *_ in THIRD_PARTY:
            for (s, o) in third_keys.get(url, set()):
                if _fact_match(s, o, f):
                    doms.add(third_meta[url]["domain"])
                    third_hit_urls.append(url)
                    break
        families = {"Wikimedia" if "wikipedia" in d else ("RSSSF" if "rsssf" in d else d) for d in doms}
        verified = len(doms) >= 3 and len(families) >= 2
        cross = "full_collision" if len(doms) >= 3 else ("partial_collision" if len(doms) >= 2 else "no_collision")
        if cross == "full_collision":
            full += 1
        facts_out.append({
            "fact": f"{f[0]} --DEFENDEU--> {f[2][0]}",
            "wiki_sources": f[3], "third_party_sources": third_hit_urls,
            "predicted_domains": sorted(doms), "predicted_domain_count": len(doms),
            "predicted_publishers": sorted(families), "predicted_publisher_families": sorted(families),
            "collision_status": cross, "eligible_for_runtime": verified,
            "blocking_reason": None if verified else ("dom<3" if len(doms) < 3 else "families<2"),
        })

    payload = {
        "audit_id": AUDIT_ID, "generated_at": datetime.now(timezone.utc).isoformat(),
        "family": "player_defended_club", "read_only": True, "hypotheses": ["H1", "H2", "H3"],
        "allowed_players": PLAYERS, "allowed_clubs": CLUBS,
        "candidates": [u for u, *_ in THIRD_PARTY], "third_party_meta": third_meta,
        "facts": facts_out,
        "summary": {
            "urls_tested": len(fetched), "accessible_urls": sum(1 for r in fetched.values() if r.get("status") == 200),
            "third_party_eligible_sources": sum(1 for m in third_meta.values() if m["keys"] > 0),
            "full_collision_facts": full,
            "partial_collision_facts": sum(1 for f in facts_out if f["collision_status"] == "partial_collision"),
            "predicted_new_verified": full,
            "eligible_for_runtime": full >= 1,
            "recommended_next_step": "Fase 1 runtime escala DEFENDEU" if full >= 1 else "BLOCKED_THIRD_SOURCE_FOR_FULL_COLLISION",
        },
    }
    assert_no_secret_markers(json.dumps(payload, ensure_ascii=False),
                             ("neodb://", "hf_", "sk-", "gsk_", "ghp_", "xoxb-", "AKIA"))
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    print(f"[{AUDIT_ID}] full={full} eligible_sources={payload['summary']['third_party_eligible_sources']}")
    for f in facts_out:
        print(f"  {f['collision_status']:16s} doms={f['predicted_domains']} | {f['fact'][:50]}")
    print(f"[salvo em] {args.out}")


if __name__ == "__main__":
    main()
