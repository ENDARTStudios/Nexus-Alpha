"""#048.5 (Cenário B) — sonda read-only de produtividade por fonte.

Objetivo: encontrar uma 3ª fonte *produtiva* (fora de Wikipedia) que gere o
fato canônico ``MANUEL FRANCISCO DOS SANTOS -DEFENDEU-> BOTAFOGO DE FUTEBOL
E REGATAS`` (1ª corroboração cross-domain já existe via pt+en wiki). Se uma
fonte-produzir o fato, o quórum 3 (confs>=3 AND doms>=2) fecha.

Read-only: apenas GET de páginas públicas + extração local. Nada é gravado em
Neo4j/Qdrant. Anti-leak: nenhum corpo de texto vai para o relatório.
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
sys.path.insert(0, os.path.dirname(_HERE))
sys.path.insert(0, _HERE)

import audit_extraction_gap as gap  # noqa: E402
from src.cognition.canonicalizer import SemanticCanonicalizer  # noqa: E402
from src.cognition.entity_linking_audit import (  # noqa: E402
    assert_no_secret_markers,
)
from src.cognition.extractor import EntityExtractor  # noqa: E402
from src.miner.web_miner import WebMiner  # noqa: E402

# Fato canônico já presente no grafo (chave canônica do :Fato).
TARGET_KEY = ("MANUEL FRANCISCO DOS SANTOS", "DEFENDEU", "BOTAFOGO DE FUTEBOL E REGATAS")
GARRINCHA_TOKENS = ("garrincha", "manuel francisco dos santos", "man Manoel francisco dos santos".strip())
BOTAFOGO_TOKENS = ("botafogo", "clube de regatas botafogo", "botafogo de futebol e regatas")

# Domínios bloqueados: wiki/mirrors/社交/social/betting/JS-only/paywall.
BLOCKED_SUBSTR = (
    "wikipedia.org", "wikidata.org", "dbpedia", "wikiwand", "wikizero", "everipedia",
    "facebook.com", "instagram.com", "twitter.com", "x.com/", "tiktok.com", "youtube.com",
    "bet", "casino", "aposta", "linkedin.com", "pinterest", "reddit.com",
    "uol.com.br", "estadao.com.br", "folha.uol.com.br", "olglobo.com", "globo.com", "g1.globo",
    "lance.com.br", "netvasco", "terra.com.br", "sportv.globo", "premium",
    "botafogo.com.br",  # JS-only: já no cluster, 0 entidades no run 36261835211
)


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().upper()


def _key(triple: dict) -> tuple[str, str, str]:
    return (_norm(triple.get("subject")), _norm(triple.get("predicate")), _norm(triple.get("object")))


def _is_target(triple: dict) -> bool:
    s, p, o = _key(triple)
    subj_g = any(tok in s for tok in GARRINCHA_TOKENS)
    obj_b = any(tok in o for tok in BOTAFOGO_TOKENS)
    pred_ok = p in {"DEFENDEU", "JOGOU", "ATUOU", "TATUOU", "JOGOU_PARA", "PERTENCEU"}
    return subj_g and obj_b and pred_ok


def _exact_target(triple: dict) -> bool:
    return _key(triple) == TARGET_KEY


def evaluate(url: str, html: str, status: int) -> dict:
    """Extrai da página e mede o quanto ela é produtiva para o fato-alvo."""
    miner = WebMiner()
    text = miner.clean_html(html, source_url=url).get("content") or ""
    extractor = EntityExtractor(enable_fallback=True)  # F1 ativa (default)
    raw = [t.to_dict() for t in extractor.extract(text, max_triples=25)]
    canonical, _failures = gap.refine_with_reasons(raw, SemanticCanonicalizer())
    targets = [t for t in canonical if _is_target(t)]
    exact = [t for t in targets if _exact_target(t)]
    # também checa se o texto bruto (pré-refine) contém o par Garrincha+Botafogo
    text_up = re.sub(r"\s+", " ", text).upper()
    mentions_g = sum(1 for tok in GARRINCHA_TOKENS if tok in text_up)
    mentions_b = sum(1 for tok in BOTAFOGO_TOKENS if tok in text_up)
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
        "exact_canonical_match": bool(exact),
        "text_mentions_garrincha": mentions_g,
        "text_mentions_botafogo": mentions_b,
    }


def validate_candidate(url: str) -> tuple[bool, str]:
    low = url.lower()
    if not low.startswith("https://"):
        return False, "sem_https"
    for bad in BLOCKED_SUBSTR:
        if bad in low:
            return False, f"bloqueado:{bad}"
    return True, "ok"


async def run(candidates: list[str], limit: int) -> dict:
    miner = WebMiner()
    headers = miner.anti_block.generate_headers()
    ok_urls = []
    rejected = {}
    for url in candidates:
        good, why = validate_candidate(url)
        (ok_urls.append(url) if good else rejected.setdefault(url, why))
        if len(ok_urls) >= limit:
            break

    fetched = await gap.fetch_all(ok_urls, headers)
    results = []
    for url in ok_urls:
        entry = fetched.get(url) or {}
        html = entry.get("html") or ""
        status = int(entry.get("status") or 0)
        if not html:
            results.append({"url": url, "status": status, "fetch_issue": entry.get("error") or "vazio"})
            continue
        results.append(evaluate(url, html, status))

    payload = {
        "audit_id": "source_productivity_garrincha_botafogo_048_5",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target_canonical_key": list(TARGET_KEY),
        "read_only": True,
        "extractor": "EntityExtractor(enable_fallback=True) [F1 default ON]",
        "rejected_candidates": rejected,
        "results": results,
        "winners_exact_match": [r["url"] for r in results if r.get("exact_canonical_match")],
        "winners_target_triple": [r["url"] for r in results if r.get("target_triples")],
        "note": "productive = gera tripla canonica alvo; exact = chave identica ao :Fato existente",
    }
    assert_no_secret_markers(json.dumps(payload, ensure_ascii=False), ("neodb://", "hf_", "sk-", "gsk_", "ghp_", "xoxb-", "AKIA"))
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Sonda produtividade 3a fonte (read-only).")
    parser.add_argument("--candidates", required=True, help="JSON list de URLs candidatas")
    parser.add_argument("--out", required=True)
    parser.add_argument("--limit", type=int, default=12)
    args = parser.parse_args()

    with open(args.candidates, "r", encoding="utf-8") as fh:
        candidates = json.load(fh)

    payload = asyncio.run(run(candidates, args.limit))
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    print("winners_exact:", payload["winners_exact_match"])
    print("winners_target:", payload["winners_target_triple"])
    for r in payload["results"]:
        if r.get("fetch_issue"):
            print(f"  FETCH-ISSUE {r['status']} {r['url']}")
        else:
            print(
                f"  {r['status']} canon={r['canonical_triples']:3d} target={r['target_triples']} "
                f"exact={r['exact_canonical_match']} txt={r['text_length']:6d} {r['url']}"
            )
    print(f"[salvo em] {args.out}")


if __name__ == "__main__":
    main()
