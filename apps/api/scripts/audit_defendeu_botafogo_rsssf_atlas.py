"""#048.10I — Atlas read-only DEFENDEU Botafogo via pista RSSSF Brasil.

Hipotese: pagina RSSSF Brasil especifica do Botafogo (records de jogadores), referenciada
por "Source: RSSSF Brasil - Botafogo" na wiki EN. Read-only: sem Neo4j/Qdrant, sem worker.

Uso:
    python scripts/audit_defendeu_botafogo_rsssf_atlas.py
"""
from __future__ import annotations

import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "reports" / "defendeu_botafogo_rsssf_atlas_048_10I.json"
RAW_DIR = ROOT / ".autonomous" / "048_10I"

UA = "Nexus-Alpha/1.0 (read-only audit; semantic knowledge extraction)"
TIMEOUT = 15
DELAY = 2.0

CLUB = "BOTAFOGO DE FUTEBOL E REGATAS"

PLAYERS = {
    "GARRINCHA": ["garrincha"],
    "NILTON SANTOS": ["nilton santos"],
    "DIDI": ["didi"],
    "JAIRZINHO": ["jairzinho"],
    "HELENO DE FREITAS": ["heleno de freitas"],
    "QUARENTINHA": ["quarentinha"],
    "CARVALHO LEITE": ["carvalho leite"],
    "MANGA": ["manga"],
    "GENINHO": ["geninho"],
    "MENDONCA": ["mendonca", "mendonça"],
    "ROBERTO MIRANDA": ["roberto miranda"],
    "AMARILDO": ["amarildo"],
    "ZAGALLO": ["zagallo"],
}

FORBIDDEN_OBJECT_TOKENS = [
    "selecao", "seleção", "brazil", "brasil national", "copa do mundo", "world cup", "copa america",
]

DEFENDEU_PATTERNS = [
    r"played for (?:the )?botafogo",
    r"appearances for botafogo",
    r"apps for botafogo",
    r"with botafogo",
    r"at botafogo",
    r"pelo botafogo",
    r"defendeu o botafogo",
    r"jogou pelo botafogo",
    r"atuou pelo botafogo",
    r"vestiu a camisa do botafogo",
    r"como jogador do botafogo",
]

DISCOVERY_SEEDS = [
    "https://en.wikipedia.org/wiki/Botafogo_de_Futebol_e_Regatas",
    "https://pt.wikipedia.org/wiki/Botafogo_de_Futebol_e_Regatas",
]

CANDIDATE_URLS = [
    "https://www.rsssfbrasil.com/clubes/botafogo.htm",
    "https://www.rsssfbrasil.com/clubes/bfr.htm",
    "https://www.rsssfbrasil.com/tablesn/botafogo.htm",
    "https://www.rsssfbrasil.com/sel/botafogo.htm",
    "https://www.rsssfbrasil.com/recordes/botafogo.htm",
    "https://www.rsssfbrasil.com/sel/jogclub.htm",
]

ALLOWED_HOSTS = {
    "pt.wikipedia.org", "en.wikipedia.org", "rsssf.org", "www.rsssf.org",
    "rsssfbrasil.com", "www.rsssfbrasil.com",
}


def fold(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value or "")
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn").lower()


def strip_html(html: str) -> str:
    html = re.sub(r"(?is)<(script|style).*?</\1>", " ", html or "")
    return re.sub(r"\s+", " ", re.sub(r"(?s)<[^>]+>", " ", html)).strip()


def http_get(url: str) -> tuple[int, str, str]:
    if urllib.parse.urlparse(url).netloc.lower() not in ALLOWED_HOSTS:
        return 0, "", url
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310 (allowlist)
            return response.status, response.read().decode("utf-8", errors="replace"), response.geturl()
    except urllib.error.HTTPError as exc:
        return exc.code, "", url
    except Exception:
        return 0, "", url


def find_players(text_folded: str) -> list[str]:
    return [canon for canon, aliases in PLAYERS.items() if any(a in text_folded for a in aliases)]


def has_botafogo_context(text_folded: str) -> bool:
    return "botafogo" in text_folded and "botafogo-pb" not in text_folded and "botafogo pb" not in text_folded


