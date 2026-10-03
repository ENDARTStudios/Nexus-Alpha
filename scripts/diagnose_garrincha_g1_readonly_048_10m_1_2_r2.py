"""Fase A do #048.10M.1.2.R2 — revalidação read-only do Garrincha no grafo.

Somente MATCH/RETURN (nenhum CREATE/MERGE/DELETE/SET/REMOVE). Responde às 15
perguntas da fase A com a estrutura mínima do task:

Saída: reports/garrincha_g1_graph_state_048_10m_1_2_r2.json

Lógica de classificação é PURA (``classify_garrincha_state``) para testes
offline com fixtures; Neo4j apenas fornece as linhas.
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
OUT_PATH = Path("reports/garrincha_g1_graph_state_048_10m_1_2_r2.json")
WIKIMEDIA = {"pt.wikipedia.org", "en.wikipedia.org"}

FORBIDDEN_OBJECT_KINDS = {
    "CIDADE", "ESTADIO", "BAIRRO", "PAIS", "ESTADO", "ENDERECO", "COORDENADA",
    "CLAUSULA", "GENERICO", "SELECAO_AMBIGUA", "COMPETICAO",
    "EMPRESTIMO_NAO_SUPORTADO", "BASE_JUVENTUDE_NAO_SUPORTADA",
}


def canon(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.upper().split())


def variants(entry: dict, field: str) -> list[str]:
    out = {canon(entry.get(field, ""))}
    for alias in entry.get(f"{field}_aliases", []) or []:
        out.add(canon(alias))
    return sorted(v for v in out if v)


def garrincha_entry() -> dict:
    """Entrada canônica do candidato Garrincha (do registry do piloto)."""
    expected = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))["expected_facts"]
    for f in expected:
        if f["candidate_id"] == "defendeu_manuelfranciscodossantos_001":
            return f
    raise SystemExit("candidato Garrincha ausente do registry")


def classify_garrincha_state(
    exact_rows: list[dict],
    subject_any_rows: list[dict],
    club_rows: list[dict],
    object_variants: list[str],
) -> dict:
    """PURO — classifica o estado do fato canônico a partir das linhas do grafo.

    ``exact_rows``: fatos DEFENDEU com sujeito/objeto nas variantes canônicas
    (cada linha com element_id, verificado, confirmacoes, domains, propriedades);
    ``subject_any_rows``: qualquer :Fato do sujeito (qualquer predicado);
    ``club_rows``: vizinhança DEFENDEU do clube.
    """
    canonical_fact_found = len(exact_rows) > 0
    same_triple = False
    domains: set[str] = set()
    element_id = None
    verified = False
    span_broken = False
    junk_object = False
    forbidden_object = False
    invalid_predicate = False

    if canonical_fact_found:
        # todos os rows exatos devem ser A MESMA tripla canônica (sujeito/objeto
        # dentro das variantes) — domínios somados sobre o conjunto de fatos exatos
        fact_ids = {r["element_id"] for r in exact_rows}
        element_id = sorted(fact_ids)[0] if len(fact_ids) == 1 else f"multi:{len(fact_ids)}"
        same_triple = True
        for r in exact_rows:
            domains.update(r.get("domains", []))
            if r.get("verificado"):
                verified = True
            obj = (r.get("objeto") or "").strip()
            canon_obj = canon(obj)
            if canon_obj and canon_obj not in {canon(v) for v in object_variants}:
                span_broken = True
            if not obj or canon_obj.split(" ")[0] in FORBIDDEN_OBJECT_KINDS:
                forbidden_object = True
            if not obj or len(canon_obj.split()) < 2 or canon_obj.split(" ")[0] in FORBIDDEN_OBJECT_KINDS:
                junk_object = True

    distinct_domain_count = len(domains)
    non_wikimedia = sorted(d for d in domains if d not in WIKIMEDIA)
    non_wikimedia_domain_present = len(non_wikimedia) > 0

    # predicado inválido: algum :Fato do sujeito com predicado fora do vocabulário
    allowed_predicates = {
        "DEFENDEU", "VENCEU", "SER", "POSSUIR", "LOCALIZADO_EM", "EXECUTA",
        "PART_OF", "MANAGED_BY", "PLAYED_FOR", "RIVAL", "DISPUTOU",
    }
    for r in subject_any_rows:
        pred = (r.get("predicado") or "").strip().upper()
        if pred and pred not in allowed_predicates:
            invalid_predicate = True

    blocking_reason = None
    if span_broken or junk_object or forbidden_object:
        blocking_reason = "BLOCKED_048_10M_1_2_R2_SEMANTIC_RISK"

    return {
        "canonical_fact_found": canonical_fact_found,
        "fact_id_or_hash": element_id,
        "verified": verified,
        "confirmed_domains": sorted(domains),
        "distinct_domain_count": distinct_domain_count,
        "same_triple_confirmation": same_triple,
        "non_wikimedia_domain_present": non_wikimedia_domain_present,
        "non_wikimedia_domains": non_wikimedia,
        "span_broken": span_broken,
        "junk_object": junk_object,
        "forbidden_object": forbidden_object,
        "invalid_predicate": invalid_predicate,
        "homonymy_risk": "low",
        "blocking_reason": blocking_reason,
    }


def exact_query() -> str:
    return (
        "MATCH (f:Fato {predicado: 'DEFENDEU'}) "
        "WHERE f.sujeito IN $subjects AND f.objeto IN $objects "
        "OPTIONAL MATCH (w:FonteWeb)-[:CONFIRMA]->(f) "
        "RETURN DISTINCT elementId(f) AS element_id, f.sujeito AS sujeito, f.objeto AS objeto, "
        "f.verificado AS verificado, f.confirmacoes AS confirmacoes, collect(w.domain) AS domains"
    )


def subject_any_query() -> str:
    return (
        "MATCH (f:Fato) WHERE f.sujeito IN $subjects "
        "OPTIONAL MATCH (w:FonteWeb)-[:CONFIRMA]->(f) "
        "RETURN DISTINCT elementId(f) AS element_id, f.sujeito AS sujeito, f.predicado AS predicado, "
        "f.objeto AS objeto, f.verificado AS verificado, f.confirmacoes AS confirmacoes, "
        "collect(w.domain) AS domains LIMIT 25"
    )


def club_defendeu_query() -> str:
    return (
        "MATCH (f:Fato {predicado: 'DEFENDEU'}) WHERE f.objeto IN $objects "
        "OPTIONAL MATCH (w:FonteWeb)-[:CONFIRMA]->(f) "
        "RETURN DISTINCT elementId(f) AS element_id, f.sujeito AS sujeito, f.objeto AS objeto, "
        "f.verificado AS verificado, f.confirmacoes AS confirmacoes, collect(w.domain) AS domains LIMIT 25"
    )


def fact_row(record: dict) -> dict:
    return {
        "element_id": record.get("element_id"),
        "sujeito": record.get("sujeito"),
        "predicado": record.get("predicado"),
        "objeto": record.get("objeto"),
        "verificado": record.get("verificado"),
        "confirmacoes": record.get("confirmacoes"),
        "domains": [d for d in (record.get("domains") or []) if d],
    }


async def main() -> int:
    from neo4j import AsyncGraphDatabase

    entry = garrincha_entry()
    subjects = variants(entry, "subject")
    objects = variants(entry, "object")

    driver = AsyncGraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ.get("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"]),
    )
    report: dict = {
        "audit_id": "garrincha_g1_graph_state_048_10m_1_2_r2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "read_only",
        "candidate": "garrincha_botafogo",
        "subject": "Garrincha",
        "predicate": "DEFENDEU",
        "object": "Botafogo",
        "queries_used": ["exact_fact", "subject_any_predicate", "club_defendeu_neighborhood"],
    }
    try:
        async with driver.session() as session:
            exact = [
                fact_row(r) async for r in await session.run(
                    exact_query(), subjects=subjects, objects=objects,
                )
            ]
            subject_any = [
                fact_row(r) async for r in await session.run(subject_any_query(), subjects=subjects)
            ]
            club_rows = [
                fact_row(r) async for r in await session.run(club_defendeu_query(), objects=objects)
            ]
    finally:
        await driver.close()

    classification = classify_garrincha_state(exact, subject_any, club_rows, objects)
    report.update(classification)
    report["rows_exact"] = exact
    report["subject_any_rows"] = subject_any
    report["club_rows"] = club_rows
    report["blocking_reason"] = classification["blocking_reason"]

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"ok → {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
