"""Nexus-Alpha — Auditoria read-only pós-limpeza (#051).

Mede, sobre o estado atual (sem reset/deploy/mudança de runtime):
1. near-match cross-domain (audit lexical, sem Qdrant);
2. cobertura de domínios;
3. reconciliação raw → canonical → facts;
4. saúde de predicados (unmapped/modal/ambiguous).

Não promove fato, não altera `confirmacoes`, não escreve no grafo.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

from src.cognition.cross_source_audit import (  # noqa: E402
    audit,
    domain_coverage,
    reconcile_pipeline,
)

FETCH_QUERY = """
MATCH (f:Fato)
OPTIONAL MATCH (fw:FonteWeb)-[:CONFIRMA]->(f)
WITH f, collect(DISTINCT fw.url) AS urls, collect(DISTINCT fw.domain) AS domains
RETURN coalesce(f.sujeito, f.subject) AS subject,
       coalesce(f.predicado, f.predicate) AS predicate,
       coalesce(f.objeto, f.object) AS object,
       [u IN urls WHERE u IS NOT NULL] AS urls,
       [d IN domains WHERE d IS NOT NULL] AS domains
"""


def _domain(source: str) -> str:
    source = (source or "").strip().lower()
    host = urlparse(source).netloc if "://" in source else source
    return host[4:] if host.startswith("www.") else host


async def fetch_facts() -> list[dict]:
    from neo4j import AsyncGraphDatabase

    driver = AsyncGraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ.get("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"]),
    )
    try:
        async with driver.session() as session:
            facts = []
            async for record in await session.run(FETCH_QUERY):
                urls = list(record["urls"])
                domains = {d.strip().lower() for d in record["domains"] if d}
                if not domains:
                    domains = {_domain(u) for u in urls if u}
                facts.append({
                    "subject": record["subject"],
                    "predicate": record["predicate"],
                    "object": record["object"],
                    "urls": urls,
                    "domains": sorted(domains),
                })
            return facts
    finally:
        await driver.close()


def _predicate_health(metrics: dict) -> dict:
    eq = metrics.get("extraction_quality", {})
    reasons = eq.get("rejection_reasons", {}) or {}
    return {
        "unmapped_predicate_total": reasons.get("unmapped_predicate", 0),
        "modal_predicate_total": reasons.get("modal_predicate", 0),
        "ambiguous_predicate_total": reasons.get("ambiguous_predicate", 0),
        "top_unmapped_predicates": eq.get("top_unmapped_predicates", []),
        "top_modal_predicates": [],
        "top_ambiguous_predicates": [],
        "note": "top_modal/top_ambiguous não expostos pelo runtime (lacuna de observabilidade).",
    }


def main() -> None:
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env.local"))
    parser = argparse.ArgumentParser(description="Auditoria read-only pós-limpeza (#051).")
    parser.add_argument("--metrics-json", default=os.path.join(
        os.environ.get("TEMP", "."), "post_clean_metrics.json"))
    parser.add_argument("--commit", default="ac0857f")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--quorum", type=int, default=int(os.environ.get("NEXUS_VERIFY_QUORUM", 3)))
    parser.add_argument("--out", default=os.path.join(
        os.environ.get("TEMP", "."), f"post_clean_audit_{datetime.now(timezone.utc):%Y-%m-%d}.json"))
    args = parser.parse_args()

    facts = asyncio.run(fetch_facts())
    if os.path.exists(args.metrics_json):
        with open(args.metrics_json, encoding="utf-8") as fh:
            metrics = json.load(fh)
    else:
        base = os.environ.get("NEXUS_SPACE_URL", "").rstrip("/")
        headers = {"Authorization": f"Bearer {os.environ.get('HF_TOKEN','')}"}
        metrics = httpx.get(base + "/api/metrics", headers=headers, timeout=60.0).json()

    eq = metrics.get("extraction_quality", {})
    same_domain_multi_url = sum(1 for f in facts if len(f["urls"]) > len(f["domains"]))
    report = {
        "audit_id": f"post_clean_audit_{datetime.now(timezone.utc):%Y-%m-%d}",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "build_space_commit": args.commit,
        "worker_run_id": args.run_id,
        "quorum": args.quorum,
        "pipeline_reconciliation": reconcile_pipeline(
            raw_triples=eq.get("raw_triples", 0),
            canonical_triples=eq.get("canonical_triples", 0),
            rejected_noise=eq.get("rejected_noise", 0),
            persisted_facts=len(facts),
            same_domain_multi_url_merge=same_domain_multi_url,
        ),
        "domain_coverage": domain_coverage(facts),
        **audit(facts, quorum=args.quorum),
        "predicate_health": _predicate_health(metrics),
        "truthfulness_note": (
            "Read-only. Similaridade lexical; sem Qdrant. Nao promove fato, nao altera "
            "confirmacoes. Sinonimos nao-lexicais nao detectados."
        ),
    }
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\n[salvo em] {args.out}")


if __name__ == "__main__":
    main()
