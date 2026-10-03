"""#059E (B1) - Atlas read-only DISPUTOU: CLUBE --DISPUTOU--> COMPETICAO.

Read-only: nao escreve em Neo4j/Qdrant, nao usa /api/ingest, nao roda worker.
Evidencia aceita (ordem): explicit_participant > group_stage > knockout_participant > finalist > winner.
Rejeita objeto-ano/rodada/posicao/pontos/resultado/clausula/generico.

Uso:
    python scripts/audit_disputou_participation_atlas.py
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
OUT = ROOT / "reports" / "disputou_participation_atlas_059e.json"
RAW_DIR = ROOT / ".autonomous" / "disputou"

UA = "NexusAlpha-059E-audit/1.0 (read-only; +https://github.com/ENDARTStudios/Nexus-Alpha)"
TIMEOUT = 20
ATTRIBUTION = "RSSSF (autor da pagina) ; Wikimedia CC0/CC-BY-SA por pagina"

CLUBS = [
    {"canon": "BOTAFOGO DE FUTEBOL E REGATAS", "aliases": ["botafogo de futebol e regatas", "botafogo fr", "botafogo"]},
    {"canon": "SANTOS FUTEBOL CLUBE", "aliases": ["santos futebol clube", "santos fc"]},
    {"canon": "CLUBE DE REGATAS DO FLAMENGO", "aliases": ["clube de regatas do flamengo", "flamengo"]},
    {"canon": "SOCIEDADE ESPORTIVA PALMEIRAS", "aliases": ["sociedade esportiva palmeiras", "palmeiras"]},
    {"canon": "SAO PAULO FUTEBOL CLUBE", "aliases": ["sao paulo futebol clube", "sao paulo fc"]},
    {"canon": "GREMIO FOOT-BALL PORTO ALEGRENSE", "aliases": ["gremio foot-ball porto alegrense", "gremio"]},
    {"canon": "SPORT CLUBE INTERNACIONAL", "aliases": ["sport club internacional"]},
]

# Ambiguidades sempre rejeitadas.
AMBIGUOUS = ["botafogo-pb", "botafogo pb", "santos-ap", "internacional de limeira", "flamengo-?"]

COMPETITIONS = [
    {"canon": "COPA LIBERTADORES", "aliases": ["libertadores", "libertadores da america", "conmebol libertadores"]},
    {"canon": "CAMPEONATO BRASILEIRO SERIE A", "aliases": ["campeonato brasileiro", "brasileirao", "serie a"]},
]

FORBIDDEN_OBJECTS = ["YEAR", "ROUND", "POSITION", "POINTS", "RESULT", "CLAUSE", "GENERIC"]

PT_VERBS = ["disputou", "participou", "competiu", "classificou-se", "integrou o grupo", "esteve no grupo"]
EN_VERBS = ["competed in", "participated in", "played in", "qualified for", "took part in", "entered"]
WINNER_HINTS = ["campeao", "champion", "won the", "venceu a", "conquistou"]

PRONOUNS = ["o time", "a equipe", "ele ", " it ", "the club", " o clube "]

WIKI_CLUBS = {
    "BOTAFOGO DE FUTEBOL E REGATAS": {
        "pt": "https://pt.wikipedia.org/wiki/Botafogo_de_Futebol_e_Regatas",
        "en": "https://en.wikipedia.org/wiki/Botafogo_de_Futebol_e_Regatas",
    },
    "SANTOS FUTEBOL CLUBE": {
        "pt": "https://pt.wikipedia.org/wiki/Santos_FC",
        "en": "https://en.wikipedia.org/wiki/Santos_FC",
    },
    "CLUBE DE REGATAS DO FLAMENGO": {
        "pt": "https://pt.wikipedia.org/wiki/Clube_de_Regatas_do_Flamengo",
        "en": "https://en.wikipedia.org/wiki/Clube_de_Regatas_do_Flamengo",
    },
    "SOCIEDADE ESPORTIVA PALMEIRAS": {
        "pt": "https://pt.wikipedia.org/wiki/Sociedade_Esportiva_Palmeiras",
        "en": "https://en.wikipedia.org/wiki/Sociedade_Esportiva_Palmeiras",
    },
}

RSSSF_SEEDS = [
    "https://www.rsssf.org/intclub.html",
    "https://www.rsssf.org/tablesb/brazchamp.html",
]


def strip_accents(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", value) if unicodedata.category(c) != "Mn")


def norm(value: str) -> str:
    return strip_accents(value or "").lower()


def http_get(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:  # noqa: S310
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, ""
    except Exception:
        return 0, ""


def strip_html(html: str) -> str:
    html = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text)


def find_club(text_norm: str) -> list[str]:
    """Clubes allowlisted presentes no texto; ambiguidades rejeitadas."""
    hits = []
    for amb in AMBIGUOUS:
        if amb in text_norm:
            # remove contexto ambiguo para nao casar o alias curto erroneamente
            text_norm = text_norm.replace(amb, " ")
    for club in CLUBS:
        for alias in club["aliases"]:
            if re.search(rf"(^|\b){re.escape(alias)}(\b|$)", text_norm):
                hits.append(club["canon"])
                break
    return sorted(set(hits))


def find_competition(text_norm: str) -> str | None:
    for comp in COMPETITIONS:
        for alias in comp["aliases"]:
            if alias in text_norm:
                return comp["canon"]
    return None


def participation_evidence(text_norm: str) -> str | None:
    if any(v in text_norm for v in PT_VERBS + EN_VERBS):
        return "explicit_participant"
    if re.search(r"group stage|fase de grupos|grupo [a-h]", text_norm):
        return "group_stage"
    if any(v in text_norm for v in WINNER_HINTS):
        return "winner"
    return None


def has_pronoun_subject(text_norm: str) -> bool:
    return any(p in f" {text_norm} " for p in PRONOUNS)


def scan_text(text: str, *, domain: str, source_type: str, url: str) -> dict:
    """Procura fatos CLUBE --DISPUTOU--> COMPETICAO em um texto (wiki ou rsssf)."""
    cleaned = strip_html(text)
    folded = norm(cleaned)
    result = {
        "url": url,
        "domain": domain,
        "source_type": source_type,
        "http_status": 200,
        "cleaned_text_length": len(cleaned),
        "facts": [],
    }
    clubs = find_club(folded)
    comp = find_competition(folded)
    if not clubs or not comp:
        return result
    # janela de evidencia: sentenca contendo clube + competicao + verbo
    sentences = re.split(r"(?<=[.!?])\s+", cleaned)
    for club in clubs:
        for sent in sentences:
            s = norm(sent)
            if not any(a in s for a in next(c["aliases"] for c in CLUBS if c["canon"] == club)):
                continue
            if not any(a in s for a in next(c["aliases"] for c in COMPETITIONS if c["canon"] == comp)):
                continue
            if has_pronoun_subject(s):
                continue
            ev = participation_evidence(s)
            if not ev:
                continue
            result["facts"].append({"club": club, "competition": comp, "evidence": ev})
    return result


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    generated = datetime.now(timezone.utc).isoformat()
    candidates = []
    urls_tested = 0
    accessible_urls = 0

    # 1) Wiki (PT/EN) por clube
    for club_canon, pages in WIKI_CLUBS.items():
        for lang, url in pages.items():
            urls_tested += 1
            code, body = http_get(url)
            if code != 200:
                candidates.append(
                    {"url": url, "final_url": url, "domain": f"{lang}.wikipedia.org",
                     "http_status": code, "blocked_reason": "http_error", "facts": []}
                )
                continue
            accessible_urls += 1
            rec = scan_text(body, domain=f"{lang}.wikipedia.org", source_type="wiki_narrative", url=url)
            rec["final_url"] = url
            rec["blocked_reason"] = None
            candidates.append(rec)
            time.sleep(2)

    # 2) RSSSF (descoberta + fetch validado)
    rsssf_candidates: set[str] = set()
    for seed in RSSSF_SEEDS:
        urls_tested += 1
        code, body = http_get(seed)
        if code == 200:
            accessible_urls += 1
            for m in re.finditer(r"(?is)href\s*=\s*[\"']?([^\"'>\s]+)", body):
                href = m.group(1)
                if href.lower().endswith(".html") and href.lower() != seed.lower():
                    rsssf_candidates.add(urllib.parse.urljoin(seed, href))
        time.sleep(2)
    # limita a 6 candidatos por orcamento
    for url in sorted(rsssf_candidates)[:6]:
        urls_tested += 1
        code, body = http_get(url)
        if code != 200:
            continue
        accessible_urls += 1
        rec = scan_text(body, domain="rsssf.org", source_type="rsssf_participation", url=url)
        rec["final_url"] = url
        rec["blocked_reason"] = None
        candidates.append(rec)
        time.sleep(2)

    # 3) consolida fatos com colisao prevista
    fact_map: dict[tuple, dict] = {}
    for rec in candidates:
        for f in rec.get("facts", []):
            key = (f["club"], f["competition"], f["evidence"])
            entry = fact_map.setdefault(key, {"club": f["club"], "competition": f["competition"],
                                               "evidence": f["evidence"], "domains": set(), "sources": []})
            entry["domains"].add(rec["domain"])
            entry["sources"].append(rec["url"])

    facts = []
    full = partial = 0
    for (club, comp, ev), entry in fact_map.items():
        domains = sorted(entry["domains"])
        dcount = len(domains)
        if dcount >= 3:
            status = "full_collision"
            full += 1
        elif dcount == 2:
            status = "partial_collision"
            partial += 1
        else:
            status = "no_collision"
        facts.append(
            {
                "fact": f"{club} --DISPUTOU--> {comp}",
                "metadata": {"participation_evidence": ev},
                "sources": entry["sources"],
                "predicted_domains": domains,
                "predicted_domain_count": dcount,
                "predicted_publishers": domains,
                "predicted_publisher_families": sorted({d.split(".")[-2] if ".wikipedia" in d else "RSSSF" for d in domains}),
                "predicted_effective_publisher_count": dcount,
                "collision_status": status,
                "eligible_for_runtime": status == "full_collision",
                "blocking_reason": None if status == "full_collision" else "insufficient_independent_domains",
            }
        )

    summary = {
        "urls_tested": urls_tested,
        "accessible_urls": accessible_urls,
        "participant_pages_found": sum(1 for c in candidates if c.get("facts")),
        "disputou_full_collision_facts": full,
        "disputou_partial_collision_facts": partial,
        "predicted_new_verified": full,
        "predicted_records_total": 0,
        "predicted_unique_predicates": 0,
        "eligible_for_runtime": full >= 3,
        "recommended_next_step": (
            "#048.10F runtime condicional para DISPUTOU (apos Space no HEAD)."
            if full >= 3
            else "DISPUTOU sem colisao full >= 3 sob fontes gratuitas; reavaliar #055 (licenca) ou fonte estatica alternativa."
        ),
    }

    atlas = {
        "audit_id": "disputou_participation_atlas_059e",
        "generated_at": generated,
        "policy": {
            "allowed_clubs": [c["canon"] for c in CLUBS],
            "allowed_competitions": [c["canon"] for c in COMPETITIONS],
            "preferred_evidence_order": ["explicit_participant", "group_stage", "knockout_participant", "finalist", "winner"],
            "forbidden_objects": FORBIDDEN_OBJECTS,
            "attribution": ATTRIBUTION,
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
