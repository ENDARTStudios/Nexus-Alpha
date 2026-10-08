"""#048.6 batch 2.0 — Auditoria read-only de duplicatas :Fato/SPO.

Responde: os 223 :Fato e ~201 chaves distintas indicam duplicação benigna
ou estão escondendo corroboração cross-domain?

Read-only: apenas leitura do Neo4j. Nada é gravado.
Anti-leak: nenhum segredo no relatório.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(_HERE))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")
load_dotenv(ROOT / ".env.local")



def _norm(value: str) -> str:
    return value.strip().upper()


async def main() -> None:
    from neo4j import AsyncGraphDatabase

    out_path = Path(
        sys.argv[1] if len(sys.argv) > 1 else "reports/fact_duplicate_audit_048_6_batch2.json"
    )

    driver = AsyncGraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ.get("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"]),
    )

    try:
        async with driver.session() as session:
            # 1) Todas as chaves SPO dos fatos + domínios confirmados
            query = """
            MATCH (f:Fato)
            OPTIONAL MATCH (fw:FonteWeb)-[:CONFIRMA]->(f)
            WITH f, collect(DISTINCT fw.domain) AS domains, collect(fw.url) AS urls, count(fw) AS confs
            RETURN f.sujeito AS s, f.predicado AS p, f.objeto AS o,
                   domains, urls, confs
            """
            facts = await (await session.run(query)).data()

            # 2) Agrupar por chave SPO normalizada
            from collections import defaultdict
            groups = defaultdict(list)
            for row in facts:
                s, p, o = _norm(row["s"]), _norm(row["p"]), _norm(row["o"])
                key = (s, p, o)
                groups[key].append({
                    "domains": row["domains"] or [],
                    "urls": row["urls"] or [],
                    "confs": row["confs"],
                })

            # 3) Classificar duplicatas
            duplicate_groups = []
            for key, facts_list in groups.items():
                if len(facts_list) <= 1:
                    continue

                all_domains = set()
                all_urls = []
                total_confs = 0
                for f in facts_list:
                    all_domains.update(d for d in f["domains"] if d)
                    all_urls.extend(f["urls"])
                    total_confs += f["confs"]

                domain_count = len([d for d in all_domains if d])
                is_cross_domain = domain_count >= 2

                # Classificação
                if is_cross_domain:
                    classification = "cross_domain_duplicate_hidden"
                else:
                    # mesma chave SPO, mesmo domínio -> benigno
                    classification = "same_domain_duplicate"

                duplicate_groups.append({
                    "subject": key[0],
                    "predicate": key[1],
                    "object": key[2],
                    "fact_count": len(facts_list),
                    "domains": sorted(all_domains),
                    "domain_count": domain_count,
                    "confirmation_count": total_confs,
                    "classification": classification,
                })

            # 4) Estatísticas globais
            total_facts = len(facts)
            # chaves SPO distintas (normalizadas)
            distinct_spo = len(groups)
            # gap graph-scoped (aprox: fatos totais - chaves SPO distinct)
            graph_scoped_gap = total_facts - distinct_spo

            cross_domain_dups = sum(1 for g in duplicate_groups if g["classification"] == "cross_domain_duplicate_hidden")
            same_domain_dups = sum(1 for g in duplicate_groups if g["classification"] == "same_domain_duplicate")
            hidden_potential_verified = sum(
                1 for g in duplicate_groups
                if g["classification"] == "cross_domain_duplicate_hidden"
                and g["domain_count"] >= 2
                and g["confirmation_count"] >= 3
            )

            # Top duplicatas (ordenar por fact_count desc)
            top_duplicates = sorted(duplicate_groups, key=lambda x: x["fact_count"], reverse=True)[:20]

            payload = {
                "audit_id": "fact_duplicate_audit_048_6_batch2",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "read_only": True,
                "build_space_commit": "503e6a3",
                "persisted_facts": total_facts,
                "graph_distinct_spo_keys": distinct_spo,
                "graph_scoped_gap": graph_scoped_gap,
                "duplicate_groups_total": len(duplicate_groups),
                "duplicate_groups_same_domain": same_domain_dups,
                "duplicate_groups_cross_domain": cross_domain_dups,
                "duplicate_groups_hidden_potential_verified": hidden_potential_verified,
                "top_duplicates": top_duplicates,
            }

            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            print(f"\n[salvo em] {out_path}")

    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(main())