def scan_defendeu(text: str, domain: str, url: str) -> dict:
    cleaned = strip_html(text)
    folded = fold(cleaned)
    record = {
        "url": url, "domain": domain, "http_status": 200,
        "cleaned_text_length": len(cleaned), "tables_found": cleaned.count("<table"),
        "facts": [], "rejection_reasons": {},
    }
    if not has_botafogo_context(folded):
        record["rejection_reasons"]["no_botafogo_context"] = 1
        return record
    sentences = re.split(r"(?<=[.!?])\s+|(?=\|)", cleaned)
    for player in find_players(folded):
        aliases = PLAYERS[player]
        for sentence in sentences:
            s = fold(sentence)
            if not any(a in s for a in aliases):
                continue
            if "botafogo" not in s:
                continue
            if any(tok in s for tok in FORBIDDEN_OBJECT_TOKENS):
                record["rejection_reasons"]["national_team_or_competition"] = record["rejection_reasons"].get("national_team_or_competition", 0) + 1
                continue
            if any(re.search(p, s) for p in DEFENDEU_PATTERNS) or re.search(r"\d{2,4}\s*\|\s*\d+", s):
                record["facts"].append({"player": player, "club": CLUB, "evidence": "explicit_player_club"})
    return record


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    generated = datetime.now(timezone.utc).isoformat()

    candidates = []
    urls_tested = 0
    accessible = 0
    discovered: list[str] = list(CANDIDATE_URLS)
    requests = 0

    # Descoberta de links rsssf nas paginas wiki do Botafogo.
    for seed in DISCOVERY_SEEDS:
        if requests >= 8:
            break
        requests += 1
        urls_tested += 1
        code, body, final = http_get(seed)
        if code == 200:
            accessible += 1
            seed_domain = urllib.parse.urlparse(final or seed).netloc.lower()
            seed_record = scan_defendeu(body, seed_domain, seed)
            seed_record["final_url"] = final or seed
            seed_record["blocked_reason"] = None
            candidates.append(seed_record)
            for m in re.finditer(r'(?i)href\s*=\s*"([^"]+)"', body):
                href = m.group(1)
                if "rsssf" in href.lower():
                    absolute = urllib.parse.urljoin(seed, href)
                    if absolute not in discovered:
                        discovered.append(absolute)
        time.sleep(DELAY)

    rsssf_botafogo_found = False
    for url in discovered:
        if requests >= 22:
            break
        requests += 1
        urls_tested += 1
        code, body, final = http_get(url)
        if code != 200:
            candidates.append({"url": url, "final_url": final, "domain": urllib.parse.urlparse(url).netloc,
                               "http_status": code, "blocked_reason": "http_error", "facts": [], "rejection_reasons": {}})
            time.sleep(DELAY)
            continue
        accessible += 1
        domain = urllib.parse.urlparse(final or url).netloc.lower()
        record = scan_defendeu(body, domain, url)
        record["final_url"] = final or url
        record["blocked_reason"] = None
        if (
            "botafogo" in url.lower()
            and domain in ("rsssfbrasil.com", "www.rsssfbrasil.com", "rsssf.org", "www.rsssf.org")
            and record.get("facts")
        ):
            rsssf_botafogo_found = True
        if record.get("facts") or domain.endswith("wikipedia.org"):
            candidates.append(record)
        (RAW_DIR / (re.sub(r"[^a-z0-9]+", "_", domain + "_" + url)[-80:] + ".len")).write_text(str(len(body)), encoding="utf-8")
        time.sleep(DELAY)

    # Colisao prevista por jogador.
    fact_map: dict[str, dict] = {}
    for rec in candidates:
        for f in rec.get("facts", []):
            entry = fact_map.setdefault(f["player"], {"player": f["player"], "domains": set(), "publishers": set()})
            entry["domains"].add(rec["domain"])
            entry["publishers"].add("Wikimedia" if rec["domain"].endswith("wikipedia.org") else "RSSSF")

    facts = []
    full = partial = 0
    for player, entry in fact_map.items():
        domains = sorted(entry["domains"])
        dcount = len(domains)
        non_wiki = any(not d.endswith("wikipedia.org") for d in domains)
        if dcount >= 3 and non_wiki:
            status = "full_collision"
            full += 1
        elif dcount >= 2:
            status = "partial_collision"
            partial += 1
        else:
            status = "no_collision"
        facts.append({
            "fact": f"{player} --DEFENDEU--> {CLUB}",
            "sources": sorted(domains),
            "predicted_domains": domains,
            "predicted_domain_count": dcount,
            "predicted_publishers": sorted(entry["publishers"]),
            "predicted_publisher_families": sorted(entry["publishers"]),
            "predicted_effective_publisher_count": len(entry["publishers"]),
            "collision_status": status,
            "eligible_for_runtime": status == "full_collision",
            "blocking_reason": None if status == "full_collision" else "insufficient_independent_domains",
        })

    if full >= 3:
        classification = "READY_048_10J_DEFENDEU_SCALE"
    elif full >= 1:
        classification = "PARTIAL_048_10I_DEFENDEU_EVIDENCE"
    else:
        classification = "BLOCKED_048_10I_NO_THIRD_SOURCE"

    summary = {
        "urls_tested": urls_tested,
        "accessible_urls": accessible,
        "rsssf_botafogo_page_found": rsssf_botafogo_found,
        "defendeu_full_collision_facts": full,
        "defendeu_partial_collision_facts": partial,
        "predicted_new_verified": full,
        "eligible_for_runtime": full >= 3,
        "classification": classification,
        "recommended_next_step": (
            "#048.10J runtime condicional DEFENDEU (apos Space restaurado)."
            if full >= 3
            else "DEFENDEU permanece sem 3a fonte independente; retomar apos #055 (licenca) ou redeploy GEO."
        ),
    }

    atlas = {
        "audit_id": "defendeu_botafogo_rsssf_atlas_048_10I",
        "generated_at": generated,
        "family": "player_defended_club",
        "hypothesis": "RSSSF Brasil Botafogo club-context player records",
        "policy": {
            "allowed_players": list(PLAYERS.keys()),
            "allowed_clubs": [CLUB],
            "forbidden_objects": ["NATIONAL_TEAM", "COMPETITION", "YEAR", "NUMBER", "PERIOD", "PRONOUN", "CLAUSE", "AMBIGUOUS_CLUB"],
        },
        "candidates": candidates,
        "facts": facts,
        "summary": summary,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(atlas, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("WROTE", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
