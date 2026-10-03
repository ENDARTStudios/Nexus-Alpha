"""#048.6 — Auditoria read-only de terceiras fontes independentes produtivas.

Valida candidatas a terceira fonte para clusters com duplicate_cross_domain > 0,
verificando se extraem o fato-alvo canônico e atendem critérios de elegibilidade.

Read-only: apenas GET de páginas públicas + extração local. Nada é gravado.
Anti-leak: nenhum corpo de texto no relatório.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, _HERE)

import httpx  # noqa: E402

import audit_cluster_productivity as base  # noqa: E402
import audit_extraction_gap as gap  # noqa: E402
from src.cognition.canonicalizer import SemanticCanonicalizer  # noqa: E402
from src.cognition.entity_linking_audit import (  # noqa: E402
    assert_no_secret_markers,
)
from src.cognition.extractor import EntityExtractor  # noqa: E402

# Fatos-alvo por cluster (baseado em duplicate_cross_domain > 0)
TARGET_FACTS = {
    "garrincha_botafogo": {
        "subject_any": ["GARRINCHA", "MANUEL FRANCISCO DOS SANTOS", "MANOEL FRANCISCO DOS SANTOS"],
        "object_any": ["BOTAFOGO", "BOTAFOGO DE FUTEBOL E REGATAS", "CLUBE DE REGATAS BOTAFOGO"],
        "predicates": ["DEFENDEU", "JOGOU", "ATUOU", "TATUOU", "JOGOU_PARA", "PERTENCEU"],
    },
    "pele_santos": {
        "subject_any": ["PELE", "EDSON ARANTES DO NASCIMENTO", "O REI"],
        "object_any": ["SANTOS", "SANTOS FUTEBOL CLUBE", "SANTOS FC"],
        "predicates": ["DEFENDEU", "JOGOU", "ATUOU", "TATUOU", "PERTENCEU"],
    },
    "santos_estadio": {
        "subject_any": ["SANTOS", "SANTOS FUTEBOL CLUBE", "SANTOS FC"],
        "object_any": ["ESTADIO URBANO CALDEIRA", "VILA BELMIRO", "ESTÁDIO URBANO CALDEIRA"],
        "predicates": ["POSSUIR", "MANDAR", "UTILIZAR", "LOCALIZADO_EM"],
    },
    "botafogo_libertadores": {
        "subject_any": ["BOTAFOGO", "BOTAFOGO DE FUTEBOL E REGATAS"],
        "object_any": ["LIBERTADORES", "COPA LIBERTADORES", "COPA CONMEBOL LIBERTADORES", "CONMEBOL LIBERTADORES"],
        "predicates": ["VENCEU", "DISPUTOU", "CONQUISTOU", "GANHOU", "CAMPEAO"],
    },
    "botafogo_brasileirao": {
        "subject_any": ["BOTAFOGO", "BOTAFOGO DE FUTEBOL E REGATAS"],
        "object_any": ["BRASILEIRO", "CAMPEONATO BRASILEIRO", "BRASILEIRAO", "CAMPEONATO BRASILEIRO SERIE A", "CAMPEONATO BRASILEIRO SÉRIE A"],
        "predicates": ["VENCEU", "DISPUTOU", "CONQUISTOU", "GANHOU", "CAMPEAO"],
    },
}

# Domínios bloqueados: wiki/mirrors/social/betting/paywall/JS-only
# NOTA: grandes sites de notícias (reuters, apnews, theguardian, fifa, cbf, conmebol, britannica)
# NÃO são bloqueados aqui — são testados; paywall/403/404 serão detectados no fetch.
BLOCKED_SUBSTR = (
    "wikipedia.org", "wikidata.org", "dbpedia", "wikiwand", "wikizero", "everipedia",
    "facebook.com", "instagram.com", "twitter.com", "x.com/", "tiktok.com", "youtube.com",
    "linkedin.com", "pinterest", "reddit.com",
    "botafogo.com.br", "santosfc.com.br",  # JS-heavy, já no cluster
    "mercadolivre.com.br", "shopee.com.br", "lojagloriosa", "soualvinegro", "playforacause",
)

# Candidatas por cluster (ordem de prioridade)
CANDIDATES = {
    "garrincha_botafogo": [
        "https://www.britannica.com/topic/Botafogo-de-Futebol-e-Regatas",
        "https://www.britannica.com/biography/Garrincha",
        "https://www.theguardian.com/football/blog/2009/dec/20/garrincha-botafogo",
        "https://www.fifa.com/",
        "https://www.cbf.com.br/",
        "https://ge.globo.com/futebol/times/botafogo/",
        "https://www.uol.com.br/esporte/futebol/",
        "https://www.estadao.com.br/",
        "https://www.rsssfbrasil.com/",
    ],
    "pele_santos": [
        "https://www.santosfc.com.br/",
        "https://www.fifa.com/",
        "https://www.cbf.com.br/",
        "https://www.britannica.com/biography/Pele",
        "https://www.theguardian.com/football/pele",
        "https://ge.globo.com/futebol/times/santos/",
        "https://www.uol.com.br/esporte/futebol/",
    ],
    "santos_estadio": [
        "https://www.santosfc.com.br/",
        "https://ge.globo.com/futebol/times/santos/",
        "https://www.uol.com.br/esporte/futebol/",
        "https://www.estadao.com.br/",
        "https://www.britannica.com/topic/Santos-Football-Club",
    ],
    "botafogo_libertadores": [
        "https://www.conmebol.com/",
        "https://www.reuters.com/",
        "https://apnews.com/",
        "https://ge.globo.com/futebol/times/botafogo/",
        "https://www.uol.com.br/esporte/futebol/",
        "https://www.estadao.com.br/",
    ],
    "botafogo_brasileirao": [
        "https://www.cbf.com.br/",
        "https://ge.globo.com/futebol/times/botafogo/",
        "https://www.uol.com.br/esporte/futebol/",
        "https://www.estadao.com.br/",
        "https://www.rsssfbrasil.com/",
    ],
}


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().upper()


def _key(triple: dict) -> tuple[str, str, str]:
    return (_norm(triple.get("subject")), _norm(triple.get("predicate")), _norm(triple.get("object")))


def _is_target(triple: dict, target: dict) -> bool:
    s, p, o = _key(triple)
    subj_ok = any(tok in s for tok in target["subject_any"])
    obj_ok = any(tok in o for tok in target["object_any"])
    pred_ok = p in target["predicates"]
    return subj_ok and obj_ok and pred_ok


def validate_candidate(url: str) -> tuple[bool, str]:
    low = url.lower()
    if not low.startswith("https://"):
        return False, "sem_https"
    for bad in BLOCKED_SUBSTR:
        if bad in low:
            return False, f"bloqueado:{bad}"
    return True, "ok"


async def evaluate_url(url: str, target: dict, extractor: EntityExtractor, canon: SemanticCanonicalizer) -> dict:
    miner = base.WebMiner()
    headers = miner.anti_block.generate_headers()
    async with httpx.AsyncClient(follow_redirects=True, timeout=25.0) as client:
        fetched = await base.fetch_one(client, url, headers)
    status = fetched.get("status", 0)
    html = fetched.get("html") or ""
    error = fetched.get("error") or ""

    if not html:
        return {"url": url, "status": status, "fetch_issue": error or "empty_html"}

    text = miner.clean_html(html, source_url=url).get("content") or ""
    if not text:
        return {"url": url, "status": status, "fetch_issue": "clean_html_empty"}

    raw = [t.to_dict() for t in extractor.extract(text, max_triples=25)]
    canonical, _failures = gap.refine_with_reasons(raw, canon)

    targets = [t for t in canonical if _is_target(t, target)]
    exact_match = any(
        _norm(t.get("subject")) in target["subject_any"] and
        _norm(t.get("object")) in target["object_any"] and
        _norm(t.get("predicate")) in target["predicates"]
        for t in canonical
    )

    return {
        "url": url,
        "status": status,
        "text_length": len(text),
        "raw_triples": len(raw),
        "canonical_triples": len(canonical),
        "target_triples": len(targets),
        "target_triples_sample": [
            {"subject": t.get("subject"), "predicate": t.get("predicate"), "object": t.get("object")}
            for t in targets[:3]
        ],
        "exact_canonical_match": exact_match,
        "productive": bool(targets),
    }


async def run(custom_candidates: dict | None = None, limit_per_cluster: int = 8) -> dict:
    cand = custom_candidates or CANDIDATES
    extractor = EntityExtractor(enable_fallback=True)
    canon = SemanticCanonicalizer()

    results: dict[str, list[dict]] = {}
    for cluster_id, urls in cand.items():
        target = TARGET_FACTS.get(cluster_id, {})
        cluster_results = []
        tested = 0
        for url in urls:
            if tested >= limit_per_cluster:
                break
            good, why = validate_candidate(url)
            if not good:
                cluster_results.append({"url": url, "eligible_for_seed": False, "blocking_reason": why})
                continue
            result = await evaluate_url(url, target, extractor, canon)
            eligible = (
                result.get("status") == 200 and
                result.get("productive") and
                result.get("canonical_triples", 0) >= 1 and
                result.get("target_triples", 0) >= 1
            )
            result["eligible_for_seed"] = eligible
            if not eligible:
                reasons = []
                if result.get("status") != 200:
                    reasons.append(f"http_status_{result.get('status')}")
                if result.get("fetch_issue"):
                    reasons.append(f"fetch:{result['fetch_issue']}")
                if result.get("canonical_triples", 0) < 1:
                    reasons.append("no_canonical")
                if result.get("target_triples", 0) < 1:
                    reasons.append("no_target_fact")
                result["blocking_reason"] = ";".join(reasons) if reasons else "unknown"
            cluster_results.append(result)
            tested += 1
        results[cluster_id] = cluster_results

    payload = {
        "audit_id": "third_domain_candidates_048_6",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "extractor": "EntityExtractor(enable_fallback=True) [F1 default ON]",
        "clusters": results,
        "summary": {
            cluster_id: {
                "total_tested": len([r for r in res if "eligible_for_seed" in r]),
                "eligible": len([r for r in res if r.get("eligible_for_seed")]),
                "eligible_urls": [r["url"] for r in res if r.get("eligible_for_seed")],
            }
            for cluster_id, res in results.items()
        },
    }
    assert_no_secret_markers(json.dumps(payload, ensure_ascii=False), ("neodb://", "hf_", "sk-", "gsk_", "ghp_", "xoxb-", "AKIA"))
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Auditoria read-only de terceiras fontes (#048.6).")
    parser.add_argument("--candidates", help="JSON file com candidatos customizados")
    parser.add_argument("--out", required=True)
    parser.add_argument("--limit", type=int, default=8)
    args = parser.parse_args()

    custom = None
    if args.candidates:
        with open(args.candidates, "r", encoding="utf-8") as fh:
            custom = json.load(fh)

    payload = asyncio.run(run(custom_candidates=custom, limit_per_cluster=args.limit))
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    for cluster_id, res in payload["clusters"].items():
        print(f"=== {cluster_id} ===")
        for r in res:
            if "eligible_for_seed" in r:
                tag = "✅ ELIGIBLE" if r.get("eligible_for_seed") else f"❌ {r.get('blocking_reason')}"
            else:
                tag = f"⛔ {r.get('blocking_reason')}"
            print(f"  {tag} {r['url']} (canon={r.get('canonical_triples',0)} target={r.get('target_triples',0)})")
        print(f"  eligible: {payload['summary'][cluster_id]['eligible']}")
    print(f"\n[salvo em] {args.out}")


if __name__ == "__main__":
    main()