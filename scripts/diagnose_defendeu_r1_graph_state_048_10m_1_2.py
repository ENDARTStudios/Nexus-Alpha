"""Diagnóstico read-only R1 (#048.10M.1.2.R1) — estado do grafo para os 7
candidatos DEFENDEU do piloto.

Somente MATCH/RETURN (nenhuma escrita). Para cada candidato:
1. fato exato (sujeito/objeto canônicos + aliases, fold de acento/case);
2. qualquer :Fato com o sujeito canônico (qualquer predicado) — mostra o que
   existe do jogador no grafo;
3. qualquer :Fato com o objeto canônico + predicado DEFENDEU (quem o clube
   diz defender/ter defendido) — mostra vizinhança do clube.

Saída: reports/defendeu_r1_graph_state_048_10m_1_2.json (sanitizado:
ids/sujeito/objeto/predicado/verificado/confirmacoes/domínios — sem segredos).
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

EXPECTED_PATH = Path("reports/defendeu_pilot_expected_facts_048_10m_1.json")
OUT_PATH = Path("reports/defendeu_r1_graph_state_048_10m_1_2.json")


def canon(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.upper().split())


def variants(entry: dict, field: str) -> list[str]:
    out = {canon(entry.get(field, ""))}
    for alias in entry.get(f"{field}_aliases", []) or []:
        out.add(canon(alias))
    return sorted(v for v in out if v)


def fact_row(record: dict) -> dict:
    return {
        "sujeito": record.get("sujeito"),
        "predicado": record.get("predicado"),
        "objeto": record.get("objeto"),
        "verificado": record.get("verificado"),
        "confirmacoes": record.get("confirmacoes"),
        "domains": record.get("domains", []),
    }


async def main() -> int:
    from neo4j import AsyncGraphDatabase

    expected = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))["expected_facts"]
    driver = AsyncGraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ.get("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"]),
    )
    report: dict = {
        "audit_id": "defendeu_r1_graph_state_048_10m_1_2",
        "mode": "read_only",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidates": [],
    }
    try:
        async with driver.session() as session:
            for fact in expected:
                subjects = variants(fact, "subject")
                objects = variants(fact, "object")
                cid = fact["candidate_id"]

                exact_q = (
                    "MATCH (f:Fato {predicado: 'DEFENDEU'}) "
                    "WHERE f.sujeito IN $subjects AND f.objeto IN $objects "
                    "OPTIONAL MATCH (w:FonteWeb)-[:CONFIRMA]->(f) "
                    "RETURN f.sujeito AS sujeito, f.objeto AS objeto, f.verificado AS verificado, "
                    "f.confirmacoes AS confirmacoes, collect(DISTINCT w.domain) AS domains"
                )
                exact = [fact_row(r) async for r in await session.run(exact_q, subjects=subjects, objects=objects)]

                any_pred_q = (
                    "MATCH (f:Fato) WHERE f.sujeito IN $subjects "
                    "OPTIONAL MATCH (w:FonteWeb)-[:CONFIRMA]->(f) "
                    "RETURN f.sujeito AS sujeito, f.predicado AS predicado, f.objeto AS objeto, "
                    "f.verificado AS verificado, f.confirmacoes AS confirmacoes, "
                    "collect(DISTINCT w.domain) AS domains LIMIT 25"
                )
                any_pred = [fact_row(r) async for r in await session.run(any_pred_q, subjects=subjects)]

                club_defendeu_q = (
                    "MATCH (f:Fato {predicado: 'DEFENDEU'}) WHERE f.objeto IN $objects "
                    "OPTIONAL MATCH (w:FonteWeb)-[:CONFIRMA]->(f) "
                    "RETURN f.sujeito AS sujeito, f.objeto AS objeto, f.verificado AS verificado, "
                    "f.confirmacoes AS confirmacoes, collect(DISTINCT w.domain) AS domains LIMIT 25"
                )
                club_def = [fact_row(r) async for r in await session.run(club_defendeu_q, objects=objects)]

                report["candidates"].append(
                    {
                        "candidate_id": cid,
                        "expected": fact["fact"],
                        "exact_match": exact,
                        "any_predicate_for_subject": any_pred,
                        "club_defendeu_neighbors": club_def,
                    }
                )
    finally:
        await driver.close()

    OUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"ok → {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
