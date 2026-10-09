"""Validação fact-level do worker piloto DEFENDEU (#048.10M.1.2) — READ-ONLY.

Conecta no Neo4j vivo (credenciais via .env) apenas com queries MATCH/RETURN
(nenhuma escrita). Para cada expected fact do registry, verifica:
existência de :Fato com predicado DEFENDEU e sujeito/objeto canônicos
(considerando aliases, fold de acentos e case), status `verificado`,
`confirmacoes` e domínios distintos via `:FonteWeb`-[:CONFIRMA]->.

Saída: reports/defendeu_pilot_worker_fact_validation_048_10m_1_2.json
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

EXPECTED_PATH = (Path(__file__).resolve().parents[1] / "reports" / "defendeu_pilot_expected_facts_048_10m_1.json")
OUT_PATH = (Path(__file__).resolve().parents[1] / "reports" / "defendeu_pilot_worker_fact_validation_048_10m_1_2.json")
WIKIMEDIA = {"pt.wikipedia.org", "en.wikipedia.org"}


def canon(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.upper().split())


def variants(entry: dict, field: str) -> list[str]:
    out = {canon(entry.get(field, ""))}
    for alias in entry.get(f"{field}_aliases", []) or []:
        out.add(canon(alias))
    return sorted(v for v in out if v)


async def main() -> int:
    from neo4j import AsyncGraphDatabase

    expected = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))["expected_facts"]
    driver = AsyncGraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ.get("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"]),
    )
    results: list[dict] = []
    try:
        async with driver.session() as session:
            for fact in expected:
                subjects = variants(fact, "subject")
                objects = variants(fact, "object")
                # #056.5 — match accent-tolerant: o grafo tem nós acentuados
                # (SÓCRATES) e desacentuados (SOCRATES); `IN` exato falhava.
                # Traz os DEFENDEU do sujeito (todos os candidatos) e filtra no Python.
                query = (
                    "MATCH (f:Fato {predicado: 'DEFENDEU'}) "
                    "OPTIONAL MATCH (w:FonteWeb)-[:CONFIRMA]->(f) "
                    "RETURN f.sujeito AS sujeito, f.objeto AS objeto, "
                    "f.verificado AS verificado, f.confirmacoes AS confirmacoes, "
                    "collect(DISTINCT w.domain) AS domains"
                )
                records = await session.run(query)
                raw_rows = [rec.data() async for rec in records]
                subjects_set, objects_set = set(subjects), set(objects)
                rows = [
                    r for r in raw_rows
                    if canon(r["sujeito"]) in subjects_set and canon(r["objeto"]) in objects_set
                ]
                verified_rows = [r for r in rows if r["verificado"] is True]
                best_domains: set[str] = set()
                for row in verified_rows or rows:
                    best_domains.update(d for d in (row["domains"] or []) if d)
                non_wikimedia = sorted(d for d in best_domains if d not in WIKIMEDIA)
                results.append({
                    "candidate_id": fact["candidate_id"],
                    "expected": fact["fact"],
                    "present_in_graph": bool(rows),
                    "verified_in_graph": bool(verified_rows),
                    "confirmed_domains": sorted(best_domains),
                    "domain_count": len(best_domains),
                    "non_wikimedia_domain_present": bool(non_wikimedia),
                    "meets_quorum": len(best_domains) >= 3,
                    "rows": [
                        {
                            "sujeito": r["sujeito"], "objeto": r["objeto"],
                            "verificado": r["verificado"], "confirmacoes": r["confirmacoes"],
                            "domains": r["domains"],
                        }
                        for r in rows
                    ],
                })
    finally:
        await driver.close()

    verified_expected = sum(1 for r in results if r["verified_in_graph"])
    missing = [r["candidate_id"] for r in results if not r["present_in_graph"]]
    partial = [
        r["candidate_id"] for r in results
        if r["present_in_graph"] and not r["verified_in_graph"]
    ]
    report = {
        "audit_id": "defendeu_pilot_worker_fact_validation_048_10m_1_2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "read_only",
        "expected_facts_total": len(results),
        "verified_expected_facts": verified_expected,
        "missing_expected_facts": missing,
        "partial_expected_facts": partial,
        "candidates": results,
    }
    OUT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    for r in results:
        print(json.dumps({
            "candidate_id": r["candidate_id"],
            "present": r["present_in_graph"],
            "verified": r["verified_in_graph"],
            "domains": r["domain_count"],
            "non_wikimedia": r["non_wikimedia_domain_present"],
        }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
