"""#048.6 batch 2.1 — Descoberta e validacao offline de URLs article-like.

Busca DuckDuckGo HTML por queries focadas em artigos declarativos,
extrai URLs article-like (nao homepages/secoes/tabelas),
valida offline se produzem o fato-alvo canonico.

Read-only: apenas GET publicos + extracao local. Nada gravado.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone
from urllib.parse import parse_qs, unquote, urlparse

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, _HERE)

import httpx  # noqa: E402
import audit_cluster_productivity as base  # noqa: E402
import audit_extraction_gap as gap  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402
from src.cognition.canonicalizer import SemanticCanonicalizer  # noqa: E402
from src.cognition.entity_linking_audit import assert_no_secret_markers  # noqa: E402
from src.cognition.extractor import EntityExtractor  # noqa: E402

DDG = "https://html.duckduckgo.com/html/"

TARGET_FACTS = {
    "garrincha_botafogo_p0": {
        "subject_any": ["GARRINCHA", "MANUEL FRANCISCO DOS SANTOS", "MANOEL FRANCISCO DOS SANTOS"],
        "object_any": ["BOTAFOGO", "BOTAFOGO DE FUTEBOL E REGATAS", "CLUBE DE REGATAS BOTAFOGO"],
        "predicates": ["DEFENDEU"],
        "queries": [
            '"Garrincha" "Botafogo" "played for"',
            '"Manuel Francisco dos Santos" "Botafogo"',
            '"Garrincha" "defendeu" "Botafogo"',
            '"Garrincha" "jogou pelo" "Botafogo"',
            '"Garrincha" "Botafogo de Futebol e Regatas"',
            '"Garrincha" biography Botafogo',
            '"Garrincha" obituary Botafogo',
        ],
    },
    "pele_santos_p1": {
        "subject_any": ["PELE", "EDSON ARANTES DO NASCIMENTO", "O REI"],
        "object_any": ["SANTOS", "SANTOS FUTEBOL CLUBE", "SANTOS FC"],
        "predicates": ["DEFENDEU"],
        "queries": [
            '"Pele" "Santos" "played for"',
            '"Edson Arantes do Nascimento" "Santos"',
            '"Pele" "defendeu" "Santos"',
            '"Pele" "jogou pelo" "Santos"',
            '"Pele" biography "Santos FC"',
        ],
    },
    "botafogo_libertadores_p2": {
        "subject_any": ["BOTAFOGO", "BOTAFOGO DE FUTEBOL E REGATAS"],
        "object_any": ["LIBERTADORES", "COPA LIBERTADORES", "COPA CONMEBOL LIBERTADORES", "CONMEBOL LIBERTADORES"],
        "predicates": ["VENCEU"],
        "queries": [
            '"Botafogo" "won" "Copa Libertadores"',
            '"Botafogo" "venceu" "Copa Libertadores"',
            '"Botafogo de Futebol e Regatas" "Libertadores"',
            '"Botafogo" "Libertadores 2024" final',
        ],
    },
    "botafogo_brasileirao_p3": {
        "subject_any": ["BOTAFOGO", "BOTAFOGO DE FUTEBOL E REGATAS"],
        "object_any": ["BRASILEIRO", "CAMPEONATO BRASILEIRO", "BRASILEIRAO", "CAMPEONATO BRASILEIRO SERIE A"],
        "predicates": ["VENCEU"],
        "queries": [
            '"Botafogo" "won" "Brasileirao"',
            '"Botafogo" "venceu" "Brasileirao"',
            '"Botafogo" "Campeonato Brasileiro" 2024',
            '"Botafogo de Futebol e Regatas" "Serie A" champion',
        ],
    },
    "santos_estadio_p4": {
        "subject_any": ["SANTOS", "SANTOS FUTEBOL CLUBE", "SANTOS FC"],
        "object_any": ["ESTADIO URBANO CALDEIRA", "VILA BELMIRO"],
        "predicates": ["POSSUIR"],
        "queries": [
            '"Santos FC" "Vila Belmiro"',
            '"Santos Futebol Clube" "Estadio Urbano Caldeira"',
            '"Santos FC" "home ground"',
            '"Santos FC" owns stadium',
        ],
    },
}

# Bloqueios: homepage, secao, busca, listing, tabela, JS-only, paywall, social, video, Almanaque.
# Dominios bloqueados (wiki, social, betting, paywall pesado, JS-heavy, lojas).
BLOCKED_DOMAIN_SUBSTR = (
    "wikipedia.org", "wikidata.org", "dbpedia", "wikiwand", "wikizero", "everipedia",
    "facebook.com", "instagram.com", "twitter.com", "x.com/", "tiktok.com", "youtube.com",
    "vimeo.com", "dailymotion.com", "linkedin.com", "pinterest.com", "reddit.com",
    "botafogo.com.br", "santosfc.com.br",
    "mercadolivre", "shopee", "olx.", "enjoei", "magazineluiza",
    "almanaquedosclubes",
)
# Padroes de URL que indicam homepage/secao/listing/tag/busca (nao artigo).
BLOCKED_URL_PATTERNS = (
    "/futebol/times/", "/futebol/", "/esporte/futebol/", "/esportes/",
    "/tag/", "/tags/", "/categoria/", "/category/", "/search", "/busca",
    "/times/", "/clubes/", "/competicoes/", "/blog/", "/blogs/",
)
# Dominios de paywall/login conhecido (bloquear sem tentar? tentar 1x e marcar).
PAYWALL_HINT = ("uol.com.br", "estadao.com.br", "folha.uol.com.br", "olglobo.com", "lance.com.br")


def _unwrap(href: str) -> str:
    if "duckduckgo.com/l/" in href:
        qs = parse_qs(urlparse(href).query)
        if "uddg" in qs:
            return unquote(qs["uddg"][0])
    return href


def _norm(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().upper()


def validate_candidate(url: str) -> tuple[bool, str]:
    low = url.lower()
    if not low.startswith("https://"):
        return False, "sem_https"
    for bad in BLOCKED_DOMAIN_SUBSTR:
        if bad in low:
            return False, f"bloqueado_dominio:{bad}"
    path = urlparse(low).path or "/"
    for pat in BLOCKED_URL_PATTERNS:
        if pat in path and len(path) < len(pat) + 30:
            return False, f"provavel_secao:{pat}"
    return True, "ok"


def _is_target(triple: dict, target: dict) -> bool:
    s = _norm(triple.get("subject"))
    p = _norm(triple.get("predicate"))
    o = _norm(triple.get("object"))
    subj_ok = any(tok in s for tok in target["subject_any"])
    obj_ok = any(tok in o for tok in target["object_any"])
    pred_ok = p in target["predicates"]
    return subj_ok and obj_ok and pred_ok


UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


async def discover_for_target(client: httpx.AsyncClient, queries: list[str], max_urls: int = 12) -> list[dict]:
    """Retorna URLs article-like descobertas via DDG HTML."""
    found: list[dict] = []
    seen: set[str] = set()
    for q in queries:
        try:
            r = await client.get(DDG, params={"q": q})
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.select("a.result__a"):
                href = _unwrap(a.get("href") or "")
                if not href.startswith("http") or href in seen:
                    continue
                seen.add(href)
                good, why = validate_candidate(href)
                found.append({"url": href, "query": q, "precheck": why if not good else "ok", "eligible_precheck": good})
                if len(found) >= max_urls * 2:
                    break
        except Exception:
            continue
        if len(found) >= max_urls * 2:
            break
    return found


async def evaluate_url(url: str, target: dict, extractor: EntityExtractor, canon: SemanticCanonicalizer) -> dict:
    miner = base.WebMiner()
    headers = miner.anti_block.generate_headers()
    async with httpx.AsyncClient(follow_redirects=True, timeout=25.0, headers={"User-Agent": UA}) as client:
        fetched = await base.fetch_one(client, url, headers)
    status = fetched.get("status", 0)
    html = fetched.get("html") or ""
    error = fetched.get("error") or ""
    final_url = fetched.get("final_url") or url
    if not html:
        return {"url": url, "status": status, "fetch_issue": error or "empty_html"}

    text = miner.clean_html(html, source_url=url).get("content") or ""
    if not text or len(text) < 300:
        return {"url": url, "status": status, "fetch_issue": "clean_html_empty_or_short", "text_length": len(text)}

    raw = [t.to_dict() for t in extractor.extract(text, max_triples=25)]
    canonical, _failures = gap.refine_with_reasons(raw, canon)
    targets = [t for t in canonical if _is_target(t, target)]

    parsed = urlparse(final_url)
    domain = parsed.netloc.lower()
    publisher = domain.split(".")[-2] if "." in domain else domain

    return {
        "url": url,
        "final_url": final_url,
        "domain": domain,
        "publisher": publisher,
        "source_type": "article-like",
        "http_status": status,
        "cleaned_text_length": len(text),
        "raw_triples": len(raw),
        "canonical_triples": len(canonical),
        "target_fact_hits": len(targets),
        "target_triples_sample": [
            {"subject": t.get("subject"), "predicate": t.get("predicate"), "object": t.get("object")}
            for t in targets[:3]
        ],
        "productive": bool(targets),
    }


async def run(max_discover: int = 12, max_validate: int = 8) -> dict:
    extractor = EntityExtractor(enable_fallback=True)
    canon = SemanticCanonicalizer()
    clusters: dict[str, list[dict]] = {}
    async with httpx.AsyncClient(
        follow_redirects=True, timeout=30.0,
        headers={"User-Agent": UA, "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8"},
    ) as dclient:
        for cluster_id, target in TARGET_FACTS.items():
            discovered = await discover_for_target(dclient, target["queries"], max_urls=max_discover)
            results: list[dict] = []
            validated = 0
            for item in discovered:
                if validated >= max_validate:
                    break
                if not item["eligible_precheck"]:
                    item.update({"eligible_for_seed": False, "blocking_reason": item["precheck"]})
                    results.append(item)
                    continue
                ev = await evaluate_url(item["url"], target, extractor, canon)
                entry = {"cluster_id": cluster_id, "query": item["query"], **ev}
                eligible = (
                    entry.get("http_status") == 200
                    and entry.get("cleaned_text_length", 0) > 300
                    and entry.get("canonical_triples", 0) >= 1
                    and entry.get("target_fact_hits", 0) >= 1
                )
                entry["eligible_for_seed"] = bool(eligible)
                if not eligible:
                    reasons = []
                    if entry.get("http_status") != 200:
                        reasons.append(f"http_{entry.get('http_status')}")
                    if entry.get("fetch_issue"):
                        reasons.append(f"fetch:{entry['fetch_issue']}")
                    if entry.get("canonical_triples", 0) < 1:
                        reasons.append("no_canonical")
                    if entry.get("target_fact_hits", 0) < 1:
                        reasons.append("no_target_fact")
                    entry["blocking_reason"] = ";".join(reasons) if reasons else "unknown"
                results.append(entry)
                validated += 1
            clusters[cluster_id] = results

    summary = {
        cid: {
            "tested": len([r for r in res if r.get("eligible_for_seed") is not None]),
            "eligible": len([r for r in res if r.get("eligible_for_seed")]),
            "eligible_urls": [r["url"] for r in res if r.get("eligible_for_seed")],
        }
        for cid, res in clusters.items()
    }
    payload = {
        "audit_id": "third_domain_candidates_048_6_batch2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "extractor": "EntityExtractor(enable_fallback=True) [F1 default ON]",
        "note": "Fase 2.1: apenas URLs article-like com frase declarativa; SER nao elegivel para DEFENDEU.",
        "clusters": clusters,
        "summary": summary,
    }
    assert_no_secret_markers(
        json.dumps(payload, ensure_ascii=False),
        ("neodb://", "hf_", "sk-", "gsk_", "ghp_", "xoxb-", "AKIA"),
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Fase 2.1: descoberta article-like (#048.6 batch2).")
    parser.add_argument("--out", required=True)
    parser.add_argument("--max-discover", type=int, default=12)
    parser.add_argument("--max-validate", type=int, default=8)
    args = parser.parse_args()
    payload = asyncio.run(run(max_discover=args.max_discover, max_validate=args.max_validate))
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    for cid, res in payload["clusters"].items():
        print(f"=== {cid} ===")
        for r in res:
            if r.get("eligible_for_seed") is None:
                print(f"  SKIP {r['url']}")
            else:
                tag = "ELIGIVEL" if r.get("eligible_for_seed") else f"NEGADO:{r.get('blocking_reason')}"
                print(f"  {tag} canon={r.get('canonical_triples',0)} hits={r.get('target_fact_hits',0)} {r['url']}")
        print(f"  elegiveis: {payload['summary'][cid]['eligible']}")
    print(f"[salvo em] {args.out}")


if __name__ == "__main__":
    main()
