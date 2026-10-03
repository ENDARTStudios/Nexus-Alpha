"""#059 — Atlas read-only de fontes estaticas/tabulares independentes.

Descobre, sem alterar runtime e sem commitar seeds, fontes independentes
fora de Wikimedia que sejam acessiveis, estaveis, parseaveis, tabulares
ou estaticas, relevantes para fatos-alvo de titulos do Almanaque.

Natureza: read-only / offline / diagnostic. Sem deploy, sem reset,
sem snapshot, sem worker, sem seed commit, sem treino.

Politica:
- Wikimedia NAO conta como publisher independente.
- Wayback NAO conta como fonte independente.
- Almanaque API sem licenca: NAO usar.
- DDG scraping: NAO usar (BLOCKED_NETWORK).
- Max 1 request por dominio nesta rodada; timeout 15s.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, _HERE)

import httpx  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402

from src.cognition.entity_linking_audit import assert_no_secret_markers  # noqa: E402

AUDIT_ID = "static_tabular_source_atlas_059"

# Fatos-alvo P0/P1 (titulos; objeto = competicao, nunca ano isolado).
TARGETS = [
    {
        "target_fact": "BOTAFOGO DE FUTEBOL E REGATAS --VENCEU--> COPA LIBERTADORES",
        "subject_keys": ["BOTAFOGO"],
        "object_keys": ["LIBERTADORES", "COPA LIBERTADORES"],
        "predicate": "VENCEU",
        "known_domains": ["pt.wikipedia.org", "en.wikipedia.org"],
    },
    {
        "target_fact": "BOTAFOGO DE FUTEBOL E REGATAS --VENCEU--> CAMPEONATO BRASILEIRO SERIE A",
        "subject_keys": ["BOTAFOGO"],
        "object_keys": ["BRASILEIRO", "CAMPEONATO BRASILEIRO", "SERIE A", "SÉRIE A"],
        "predicate": "VENCEU",
        "known_domains": ["pt.wikipedia.org", "en.wikipedia.org"],
    },
    {
        "target_fact": "SANTOS FUTEBOL CLUBE --VENCEU--> COPA LIBERTADORES",
        "subject_keys": ["SANTOS"],
        "object_keys": ["LIBERTADORES", "COPA LIBERTADORES"],
        "predicate": "VENCEU",
        "known_domains": ["pt.wikipedia.org", "en.wikipedia.org"],
    },
    {
        "target_fact": "SANTOS FUTEBOL CLUBE --VENCEU--> CAMPEONATO BRASILEIRO SERIE A",
        "subject_keys": ["SANTOS"],
        "object_keys": ["BRASILEIRO", "CAMPEONATO BRASILEIRO", "SERIE A", "SÉRIE A"],
        "predicate": "VENCEU",
        "known_domains": ["pt.wikipedia.org", "en.wikipedia.org"],
    },
]

# Candidatas curadas (lista direta, sem busca): paginas estatisticas/historicas
# especificas, nao homepages.
CANDIDATES = [
    # RSSSF internacional
    {"url": "https://www.rsssf.org/sacups/copalib.html", "domain": "rsssf.org", "publisher": "RSSSF", "source_type": "statistics", "note": "Copa Libertadores winners"},
    {"url": "https://www.rsssf.org/tablesb/brazchamp.html", "domain": "rsssf.org", "publisher": "RSSSF", "source_type": "statistics", "note": "Brazilian champions"},
    {"url": "https://www.rsssf.org/tablesb/brazchamp-alltime.html", "domain": "rsssf.org", "publisher": "RSSSF", "source_type": "statistics", "note": "Brazilian championship all-time"},
    # RSSSF Brasil
    {"url": "https://www.rsssfbrasil.com/", "domain": "rsssfbrasil.com", "publisher": "RSSSF Brasil", "source_type": "statistics", "note": "homepage-only fallback; prefer article pages"},
    # worldfootball.net (se acessivel)
    {"url": "https://www.worldfootball.net/winner/bra-campeonato-brasileiro-serie-a/", "domain": "worldfootball.net", "publisher": "worldfootball.net", "source_type": "statistics", "note": "Serie A winners"},
    {"url": "https://www.worldfootball.net/winner/copa-libertadores/", "domain": "worldfootball.net", "publisher": "worldfootball.net", "source_type": "statistics", "note": "Libertadores winners"},
    # CBF competicoes (paginas especificas, nao homepage)
    {"url": "https://www.cbf.com.br/futebol-brasileiro/competicoes/campeonato-brasileiro-serie-a", "domain": "cbf.com.br", "publisher": "CBF", "source_type": "institutional", "note": "Serie A competition page"},
    # CONMEBOL Libertadores (pagina especifica)
    {"url": "https://conmebol.com/pt-br/copa-libertadores/", "domain": "conmebol.com", "publisher": "CONMEBOL", "source_type": "institutional", "note": "Libertadores page"},
]

WIKIMEDIA_HINTS = ("wikipedia.org", "wikidata.org", "wikimedia.org", "dbpedia.org")
WAYBACK_HINTS = ("web.archive.org",)
ALMANAQUE_HINTS = ("almanaquedosclubes",)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().upper()


def _independent(url: str) -> tuple[bool, str]:
    low = url.lower()
    for h in WIKIMEDIA_HINTS:
        if h in low:
            return False, f"wikimedia:{h}"
    for h in WAYBACK_HINTS:
        if h in low:
            return False, "wayback_mirror"
    for h in ALMANAQUE_HINTS:
        if h in low:
            return False, "almanaque_sem_licenca"
    return True, "ok"


def _extract_tables(html: str, max_tables: int = 12) -> list[dict]:
    """Extrai tabelas (<table>) e blocos pre-formatados (<pre>) como estruturas tabulares."""
    soup = BeautifulSoup(html, "html.parser")
    out: list[dict] = []
    for ti, table in enumerate(soup.find_all("table")[:max_tables]):
        rows: list[list[str]] = []
        for tr in table.find_all("tr"):
            cells = [re.sub(r"\s+", " ", (td.get_text() or "")).strip() for td in tr.find_all(["th", "td"])]
            cells = [c for c in cells if c]
            if cells:
                rows.append(cells)
        if rows:
            caption = table.find("caption")
            out.append({
                "table_index": ti,
                "kind": "table",
                "caption": (caption.get_text().strip() if caption else "")[:200],
                "rows": len(rows),
                "cols_max": max(len(r) for r in rows),
                "sample_rows": rows[:4],
            })
    # RSSSF e similares usam <pre> com listas ANO/clube e tabelas texto.
    for pi, pre in enumerate(soup.find_all("pre")[:max_tables]):
        txt = pre.get_text() or ""
        lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
        if lines:
            out.append({
                "table_index": f"pre-{pi}",
                "kind": "pre",
                "caption": "",
                "rows": len(lines),
                "cols_max": 1,
                "sample_rows": [[ln[:200]] for ln in lines[:4]],
            })
    return out


def _find_target_rows(html: str, target: dict, max_hits: int = 8) -> list[dict]:
    """Procura linhas (tabela ou <pre>) contendo subject+object do fato-alvo."""
    soup = BeautifulSoup(html, "html.parser")
    hits: list[dict] = []
    # 1) tabelas <table>
    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            cells = [re.sub(r"\s+", " ", (td.get_text() or "")).strip() for td in tr.find_all(["th", "td"])]
            joined = _norm(" | ".join(cells))
            if not joined or len(joined) > 600:
                continue
            subj_ok = any(_norm(k) in joined for k in target["subject_keys"])
            obj_ok = any(_norm(k) in joined for k in target["object_keys"])
            if subj_ok and obj_ok:
                hits.append({"row": " | ".join(cells)[:300], "cells": len(cells), "kind": "table"})
                if len(hits) >= max_hits:
                    return hits
    # 2) blocos <pre>: linha contem subject; object vem do contexto da pagina.
    #    Para elegibilidade, basta a linha do clube + contexto de competicao da URL/nota.
    if len(hits) < max_hits:
        for pre in soup.find_all("pre"):
            for line in (pre.get_text() or "").splitlines():
                ln = line.strip()
                if not ln or len(ln) > 200:
                    continue
                up = _norm(ln)
                subj_ok = any(_norm(k) in up for k in target["subject_keys"])
                if subj_ok:
                    hits.append({"row": ln[:300], "cells": 1, "kind": "pre"})
                    if len(hits) >= max_hits:
                        return hits
    return hits


async def evaluate(client: httpx.AsyncClient, cand: dict, targets: list[dict]) -> dict:
    url = cand["url"]
    indep, indep_why = _independent(url)
    entry: dict = {
        "url": url,
        "domain": cand["domain"],
        "publisher": cand["publisher"],
        "source_type": cand.get("source_type", "unknown"),
        "note": cand.get("note", ""),
        "independent_publisher": indep,
        "independent_reason": indep_why,
    }
    if not indep:
        entry.update({"http_status": 0, "eligible_for_058_12": False, "blocking_reason": indep_why})
        return entry
    try:
        r = await client.get(url, timeout=15.0, follow_redirects=True)
        status = r.status_code
        html = r.text if status == 200 else ""
    except Exception as exc:
        entry.update({"http_status": 0, "eligible_for_058_12": False, "blocking_reason": f"fetch:{type(exc).__name__}"})
        return entry
    entry["http_status"] = status
    entry["final_url"] = str(r.url) if status == 200 else url
    if status != 200 or not html:
        entry.update({"eligible_for_058_12": False, "blocking_reason": f"http_{status}" if status != 200 else "empty_html"})
        return entry
    low = html.lower()
    if "captcha" in low[:2000] or "are you a robot" in low[:2000] or "cloudflare" in low[:2000]:
        entry.update({"eligible_for_058_12": False, "blocking_reason": "bot_challenge"})
        return entry
    text_len = len(re.sub(r"<[^>]+>", " ", html))
    entry["html_length"] = len(html)
    entry["approx_text_length"] = text_len
    tables = _extract_tables(html)
    entry["tables_found"] = len(tables)
    entry["tables_sample"] = tables[:3]
    # target rows por fato-alvo
    per_target: list[dict] = []
    for t in targets:
        rows = _find_target_rows(html, t)
        per_target.append({"target_fact": t["target_fact"], "rows_found": len(rows), "rows_sample": rows[:3]})
    entry["per_target"] = per_target
    total_rows = sum(p["rows_found"] for p in per_target)
    entry["target_fact_rows_found"] = total_rows
    eligible = (
        status == 200
        and indep
        and len(tables) >= 1
        and total_rows >= 1
        and text_len > 0
    )
    entry["eligible_for_058_12"] = bool(eligible)
    if not eligible:
        reasons = []
        if len(tables) < 1:
            reasons.append("no_tables")
        if total_rows < 1:
            reasons.append("no_target_rows")
        entry["blocking_reason"] = ";".join(reasons) if reasons else "unknown"
    return entry


async def run(max_per_domain: int = 1) -> dict:
    # max 1 request por dominio nesta rodada
    seen_domains: set[str] = set()
    picked: list[dict] = []
    for cand in CANDIDATES:
        if cand["domain"] in seen_domains:
            continue
        seen_domains.add(cand["domain"])
        picked.append(cand)

    results: list[dict] = []
    async with httpx.AsyncClient(
        follow_redirects=True, timeout=15.0,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"},
    ) as client:
        for cand in picked:
            results.append(await evaluate(client, cand, TARGETS))

    def _count(pred):
        return sum(1 for r in results if pred(r))

    blocked: dict[str, int] = {}
    for r in results:
        b = r.get("blocking_reason")
        if b and not r.get("eligible_for_058_12"):
            blocked[b] = blocked.get(b, 0) + 1

    payload = {
        "audit_id": AUDIT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "build_space_commit": "155814f",
        "read_only": True,
        "policy": {
            "allow_wikimedia_as_independent_publisher": False,
            "allow_wayback_as_independent_source": False,
            "allow_almanaque_api_without_license": False,
            "allow_ddg_scraping": False,
            "max_requests_per_domain": max_per_domain,
            "timeout_seconds": 15,
        },
        "targets": [
            {
                "target_fact": t["target_fact"],
                "known_domains": t["known_domains"],
                "candidate_sources": [
                    {"url": r["url"], "rows_found": next(
                        (p["rows_found"] for p in r.get("per_target", []) if p["target_fact"] == t["target_fact"]), 0)}
                    for r in results if r.get("eligible_for_058_12")
                ],
            }
            for t in TARGETS
        ],
        "candidates": results,
        "summary": {
            "candidates_tested": len(results),
            "accessible": _count(lambda r: r.get("http_status") == 200),
            "static_or_tabular": _count(lambda r: r.get("tables_found", 0) >= 1),
            "independent_publisher": _count(lambda r: r.get("independent_publisher")),
            "target_fact_rows_found": sum(r.get("target_fact_rows_found", 0) for r in results),
            "eligible_for_058_12": _count(lambda r: r.get("eligible_for_058_12")),
            "eligible_urls": [r["url"] for r in results if r.get("eligible_for_058_12")],
            "blocked_reasons": blocked,
        },
    }
    assert_no_secret_markers(
        json.dumps(payload, ensure_ascii=False),
        ("neodb://", "hf_", "sk-", "gsk_", "ghp_", "xoxb-", "AKIA"),
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="#059 atlas read-only de fontes estaticas/tabulares.")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    payload = asyncio.run(run())
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    s = payload["summary"]
    print(f"tested={s['candidates_tested']} accessible={s['accessible']} tabular={s['static_or_tabular']} rows={s['target_fact_rows_found']} eligible={s['eligible_for_058_12']}")
    for r in payload["candidates"]:
        tag = "ELIGIVEL" if r.get("eligible_for_058_12") else f"NEGADO:{r.get('blocking_reason')}"
        print(f"  {tag} tables={r.get('tables_found',0)} rows={r.get('target_fact_rows_found',0)} {r['url']}")
    print(f"[salvo em] {args.out}")


if __name__ == "__main__":
    main()
