"""Nexus-Alpha — CLI read-only: auditoria de produtividade por URL (#058).

Para cada URL candidata: fetch (segue redirects) → limpeza de HTML → contagem de
sentenças → ``EntityExtractor`` → ``refine_triple_ex`` → classificação
``productive | weak | unproductive``.

**Não** grava em Neo4j, **não** grava em Qdrant, **não** chama ``/api/ingest``,
**não** promove fato. Única escrita: o JSON local em ``reports/``.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx  # noqa: E402

from src.cognition.entity_linking_audit import (  # noqa: E402
    CREDENTIAL_MARKERS,
    assert_no_secret_markers,
)
from src.miner.source_productivity import analyze_text, summarize  # noqa: E402
from src.miner.web_miner import WebMiner  # noqa: E402

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 Nexus-Alpha-Audit/1.0"
)

CANDIDATE_URLS: list[str] = [
    # santos_fc / estadio
    "https://pt.wikipedia.org/wiki/Santos_FC",
    "https://en.wikipedia.org/wiki/Santos_FC",
    "https://www.santosfc.com.br/institucional/historia",
    "https://www.santosfc.com.br/estadio",
    "https://ge.globo.com/futebol/times/santos/",
    "https://almanaquedosclubes.com/clubes/santos",
    "https://www.cbf.com.br/",
    "https://www.fifa.com/",
    "https://pt.wikipedia.org/wiki/Est%C3%A1dio_Urbano_Caldeira",
    "https://en.wikipedia.org/wiki/Est%C3%A1dio_Urbano_Caldeira",
    # pele
    "https://pt.wikipedia.org/wiki/Pel%C3%A9",
    "https://en.wikipedia.org/wiki/Pel%C3%A9",
    "https://almanaquedosclubes.com/jogadores/pele",
    # botafogo / garrincha
    "https://pt.wikipedia.org/wiki/Garrincha",
    "https://en.wikipedia.org/wiki/Garrincha",
    "https://pt.wikipedia.org/wiki/Botafogo_de_Futebol_e_Regatas",
    "https://en.wikipedia.org/wiki/Botafogo_F.C.",
    "https://www.botafogo.com.br/",
    "https://ge.globo.com/futebol/times/botafogo/",
    "https://almanaquedosclubes.com/clubes/botafogo",
    # alternativas institucionais / imprensa
    "https://www.lance.com.br/",
    "https://www.uol.com.br/esporte/",
]


async def fetch_one(client: httpx.AsyncClient, url: str) -> dict:
    try:
        response = await client.get(url, headers={"User-Agent": USER_AGENT}, timeout=25.0)
        return {
            "status": int(response.status_code),
            "final_url": str(response.url),
            "html": response.text if response.status_code == 200 else "",
            "error": "",
        }
    except Exception as exc:
        return {"status": 0, "final_url": url, "html": "", "error": type(exc).__name__}


def build_url_report(url: str, fetch_result: dict) -> dict:
    html = fetch_result.get("html") or ""
    if not html:
        report = analyze_text("", url=url, status=fetch_result.get("status", 0), content_length=0)
        report["final_url"] = fetch_result.get("final_url") or url
        report["error"] = fetch_result.get("error") or ""
        report["extractive_quality"] = "unproductive"
        report["notes"] = (
            f"fetch falhou ({report['error']})" if report["error"]
            else f"fetch falhou (status {report['status']})"
        )
        return report

    cleaned = WebMiner().clean_html(html, source_url=url)
    report = analyze_text(
        cleaned.get("content") or "",
        url=url,
        status=fetch_result.get("status", 200),
        content_length=len(html),
    )
    report["final_url"] = fetch_result.get("final_url") or url
    report["error"] = ""
    return report


async def audit_urls(urls: list[str]) -> list[dict]:
    limits = httpx.Limits(max_keepalive_connections=5, max_connections=8)
    async with httpx.AsyncClient(limits=limits, follow_redirects=True, verify=True) as client:
        results = await asyncio.gather(*[fetch_one(client, url) for url in urls])
    reports = [build_url_report(url, result) for url, result in zip(urls, results)]
    return sorted(reports, key=lambda r: (r.get("extractive_quality") != "productive", r.get("url") or ""))


def _default_out() -> str:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "reports", f"source_productivity_audit_{datetime.now(timezone.utc):%Y-%m-%d}.json")


def main() -> None:
    parser = argparse.ArgumentParser(description="Auditoria de produtividade de fontes (read-only).")
    parser.add_argument("--out", default=_default_out())
    parser.add_argument("--urls-file", default="")
    args = parser.parse_args()

    urls = list(CANDIDATE_URLS)
    if args.urls_file:
        with open(args.urls_file, "r", encoding="utf-8") as fh:
            urls = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

    reports = asyncio.run(audit_urls(urls))
    document = {
        "audit_id": f"source_productivity_audit_{datetime.now(timezone.utc):%Y-%m-%d}",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "quorum": int(os.environ.get("NEXUS_VERIFY_QUORUM", 3)),
        "read_only": True,
        "promote_automatically": False,
        "results": reports,
        "summary": summarize(reports),
        "truthfulness_note": {
            "read_only": True,
            "no_neo4j_no_qdrant_no_ingest": True,
            "does_not_change_quorum_or_confirmacoes": True,
            "classification_is_diagnostic_only": True,
        },
    }

    text = json.dumps(document, ensure_ascii=False, indent=2)
    leaks = assert_no_secret_markers(text, CREDENTIAL_MARKERS)
    if leaks:
        raise SystemExit(f"[anti-leak] marcadores suspeitos no relatorio: {sorted(set(leaks))}")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(text)
    print(f"\n[salvo em] {args.out}")


if __name__ == "__main__":
    main()
