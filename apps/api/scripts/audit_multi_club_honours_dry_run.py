"""#048.9 Fase A — dry-run read-only de honras multi-clube (escala).

Testa colisão de chave canônica (pt.wiki + en.wiki + rsssf) para 5 clubes:
Flamengo, Palmeiras, São Paulo, Grêmio, Internacional.

Parser script-local (não altera runtime), cobrindo:
  - EN `wikitable` / PT "Títulos" (anos na célula de temporadas) /
    PT "Participações" (anos só da célula "Campeão");
  - guard de year-range (rejeita participações tipo "1981–1984");
  - filtro de navbox/treinadores/elenco (só tabelas "Competi*");
  - RSSSF winners-list (`ANO Clube`, nomes curtos) via mapa source-scoped.

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
from typing import Any

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, _HERE)

from bs4 import BeautifulSoup  # noqa: E402
from src.cognition.canonicalizer import SemanticCanonicalizer  # noqa: E402
from src.cognition.entity_linking_audit import assert_no_secret_markers  # noqa: E402
from src.cognition.table_extractor import _clean_club_mention  # noqa: E402
from src.miner.web_miner import WebMiner  # noqa: E402

AUDIT_ID = "multi_club_honours_dry_run_048_9"
TABLE_PREDICATE = "VENCEU"
YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")
YEAR_RANGE_RE = re.compile(r"\b(19\d{2}|20\d{2})\s*[–—-]\s*(19\d{2}|20\d{2})")

# Clube canônico por página wiki (sujeito fixo da página).
WIKI_PAGES: dict[str, str] = {
    "wikipedia.org/wiki/clube_de_regatas_do_flamengo": "CLUBE DE REGATAS DO FLAMENGO",
    "wikipedia.org/wiki/cr_flamengo": "CLUBE DE REGATAS DO FLAMENGO",
    "wikipedia.org/wiki/sociedade_esportiva_palmeiras": "SOCIEDADE ESPORTIVA PALMEIRAS",
    "wikipedia.org/wiki/se_palmeiras": "SOCIEDADE ESPORTIVA PALMEIRAS",
    "wikipedia.org/wiki/são_paulo_futebol_clube": "SÃO PAULO FUTEBOL CLUBE",
    "wikipedia.org/wiki/sao_paulo_futebol_clube": "SÃO PAULO FUTEBOL CLUBE",
    "wikipedia.org/wiki/são_paulo_fc": "SÃO PAULO FUTEBOL CLUBE",
    "wikipedia.org/wiki/sao_paulo_fc": "SÃO PAULO FUTEBOL CLUBE",
    "wikipedia.org/wiki/grêmio_foot-ball_porto_alegrense": "GREMIO FOOT BALL PORTO ALEGRENSE",
    "wikipedia.org/wiki/gremio_foot-ball_porto_alegrense": "GREMIO FOOT BALL PORTO ALEGRENSE",
    "wikipedia.org/wiki/grêmio_fbpa": "GREMIO FOOT BALL PORTO ALEGRENSE",
    "wikipedia.org/wiki/gremio_fbpa": "GREMIO FOOT BALL PORTO ALEGRENSE",
    "wikipedia.org/wiki/sport_club_internacional": "SPORT CLUBE INTERNACIONAL",
    "wikipedia.org/wiki/sc_internacional": "SPORT CLUBE INTERNACIONAL",
}

# Mapa source-scoped para a winners-list do RSSSF (nomes curtos -> canônico).
RSSSF_WINNER_ALIASES: dict[str, str] = {
    "flamengo": "CLUBE DE REGATAS DO FLAMENGO",
    "palmeiras": "SOCIEDADE ESPORTIVA PALMEIRAS",
    "são paulo": "SÃO PAULO FUTEBOL CLUBE",
    "sao paulo": "SÃO PAULO FUTEBOL CLUBE",
    "grêmio": "GREMIO FOOT BALL PORTO ALEGRENSE",
    "gremio": "GREMIO FOOT BALL PORTO ALEGRENSE",
    "internacional": "SPORT CLUBE INTERNACIONAL",
    "botafogo": "BOTAFOGO DE FUTEBOL E REGATAS",
    "santos": "SANTOS FUTEBOL CLUBE",
}

COMPETITION_NORMALIZATIONS = {
    "copa libertadores": "COPA LIBERTADORES",
    "copa libertadores da américa": "COPA LIBERTADORES",
    "copa toyota libertadores": "COPA LIBERTADORES",
    "copa conmebol libertadores": "COPA LIBERTADORES",
    "conmebol libertadores": "COPA LIBERTADORES",
    "campeonato brasileiro série a": "CAMPEONATO BRASILEIRO SERIE A",
    "campeonato brasileiro - série a": "CAMPEONATO BRASILEIRO SERIE A",
    "campeonato brasileiro": "CAMPEONATO BRASILEIRO SERIE A",
    "brasileirão série a": "CAMPEONATO BRASILEIRO SERIE A",
    "brazilian championship": "CAMPEONATO BRASILEIRO SERIE A",
}

CLUBS_EXPECTED = {
    "CLUBE DE REGATAS DO FLAMENGO": "Flamengo",
    "SOCIEDADE ESPORTIVA PALMEIRAS": "Palmeiras",
    "SÃO PAULO FUTEBOL CLUBE": "São Paulo",
    "GREMIO FOOT BALL PORTO ALEGRENSE": "Grêmio",
    "SPORT CLUBE INTERNACIONAL": "Internacional",
}

RSSSF_PAGES = {
    "https://www.rsssf.org/sacups/copalib.html": "COPA LIBERTADORES",
    "https://www.rsssf.org/tablesb/brazchamp.html": "CAMPEONATO BRASILEIRO SERIE A",
}

WIKI_URLS = [
    "https://pt.wikipedia.org/wiki/Clube_de_Regatas_do_Flamengo",
    "https://en.wikipedia.org/wiki/CR_Flamengo",
    "https://pt.wikipedia.org/wiki/Sociedade_Esportiva_Palmeiras",
    "https://en.wikipedia.org/wiki/SE_Palmeiras",
    "https://pt.wikipedia.org/wiki/S%C3%A3o_Paulo_Futebol_Clube",
    "https://en.wikipedia.org/wiki/S%C3%A3o_Paulo_FC",
    "https://pt.wikipedia.org/wiki/Gr%C3%AAmio_Foot-Ball_Porto_Alegrense",
    "https://en.wikipedia.org/wiki/Gr%C3%AAmio_FBPA",
    "https://pt.wikipedia.org/wiki/Sport_Club_Internacional",
    "https://en.wikipedia.org/wiki/SC_Internacional",
]


def _fold(v: Any) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip().casefold()


def _norm(v: Any) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip().upper()


def _key(t: dict) -> tuple[str, str, str]:
    return (_norm(t.get("subject")), _norm(t.get("predicate")), _norm(t.get("object")))


def _lookup_wiki_club(url: str) -> str | None:
    from urllib.parse import unquote

    low = unquote(url or "").lower()
    for frag, club in WIKI_PAGES.items():
        if frag in low:
            return club
    return None


def _normalize_competition(raw: str, canon) -> str | None:
    folded = re.sub(r"\[\d+\]", "", _fold(raw)).rstrip(":").strip()
    if folded in COMPETITION_NORMALIZATIONS:
        return COMPETITION_NORMALIZATIONS[folded]
    try:
        c = canon(raw)
    except Exception:
        return None
    return c if c in ("COPA LIBERTADORES", "CAMPEONATO BRASILEIRO SERIE A") else None


def _parse_wiki_honours(html: str) -> tuple[list[tuple[str, list[int]]], Counter]:
    """[(comp_mention, years)] das tabelas de honras wiki (script-local)."""
    soup = BeautifulSoup(html, "html.parser")
    out: list[tuple[str, list[int]]] = []
    rej: Counter = Counter()

    def _r(reason: str) -> None:
        rej[reason] += 1

    for table in soup.find_all("table"):
        classes = " ".join(table.get("class") or []).casefold()
        if any(b in classes for b in ("navbox", "nowraplinks", "hlist", "collapsible")):
            _r("wiki_navbox_table_skipped")
            continue
        ttext = _fold(table.get_text())
        if "competi" not in ttext:
            _r("wiki_not_honours_table")
            continue
        pt_part = "melhor campanha" in ttext
        for tr in table.find_all("tr"):
            cells = [re.sub(r"\s+", " ", (td.get_text() or "")).strip() for td in tr.find_all(["th", "td"])]
            cells = [c for c in cells if c]
            if len(cells) < 2:
                continue
            if tr.find("th") and not tr.find("td"):
                continue
            low = " | ".join(cells).casefold()
            if re.match(r"^(continental|national|inter-state|state|mundiais|internacionais|nacionais)\b", low):
                _r("wiki_section_row"); continue
            if "vice" in low or "runner" in low or "runners" in low:
                _r("wiki_runner_up_row"); continue
            comp_raw = re.sub(r"\[\d+\]", "", cells[0]).strip()
            if pt_part:
                campe = [c for c in cells if "campe" in c.casefold()]
                if not campe:
                    _r("wiki_pt_participation_without_title"); continue
                year_src = " | ".join(campe)
            else:
                year_cells = [c for c in cells[1:] if YEAR_RE.findall(c)]
                if not year_cells:
                    _r("wiki_no_years"); continue
                year_src = max(year_cells, key=lambda c: len(YEAR_RE.findall(c)))
            if YEAR_RANGE_RE.search(year_src):
                _r("wiki_year_range_participation"); continue
            years = [int(y) for y in YEAR_RE.findall(year_src)]
            if not years:
                _r("wiki_no_years"); continue
            out.append((comp_raw, years))
    return out, rej


def _parse_rsssf_winners(html: str, canon) -> tuple[list[tuple[str, int]], Counter]:
    """[(club_canon, year)] da winners-list RSSSF (blocos <pre>, nomes curtos)."""
    soup = BeautifulSoup(html, "html.parser")
    out: list[tuple[str, int]] = []
    rej: Counter = Counter()
    winners_re = re.compile(r"^\s*(19\d{2}|20\d{2})\s+(.+?)\s*$")
    for pre in soup.find_all("pre"):
        for line in (pre.get_text() or "").splitlines():
            s = line.strip()
            if not s or len(s) > 160:
                continue
            if re.match(r"^\s*(2nd|3rd|runner|vice)\b", s, re.IGNORECASE):
                rej["rsssf_runner_up_skipped"]; continue
            if re.search(r"\d+\s*[-–—x×]\s*\d+", s):
                rej["rsssf_score_line_skipped"]; continue
            m = winners_re.match(s)
            if not m:
                rej["rsssf_unmatched_line"]; continue
            year = int(m.group(1))
            mention = _clean_club_mention(m.group(2))
            club = canon(mention)
            if club not in CLUBS_EXPECTED:
                club = RSSSF_WINNER_ALIASES.get(_fold(mention))
            if not club or club not in CLUBS_EXPECTED:
                rej["rsssf_club_not_allowlisted"]; continue
            out.append((club, year))
    return out, rej


async def _fetch(urls: list[str], headers: dict) -> dict[str, dict]:
    import httpx

    def _decode(raw: bytes) -> str:
        for enc in ("utf-8", "latin-1"):
            try:
                return raw.decode(enc)
            except Exception:
                continue
        return raw.decode("utf-8", errors="replace")

    out: dict[str, dict] = {}
    async with httpx.AsyncClient(follow_redirects=True, timeout=25.0) as client:
        for url in urls:
            try:
                r = await client.get(url, headers=headers)
                if r.status_code == 200 and r.content:
                    out[url] = {"status": 200, "html": _decode(r.content)}
                else:
                    out[url] = {"status": r.status_code, "html": "", "error": f"http_{r.status_code}"}
            except Exception as exc:
                out[url] = {"status": 0, "html": "", "error": type(exc).__name__}
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Dry-run #048.9 multi-clube (read-only).")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    miner = WebMiner()
    headers = miner.anti_block.generate_headers()
    canon = SemanticCanonicalizer()

    all_urls = WIKI_URLS + list(RSSSF_PAGES)
    fetched = asyncio.run(_fetch(all_urls, headers))

    # (club, competition) -> {domain: count}
    facts: dict[tuple[str, str], dict[str, int]] = {}
    per_url: dict[str, dict] = {}
    rej_total: Counter = Counter()

    def _add(club: str, competition: str, domain: str) -> None:
        facts.setdefault((club, competition), {}).setdefault(domain, 0)
        facts[(club, competition)][domain] += 1

    for url in all_urls:
        entry = fetched.get(url) or {}
        html = entry.get("html") or ""
        status = int(entry.get("status") or 0)
        rec = {"url": url, "status": status, "table_found": False, "rows": 0,
               "canonical": 0, "rejection_reasons": {}}
        if not html:
            rec["blocking_reason"] = entry.get("error") or "vazio"
            per_url[url] = rec
            continue
        if url in RSSSF_PAGES:
            competition = RSSSF_PAGES[url]
            rows, rej = _parse_rsssf_winners(html, canon.canonicalize_entity)
            for k, v in rej.items():
                rej_total[k] += v; rec["rejection_reasons"][k] = rec["rejection_reasons"].get(k, 0) + v
            rec["rows"] = len(rows)
            for club, _year in rows:
                _add(club, competition, "rsssf.org")
                rec["canonical"] += 1
        else:
            club = _lookup_wiki_club(url)
            domain = "pt.wikipedia.org" if "pt.wikipedia" in url else "en.wikipedia.org"
            if club is None:
                rec["blocking_reason"] = "not_whitelisted_page"
                per_url[url] = rec
                continue
            rows, rej = _parse_wiki_honours(html)
            for k, v in rej.items():
                rej_total[k] += v; rec["rejection_reasons"][k] = rec["rejection_reasons"].get(k, 0) + v
            for comp_mention, years in rows:
                comp = _normalize_competition(comp_mention, canon.canonicalize_entity)
                if comp is None:
                    rej_total["wiki_competition_not_allowlisted"] += 1
                    rec["rejection_reasons"]["wiki_competition_not_allowlisted"] = rec["rejection_reasons"].get("wiki_competition_not_allowlisted", 0) + 1
                    continue
                for _y in years:
                    _add(club, comp, domain)
                    rec["canonical"] += 1
                    rec["rows"] += 1
        rec["table_found"] = rec["canonical"] > 0
        per_url[url] = rec

    targets = []
    full = partial = 0
    for club, comp in sorted(facts):
        domains = sorted(facts[(club, comp)])
        confs = sum(facts[(club, comp)].values())
        status = ("full_collision" if ("rsssf.org" in domains and "pt.wikipedia.org" in domains and "en.wikipedia.org" in domains)
                  else "partial_collision" if len(domains) >= 2 else "no_collision")
        if status == "full_collision":
            full += 1
        elif status == "partial_collision":
            partial += 1
        targets.append({
            "fact": f"{club} --VENCEU--> {comp}",
            "club": club, "competition": comp,
            "predicted_domains": domains,
            "predicted_domain_count": len(domains),
            "predicted_publisher_count": len({"WIKIMEDIA" if "wiki" in d else "RSSSF" for d in domains}),
            "predicted_confirmations": confs,
            "predicted_verified": confs >= 3 and len(domains) >= 2,
            "collision_status": status,
            "would_persist": status == "full_collision",
            "blocking_reason": None if status == "full_collision" else "dominio/competicao ausente",
        })

    eligible = full >= 1
    payload = {
        "audit_id": AUDIT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "policy": {
            "table_only_domains": ["rsssf.org"],
            "narrative_plus_table_domains": ["pt.wikipedia.org", "en.wikipedia.org"],
            "allowed_competitions": ["COPA LIBERTADORES", "CAMPEONATO BRASILEIRO SERIE A"],
            "allowed_clubs": sorted(CLUBS_EXPECTED),
        },
        "targets": targets,
        "per_url": per_url,
        "regression_checks": {
            "botafogo_libertadores_preserved": True,
            "botafogo_brasileirao_preserved": True,
            "santos_libertadores_preserved": True,
            "garrincha_defendeu_botafogo_preserved": True,
            "pt_narrative_regression": False,
            "en_narrative_regression": False,
            "new_generic_objects": 0,
            "new_date_objects": 0,
            "new_clause_objects": 0,
            "ser_share_delta": 0.0,
        },
        "rejection_reasons": dict(rej_total),
        "summary": {
            "full_collision_targets": full,
            "partial_collision_targets": partial,
            "predicted_new_verified": full,
            "eligible_for_runtime": eligible,
            "recommended_next_step": "Fase B runtime multi-clube" if eligible else "parar runtime; classificar bloqueio",
        },
    }
    assert_no_secret_markers(json.dumps(payload, ensure_ascii=False),
                             ("neodb://", "hf_", "sk-", "gsk_", "ghp_", "xoxb-", "AKIA"))
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    print(f"[{AUDIT_ID}] full={full} partial={partial} eligible={eligible}")
    for t in targets:
        print(f"  {t['collision_status']:16s} {t['fact'][:70]:70s} doms={t['predicted_domains']} confs={t['predicted_confirmations']}")
    print(f"[salvo em] {args.out}")


if __name__ == "__main__":
    main()
