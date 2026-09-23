"""Nexus-Alpha — CLI read-only: entity linking audit (#057).

Lê apenas estado existente do Neo4j (``:Fato`` + ``:FonteWeb``/``:CONFIRMA``),
roda :func:`src.cognition.entity_linking_audit.build_report` e grava um JSON
local em ``reports/`` (gitignored). Não escreve no grafo, não toca Qdrant, não
chama ``/api/ingest``, não promove fato, não altera quórum.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv  # noqa: E402

from src.cognition.entity_linking_audit import (  # noqa: E402
    CREDENTIAL_MARKERS,
    assert_no_secret_markers,
    assert_read_only_cypher,
    build_report,
)

FETCH_QUERY = """
MATCH (f:Fato)
OPTIONAL MATCH (ff:FonteWeb)-[:CONFIRMA]->(f)
WITH f, collect(DISTINCT coalesce(ff.domain, ff.url)) AS sources
RETURN coalesce(f.sujeito, f.subject) AS subject,
       coalesce(f.predicado, f.predicate) AS predicate,
       coalesce(f.objeto, f.object) AS object,
       coalesce(f.fact_hash, f.chave) AS fact_hash,
       coalesce(f.confirmacoes, 0) AS confirmacoes,
       coalesce(f.verificado, false) AS verificado,
       [s IN sources WHERE s IS NOT NULL] AS sources
"""

_ENV_SECRET_NAMES = ("HF_TOKEN", "NEO4J_PASSWORD", "NEXUS_API_TOKEN", "QDRANT_API_KEY")


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
                    "fact_hash": record["fact_hash"],
                    "confirmacoes": int(record["confirmacoes"] or 0),
                    "verificado": bool(record["verificado"]),
                    "domains": sorted({_domain(s) for s in record["sources"] if s}),
                })
            return facts
    finally:
        await driver.close()


def _head_commit() -> str:
    try:
        done = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=10, check=False,
        )
        if done.returncode == 0 and done.stdout.strip():
            return done.stdout.strip()
    except Exception:
        return "unknown"
    return "unknown"


def _credential_leaks(text: str) -> list[str]:
    found = assert_no_secret_markers(text, CREDENTIAL_MARKERS)
    lowered = text.lower()
    for name in _ENV_SECRET_NAMES:
        value = os.environ.get(name)
        if value and value.lower() in lowered:
            found.append(name)
    return found


def main() -> None:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(root, ".env"))
    parser = argparse.ArgumentParser(description="Entity linking audit cross-domain (read-only).")
    parser.add_argument("--quorum", type=int, default=int(os.environ.get("NEXUS_VERIFY_QUORUM", 3)))
    parser.add_argument("--max-examples", type=int, default=20)
    parser.add_argument("--build-space-commit", default=None)
    parser.add_argument("--worker-run-id", default="unknown")
    parser.add_argument("--out", default=os.path.join(
        root, "reports", f"entity_linking_audit_{datetime.now(timezone.utc):%Y-%m-%d}.json"))
    args = parser.parse_args()

    assert_read_only_cypher(FETCH_QUERY)
    facts = asyncio.run(fetch_facts())
    report = build_report(
        facts,
        quorum=args.quorum,
        max_examples=args.max_examples,
        build_space_commit=args.build_space_commit or _head_commit(),
        worker_run_id=args.worker_run_id,
    )
    report["truthfulness_note"]["note"] = (
        "Read-only; NAO promove fato, NAO altera confirmacoes/quorum, NAO usa Qdrant. "
        "medium e limite superior teorico; apenas high alimenta revisao de alias curado."
    )

    text = json.dumps(report, ensure_ascii=False, indent=2)
    leaks = _credential_leaks(text)
    if leaks:
        raise SystemExit(f"[anti-leak] marcadores suspeitos no relatorio: {sorted(set(leaks))}")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(text)
    print(f"\n[salvo em] {args.out}")


if __name__ == "__main__":
    main()
