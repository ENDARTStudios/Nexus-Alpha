"""#059C Fase 0 — Atlas read-only de TERCEIRA fonte independente p/ DEFENDEU.

Hipóteses: H1 club-context player records (RSSSF Brasil jogclub), H2 tabela
explícita Player+Club, H3 perfil estático. Não conta Wikipedia como terceira
fonte; rsssfbrasil.com é domínio distinto (família editorial suspeita → #053).

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
from bs4 import BeautifulSoup  # noqa: E402
from src.cognition.canonicalizer import SemanticCanonicalizer  # noqa: E402
from src.cognition.entity_linking_audit import assert_no_secret_markers  # noqa: E402
from src.cognition.extractor import EntityExtractor  # noqa: E402
from src.miner.web_miner import WebMiner  # noqa: E402

AUDIT_ID = "defendeu_third_source_atlas_059c"
P = "https://pt.wikipedia.org/wiki/"
E = "https://en.wikipedia.org/wiki/"

ALLOWED_PLAYERS = frozenset({
    "GARRINCHA", "MANUEL FRANCISCO DOS SANTOS", "PELÉ", "PELE",
    "EDSON ARANTES DO NASCIMENTO", "NILTON SANTOS", "DIDI", "JAIRZINHO",
    "HELENO DE FREITAS",
})
ALLOWED_CLUBS = frozenset({"BOTAFOGO DE FUTEBOL E REGATAS", "SANTOS FUTEBOL CLUBE"})

# Fonte club-context (H1): RSSSF Brasil, "jogadores ... como jogador do CLUBE".
JOGCLUB_URL = "https://www.rsssfbrasil.com/sel/jogclub.htm"
_PLAYER_CLUB_RE = re.compile(
    r"([^\n()]{1,45}?)\s*\(\s*\d+\s+jogos(?:[^)]*?)como jogador d[oa]\s+([^)]+?)\)"
)

FACTS = [
    {"fact": "GARRINCHA --DEFENDEU--> BOTAFOGO DE FUTEBOL E REGATAS", "subj": ["GARRINCHA", "MANUEL FRANCISCO DOS SANTOS"], "obj": ["BOTAFOGO"], "wiki": [P + "Garrincha", E + "Garrincha"]},
    {"fact": "PELÉ --DEFENDEU--> SANTOS FUTEBOL CLUBE", "subj": ["PELÉ", "PELE", "EDSON ARANTES"], "obj": ["SANTOS"], "wiki": [P + "Pel%C3%A9", E + "Pel%C3%A9", P + "Santos_FC", E + "Santos_FC"]},
    {"fact": "NILTON SANTOS --DEFENDEU--> BOTAFOGO DE FUTEBOL E REGATAS", "subj": ["NILTON SANTOS", "NÍLTON SANTOS"], "obj": ["BOTAFOGO"], "wiki": [P + "Nilton_Santos", E + "Nilton_Santos"]},
    {"fact": "DIDI --DEFENDEU--> BOTAFOGO DE FUTEBOL E REGATAS", "subj": ["DIDI"], "obj": ["BOTAFOGO"], "wiki": [P + "Didi", E + "Didi_(footballer)"]},
    {"fact": "JAIRZINHO --DEFENDEU--> BOTAFOGO DE FUTEBOL E REGATAS", "subj": ["JAIRZINHO"], "obj": ["BOTAFOGO"], "wiki": [P + "Jairzinho", E + "Jairzinho"]},
]


def _fact_has(doms: set[str], fact: dict, tj_keys: set[tuple[str, str]]) -> set[str]:
    for pl, cl in tj_keys:
        if any(tok in pl for tok in fact["subj"]) and any(c in cl for c in fact["obj"]):
            doms.add("rsssfbrasil.com")
    return doms


def _fold(v: object) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip().casefold()


async def _fetch(url: str) -> dict:
    async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as c:
        try:
            r = await c.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200 and r.content:
                raw = r.content
                for enc in ("utf-8", "latin-1"):
                    try:
                        return {"status": 200, "final_url": str(r.url), "text": raw.decode(enc)}
                    except Exception:
                        continue
                return {"status": 200, "final_url": str(r.url), "text": raw.decode("utf-8", errors="replace")}
            return {"status": r.status_code, "final_url": str(r.url), "text": "", "error": f"http_{r.status_code}"}
        except Exception as exc:
            return {"status": 0, "final_url": url, "text": "", "error": type(exc).__name__}


def _jogclub_keys(text: str, canon: SemanticCanonicalizer) -> set[tuple[str, str]]:
    soup = BeautifulSoup(text, "html.parser")
    full = "\n".join(p.get_text() for p in soup.find_all("pre")) or soup.get_text()
    out = set()
    for m in _PLAYER_CLUB_RE.finditer(full):
        player = canon.canonicalize_entity(m.group(1).strip())
        club = canon.canonicalize_entity(m.group(2).strip())
        if player in ALLOWED_PLAYERS and club in ALLOWED_CLUBS:
            out.add((player, club))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="#059C atlas (read-only).")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    miner = WebMiner()
    canon = SemanticCanonicalizer()
    extractor = EntityExtractor(enable_fallback=True)

    wiki_urls = sorted({u for f in FACTS for u in f["wiki"]})
    third_urls = [JOGCLUB_URL]

    async def run() -> dict:
        results = {}
        for u in wiki_urls + third_urls:
            results[u] = await _fetch(u)
        return results

    fetched = asyncio.run(run())

    # wiki: extrai DEFENDEU por página
    wiki_def: dict[str, set[tuple[str, str]]] = {}
    per_url = {}
    for u in wiki_urls:
        e = fetched.get(u) or {}
        text = e.get("text") or ""
        per_url[u] = {"url": u, "domain": unquote(u).split("/")[2], "http_status": e.get("status", 0)}
        if not text:
            wiki_def[u] = set()
            continue
        clean = miner.clean_html(text, source_url=u).get("content") or ""
        keys = set()
        for t in extractor.extract(clean, max_triples=25):
            if t.predicate == "DEFENDEU":
                keys.add((t.subject.upper(), t.object.upper()))
        wiki_def[u] = keys

    # terceira fonte
    tj = fetched.get(JOGCLUB_URL) or {}
    tj_keys = _jogclub_keys(tj.get("text") or "", canon) if tj.get("text") else set()
    per_url[JOGCLUB_URL] = {"url": JOGCLUB_URL, "domain": "rsssfbrasil.com",
                            "http_status": tj.get("status", 0), "source_type": "rsssf_club_records",
                            "publisher_family": "RSSSF Brasil", "target_keys": sorted(tj_keys)}

    facts_out = []
    full = partial = 0
    for f in FACTS:
        doms = set()
        for u in f["wiki"]:
            for (s, o) in wiki_def.get(u, set()):
                if any(tok in s for tok in f["subj"]) and any(c in o for c in f["obj"]):
                    doms.add(unquote(u).split("/")[2])
                    break
        doms = _fact_has(doms, f, tj_keys)
        publishers = {("Wikimedia" if "wikipedia" in d else "RSSSF Brasil") for d in doms}
        verified = len(doms) >= 3 and len(publishers) >= 2
        cross = ("full_collision" if len(doms) >= 3 else "partial_collision" if len(doms) >= 2 else "no_collision")
        if cross == "full_collision":
            full += 1
        elif cross == "partial_collision":
            partial += 1
        facts_out.append({
            "fact": f["fact"], "wiki_sources": f["wiki"],
            "third_party_sources": [JOGCLUB_URL] if "rsssfbrasil.com" in doms else [],
            "predicted_domains": sorted(doms), "predicted_domain_count": len(doms),
            "predicted_publishers": sorted(publishers), "predicted_publisher_count": len(publishers),
            "collision_status": cross, "eligible_for_runtime": verified,
            "blocking_reason": None if verified else "faltam dominios",
        })

    payload = {
        "audit_id": AUDIT_ID, "generated_at": datetime.now(timezone.utc).isoformat(),
        "family": "player_defended_club", "read_only": True,
        "hypotheses": ["H1_club_context_player_records", "H2_explicit_player_club_table", "H3_player_profile_static_source"],
        "allowed_players": sorted(ALLOWED_PLAYERS), "allowed_clubs": sorted(ALLOWED_CLUBS),
        "candidates": sorted(third_urls), "per_url": per_url, "facts": facts_out,
        "summary": {
            "urls_tested": len(wiki_urls) + len(third_urls),
            "accessible_urls": sum(1 for r in per_url.values() if r.get("http_status") == 200),
            "third_party_eligible_sources": 1 if tj_keys else 0,
            "jogclub_keys": sorted(tj_keys),
            "full_collision_facts": full, "partial_collision_facts": partial,
            "predicted_new_verified": full,
            "eligible_for_runtime": full >= 1,
            "recommended_next_step": "Fase 1 runtime player-club (rsssfbrasil jogclub)" if full >= 1 else "BLOCKED_059C_NO_THIRD_SOURCE",
        },
    }
    assert_no_secret_markers(json.dumps(payload, ensure_ascii=False),
                             ("neodb://", "hf_", "sk-", "gsk_", "ghp_", "xoxb-", "AKIA"))
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    print(f"[{AUDIT_ID}] full={full} partial={partial} third_source_keys={sorted(tj_keys)}")
    for f in facts_out:
        print(f"  {f['collision_status']:16s} doms={f['predicted_domains']} | {f['fact'][:55]}")
    print(f"[salvo em] {args.out}")


if __name__ == "__main__":
    main()
