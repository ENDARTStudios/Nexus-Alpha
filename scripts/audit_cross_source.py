"""Nexus-Alpha — CLI read-only: auditoria de near-match cross-source (#046).

Lê apenas estado existente do Neo4j (``:Fato`` + ``:FonteWeb``/``:CONFIRMA``),
roda :func:`src.cognition.cross_source_audit.audit` e grava um JSON local
(não público). Não escreve no grafo, não toca Qdrant, não promove fato.
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

from dotenv import load_dotenv  # noqa: E402

from src.cognition.cross_source_audit import audit  # noqa: E402

FETCH_QUERY = """
MATCH (f:Fato)
OPTIONAL MATCH (ff:FonteWeb)-[:CONFIRMA]->(f)
WITH f, collect(DISTINCT coalesce(ff.domain, ff.url)) AS sources
RETURN coalesce(f.sujeito, f.subject) AS subject,
       coalesce(f.predicado, f.predicate) AS predicate,
       coalesce(f.objeto, f.object) AS object,
       coalesce(f.confirmacoes, 0) AS confirmacoes,
       coalesce(f.verificado, false) AS verificado,
       [s IN sources WHERE s IS NOT NULL] AS sources
"""


def _domain(source: str) -> str:
    source = (source or "").strip().lower()
    if "://" in source:
        return urlparse(source).netloc or source
    return source


async def fetch_facts() -> list[dict]:
    from neo4j import AsyncGraphDatabase

    driver = AsyncGraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ.get("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"]),
    )
    try:
        async with driver.session() as session:
            result = await session.run(FETCH_QUERY)
            facts = []
            async for record in result:
                facts.append({
                    "subject": record["subject"],
                    "predicate": record["predicate"],
                    "object": record["object"],
                    "confirmacoes": int(record["confirmacoes"] or 0),
                    "verificado": bool(record["verificado"]),
                    "domains": sorted({_domain(s) for s in record["sources"] if s}),
                })
            return facts
    finally:
        await driver.close()


def main() -> None:
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
    parser = argparse.ArgumentParser(description="Auditoria near-match cross-source (read-only).")
    parser.add_argument("--quorum", type=int, default=int(os.environ.get("NEXUS_VERIFY_QUORUM", 3)))
    parser.add_argument("--out", default=os.path.join(
        os.environ.get("TEMP", "."), f"cross_source_audit_{datetime.now(timezone.utc):%Y-%m-%d}.json"))
    args = parser.parse_args()

    facts = asyncio.run(fetch_facts())
    report = audit(facts, quorum=args.quorum)
    report["audit_id"] = f"cross_source_audit_{datetime.now(timezone.utc):%Y-%m-%d}"
    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    report["quorum"] = args.quorum
    report["truthfulness_note"] = (
        "Similaridade lexical read-only; NAO promove fato, NAO altera confirmacoes, "
        "NAO usa Qdrant/vetores stale. Sinonimos nao-lexicais nao sao detectados."
    )
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\n[salvo em] {args.out}")


if __name__ == "__main__":
    main()
