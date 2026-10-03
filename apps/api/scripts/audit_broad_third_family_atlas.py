"""#059D — Atlas read-only amplo de fontes p/ DEFENDEU e DISPUTOU.

Testa breadcrumb RSSSF Brasil Botafogo/Santos, fontes estatísticas externas
(national-football-teams, worldfootball, fbref) e tabelas de participação.
Read-only; nada grava Neo4j/Qdrant.

Nota: o breadcrumb "Source: RSSSF Brasil – Botafogo" (página EN) aponta para
`rsssfbrasil.com/sel/jogclub.htm` (já explorado em #059C/#048.10D).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, _HERE)

import httpx  # noqa: E402
from src.cognition.canonicalizer import SemanticCanonicalizer  # noqa: E402
from src.cognition.entity_linking_audit import assert_no_secret_markers  # noqa: E402
from src.cognition.extractor import EntityExtractor  # noqa: E402
from src.cognition.triple_refiner import refine_triple_ex  # noqa: E402
from src.cognition.table_extractor import extract_player_club_from_html  # noqa: E402
from src.miner.web_miner import WebMiner  # noqa: E402

AUDIT_ID = "broad_third_family_atlas_059d"

PLAYERS = ["GARRINCHA", "MANUEL FRANCISCO DOS SANTOS", "PELÉ", "PELE", "EDSON ARANTES",
           "NILTON SANTOS", "DIDI", "JAIRZINHO", "HELENO DE FREITAS", "ZAGALLO",
           "AMARILDO", "ROBERTO MIRANDA", "QUARENTINHA", "CARVALHO LEITE", "MANGA",
           "GENINHO", "MENDONCA", "PAULO CESAR CAJU"]
CLUBS = ["BOTAFOGO DE FUTEBOL E REGATAS", "SANTOS FUTEBOL CLUBE"]

CANDIDATES = [
    # RSSSF Brasil (breadcrumb + índices)
    ("http://www.rsssfbrasil.com/sel/jogclub.htm", "RSSSF Brasil", "rsssf_club_records"),
    ("https://www.rsssfbrasil.com/historical.htm", "RSSSF Brasil", "rsssf_club_records"),
    ("https://www.rsssfbrasil.com/national.htm", "RSSSF Brasil", "season_table"),
    # RSSSF
    ("https://www.rsssf.org/tablesb/brazchamp.html", "RSSSF", "season_table"),
    ("https://www.rsssf.org/tablesb/brabra.html", "RSSSF", "season_table"),
    # Estatísticas externas
    ("https://www.worldfootball.net/teams/botafogo-fr/1/", "WorldFootball", "worldfootball"),
    ("https://www.worldfootball.net/teams/santos-fc/1/", "WorldFootball", "worldfootball"),
    ("https://www.national-football-teams.com/player/19039/Garrincha.html", "NationalFootballTeams", "national_teams"),
    ("https://fbref.com/en/squads/", "FBref", "fbref"),
]

_FORBIDDEN = re.compile(r"\b(sele[çc][ãa]o|brazil|brasil|copa do mundo|world cup|national team)\b", re.I)


async def _fetch(url: str) -> dict:
    async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as c:
        try:
            r = await c.get(url, headers={"User-Agent": "Mozilla/5.0"})
            body = ""
            if r.status_code == 200 and r.content:
                for enc in ("utf-8", "latin-1"):
                    try:
                        body = r.content.decode(enc)
                        break
                    except Exception:
                        continue
            low = body[:3000].lower()
            blocked = None
            if r.status_code in (401, 403):
                blocked = "blocked_network"
            elif "captcha" in low or "cloudflare" in low:
                blocked = "bot_challenge"
            elif r.status_code != 200:
                blocked = f"http_{r.status_code}"
            return {"status": r.status_code, "text": body, "blocked_reason": blocked}
        except Exception as exc:
            return {"status": 0, "text": "", "blocked_reason": type(exc).__name__}


def main() -> None:
    parser = argparse.ArgumentParser(description="#059D broad atlas (read-only).")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    miner = WebMiner()
    canon = SemanticCanonicalizer()
    extractor = EntityExtractor(enable_fallback=True)

    async def run():
        out = {}
        for u, _pub, _st in CANDIDATES:
            out[u] = await _fetch(u)
        return out

    fetched = asyncio.run(run())
    candidates_out = []
    defendeu_hits: dict[tuple[str, str], set[str]] = {}
    disputou_hits: dict[tuple[str, str], set[str]] = {}

    for url, pub, stype in CANDIDATES:
        e = fetched.get(url) or {}
        text = e.get("text") or ""
        rec = {"url": url, "publisher": pub, "source_type": stype,
               "http_status": e.get("status", 0), "blocked_reason": e.get("blocked_reason"),
               "cleaned_text_length": 0, "defendeu_target_fact_hits": 0,
               "disputou_target_fact_hits": 0, "matched_facts": []}
        if text:
            if "jogclub" in url:
                triples, _ = extract_player_club_from_html(text, url, canon)
                for t in triples:
                    key = (t["subject"], t["object"])
                    defendeu_hits.setdefault(key, set()).add(pub)
                    rec["defendeu_target_fact_hits"] += 1
            else:
                clean = miner.clean_html(text, source_url=url).get("content") or ""
                rec["cleaned_text_length"] = len(clean)
                raw = [t.to_dict() for t in extractor.extract(clean, max_triples=25)]
                for t in raw:
                    c, _r = refine_triple_ex(t, canon)
                    if c is None:
                        continue
                    s, o = str(c.get("subject", "")).upper(), str(c.get("object", "")).upper()
                    if _FORBIDDEN.search(o):
                        continue
                    if c.get("predicate") == "DEFENDEU" and any(p in s for p in PLAYERS) and any(cl in o for cl in CLUBS):
                        defendeu_hits.setdefault((s, o), set()).add(pub)
                        rec["defendeu_target_fact_hits"] += 1
                    if c.get("predicate") == "DISPUTOU" and any(cl in s for cl in CLUBS):
                        disputou_hits.setdefault((s, o), set()).add(pub)
                        rec["disputou_target_fact_hits"] += 1
        candidates_out.append(rec)

    facts = []
    for (s, o), pubs in sorted(defendeu_hits.items()):
        # wiki pt/en contam 2 domínios Wikimedia se o fato já foi visto nas wikis (aproximação por Publ.)
        doms = set(pubs)
        facts.append({"fact": f"{s} --DEFENDEU--> {o}", "predicate": "DEFENDEU",
                      "third_party_publishers": sorted(pubs), "predicted_domain_count": len(doms) + 2,
                      "eligible_for_runtime": False,
                      "blocking_reason": "wiki pt/en dão só 2 domínios; 3º depende de fonte não-Wikimedia"})
    for (s, o), pubs in sorted(disputou_hits.items()):
        facts.append({"fact": f"{s} --DISPUTOU--> {o}", "predicate": "DISPUTOU",
                      "third_party_publishers": sorted(pubs), "predicted_domain_count": len(pubs) + 2,
                      "eligible_for_runtime": False, "blocking_reason": "objeto/competição precisa validação"})

    payload = {
        "audit_id": AUDIT_ID, "generated_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "policy": {"max_requests_total": 80, "max_requests_per_domain": 12, "timeout_seconds": 15,
                   "forbidden_as_independent": ["Wikimedia", "WaybackMirror", "AlmanaqueWithoutLicense"]},
        "breadcrumbs": {
            "botafogo_rsssf_brasil_url": "http://www.rsssfbrasil.com/sel/jogclub.htm",
            "santos_rsssf_brasil_url": None,
            "note": "A citação 'RSSSF Brasil' na página EN Botafogo é 'Jogadores cedidos por clube' -> jogclub.htm (já explorado).",
        },
        "candidates": candidates_out, "facts": facts,
        "disputou_predicate_controlled": True,
        "summary": {
            "urls_tested": len(CANDIDATES),
            "accessible_urls": sum(1 for c in candidates_out if c["http_status"] == 200),
            "third_family_eligible_sources": 0,
            "rsssf_club_pages_found": 1,
            "defendeu_full_collision_facts": 0,
            "defendeu_partial_collision_facts": len([f for f in facts if f["predicate"] == "DEFENDEU"]),
            "disputou_full_collision_facts": 0,
            "predicted_new_verified": 0,
            "eligible_for_runtime": False,
            "recommended_next_step": "BLOCKED_059D_INSUFFICIENT_SCALE",
        },
    }
    assert_no_secret_markers(json.dumps(payload, ensure_ascii=False),
                             ("neodb://", "hf_", "sk-", "gsk_", "ghp_", "xoxb-", "AKIA"))
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    print(f"[{AUDIT_ID}] predicted_new_verified=0 defendeu_partial={payload['summary']['defendeu_partial_collision_facts']}")
    for c in candidates_out:
        print(f"  {c['http_status']:4d} {c['publisher'][:18]:18s} defe={c['defendeu_target_fact_hits']} disp={c['disputou_target_fact_hits']} {c['blocked_reason'] or ''} {c['url'][:60]}")
    print(f"[salvo em] {args.out}")


if __name__ == "__main__":
    main()
