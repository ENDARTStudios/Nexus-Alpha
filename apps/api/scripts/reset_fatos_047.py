"""Reset escopado: apaga apenas nós Fato (re-ingest pós-#047).

Uso: python scripts/reset_fatos_047.py --confirm
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    load_dotenv(Path(__file__).resolve().parent.parent / ".env.local")
except Exception:
    pass

if "--confirm" not in sys.argv:
    print("Uso: python scripts/reset_fatos_047.py --confirm")
    print("Apaga APENAS (f:Fato) + arestas. Preserva Conceito/RELACIONA/FonteWeb/Episodio.")
    raise SystemExit(2)


async def main() -> None:
    from neo4j import AsyncGraphDatabase

    driver = AsyncGraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ.get("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"]),
    )
    try:
        async with driver.session() as session:
            before = await (
                await session.run(
                    "MATCH (n) WITH labels(n)[0] AS label, count(*) AS c "
                    "RETURN label, c ORDER BY label"
                )
            ).data()
            print("before:", before)

            res = await session.run("MATCH (f:Fato) DETACH DELETE f")
            summary = await res.consume()
            print("deleted_nodes:", summary.counters.nodes_deleted)
            print("deleted_relationships:", summary.counters.relationships_deleted)

            after = await (
                await session.run(
                    "MATCH (n) WITH labels(n)[0] AS label, count(*) AS c "
                    "RETURN label, c ORDER BY label"
                )
            ).data()
            print("after:", after)

            labels_after = {r["label"] for r in after}
            for keep in ("Conceito", "FonteWeb", "Episodio"):
                print(f"preserved_{keep}:", keep in labels_after)
            print("fatos_remaining:", next((r["c"] for r in after if r["label"] == "Fato"), 0))
    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(main())
