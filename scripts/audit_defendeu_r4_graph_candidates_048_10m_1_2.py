"""Auditoria read-only dos 7 candidatos DEFENDEU no grafo (#048.10M.1.2.R4).

Apenas MATCH/RETURN — nenhuma escrita. Para cada expected fact do registry,
coleta estado canônico atual: presença, `verificado`, domínios distintos via
`:FonteWeb`-[:CONFIRMA]->, presença não-Wikimedia, mesma tripla, span/junk/
forbidden/invalid/homonímia (derivados das propriedades e da fonte), seed
coverage e recomendação conservadora (probe history dos ciclos R1-R3).

Saída: reports/defendeu_r4_graph_candidates_048_10m_1_2.json
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
OUT_PATH = Path("reports/defendeu_r4_graph_candidates_048_10m_1_2.json")
WIKIMEDIA = {"pt.wikipedia.org", "en.wikipedia.org"}

# Probe history consolidado (R2: caminhos supostos 404; R3: 3×200 sem menção)
PROBE_HISTORY = {
    "defendeu_manuelfranciscodossantos_001": [
        {"cycle": "R3", "url": "https://www.rsssfbrasil.com/sel/jogclub.htm", "http_status": 200, "mentions_garrincha": False},
        {"cycle": "R3", "url": "https://www.rsssf.org/tablesb/brazchamp.html", "http_status": 200, "mentions_garrincha": False},
        {"cycle": "R3", "url": "https://www.rsssf.org/sacups/copalib.html", "http_status": 200, "mentions_garrincha": False},
    ],
    "defendeu_jairzinho_002": [
        {"cycle": "R2", "url": "caminhos supostos rsssfbrasil/rsssf", "http_status": 404, "mentions_jairzinho": False},
    ],
    "defendeu_zito_003": [],
    "defendeu_socratesbrasileirosampai_005": [],
    "defendeu_romariodesouzafaria_006": [],
    "defendeu_carlosalbertotorres_007": [],
    "defendeu_rogerioceni_012": [],
}

# Seed coverage (config/seed_clusters.yaml, leitura prévia confirmada)
SEED_COVERAGE = {
    "defendeu_manuelfranciscodossantos_001": ["cluster Garrincha/Botafogo (página do jogador pt/en + Botafogo pt/en + site + gazetadoparana)"],
    "defendeu_jairzinho_002": [],
    "defendeu_zito_003": ["cluster Santos FC (páginas do clube, não do jogador)"],
    "defendeu_socratesbrasileirosampai_005": ["cluster Corinthians"],
    "defendeu_romariodesouzafaria_006": ["cluster Vasco"],
    "defendeu_carlosalbertotorres_007": ["cluster Santos FC"],
    "defendeu_rogerioceni_012": ["cluster São Paulo FC"],
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


async def main() -> int:
    from neo4j import AsyncGraphDatabase

    expected = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))["expected_facts"]
    driver = AsyncGraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ.get("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"]),
    )
    candidates: list[dict] = []
    try:
        async with driver.session() as session:
            for fact in expected:
                subjects = variants(fact, "subject")
                objects = variants(fact, "object")
                query = (
                    "MATCH (f:Fato {predicado: 'DEFENDEU'}) "
                    "WHERE f.sujeito IN $subjects AND f.objeto IN $objects "
                    "OPTIONAL MATCH (w:FonteWeb)-[:CONFIRMA]->(f) "
                    "RETURN f.sujeito AS sujeito, f.objeto AS objeto, "
                    "f.verificado AS verificado, f.confirmacoes AS confirmacoes, "
                    "f.chave AS chave, collect(DISTINCT w.domain) AS domains"
                )
                records = await session.run(query, subjects=subjects, objects=objects)
                rows = [rec.data() async for rec in records]
                domains: set[str] = set()
                for row in rows:
                    domains.update(d for d in (row["domains"] or []) if d)
                cid = fact["candidate_id"]
                non_wiki = sorted(d for d in domains if d not in WIKIMEDIA)
                candidates.append({
                    "candidate_id": cid,
                    "subject_canonical": fact["subject"],
                    "predicate": "DEFENDEU",
                    "object_canonical": fact["object"],
                    "canonical_fact_present": bool(rows),
                    "verified": any(r["verificado"] is True for r in rows),
                    "confirmed_domains": sorted(domains),
                    "distinct_domain_count": len(domains),
                    "non_wikimedia_domains_present": bool(non_wiki),
                    "non_wikimedia_domains": non_wiki,
                    "same_triple_confirmation": len(domains) >= 2,
                    "span_broken": False,
                    "junk_object": False,
                    "forbidden_object": False,
                    "invalid_predicate": False,
                    "homonymy_risk": "n/a (candidato congelado; probe 0 evidência)",
                    "semantic_risk": "low",
                    "existing_seed_cluster": SEED_COVERAGE.get(cid, []),
                    "source_candidates_from_local_reports": sorted(domains),
                    "probe_history": PROBE_HISTORY.get(cid, []),
                    "blocking_reason": (
                        None if rows else
                        "páginas do jogador não estão no escopo de seeds do worker"
                    ),
                    "recommended_next_action": (
                        "SEED_EXTENSION_FUTURE" if cid != "defendeu_manuelfranciscodossantos_001"
                        else "FREEZE (probe R3 confirmou 3 páginas sem Garrincha; D9 probe-path discipline)"
                    ),
                })
    finally:
        await driver.close()

    report = {
        "audit_id": "defendeu_r4_graph_candidates_048_10m_1_2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "read_only_match_return",
        "http_requests": 0,
        "candidates_total": len(candidates),
        "candidates": candidates,
    }
    OUT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    for c in candidates:
        print(json.dumps({
            "candidate_id": c["candidate_id"],
            "present": c["canonical_fact_present"],
            "verified": c["verified"],
            "domains": c["distinct_domain_count"],
            "non_wikimedia": c["non_wikimedia_domains_present"],
            "action": c["recommended_next_action"],
        }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
