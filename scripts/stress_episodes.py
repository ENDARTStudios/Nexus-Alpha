"""Nexus-Alpha — Teste de estresse leve da memória episódica durável.

Insere N episódios SINTÉTICOS e antigos (90 dias), mede inserção/leitura, checa
se o índice é usado (EXPLAIN) e valida a retenção — que remove justamente esses
nós (elegíveis por idade), sem tocar nos episódios reais do dia.

Uso: python scripts/stress_episodes.py [N]   (default 1000)
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.graph_connector import EPISODE_RECENT_QUERY, GraphConnector  # noqa: E402


MARKER = "stress.local"


def _load_env(path: str = ".env") -> None:
    """Carrega credenciais locais do .env (dev). Ignora silenciosamente se ausente."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if "=" in line and not line.strip().startswith("#"):
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def build_episodes(n: int, days_old: int = 90) -> list[dict]:
    base = datetime.now(timezone.utc) - timedelta(days=days_old)
    stamp = base.isoformat()
    day = base.strftime("%Y-%m-%d")
    return [
        {
            "id": f"stress_{i}",
            "fact_hash": f"stress-{i:08d}",
            "day": day,
            "created_at": stamp,
            "source_domain": MARKER,
            "subject": f"STRESS {i}",
            "predicate": "CONECTA_A",
            "object": "MEMORIA",
            "status": "novo",
        }
        for i in range(n)
    ]


async def _count_marker(connector: GraphConnector) -> int:
    async with connector.driver.session() as session:
        result = await session.run(
            "MATCH (e:Episodio {source_domain: $marker}) RETURN count(e) AS total",
            marker=MARKER,
        )
        record = await result.single()
        return int(record["total"]) if record else 0


async def main() -> None:
    _load_env()
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    connector = GraphConnector()
    await connector.connect()
    await connector.ensure_schema()

    t0 = time.perf_counter()
    inserted = await connector.persist_episodes(build_episodes(n))
    insert_s = time.perf_counter() - t0

    t1 = time.perf_counter()
    recent = await connector.recent_episodes(limit=20)
    read_s = time.perf_counter() - t1

    index_used = False
    operators: list[str] = []
    async with connector.driver.session() as session:
        explained = await session.run("EXPLAIN " + EPISODE_RECENT_QUERY, limit=20)
        summary = await explained.consume()
        plan = getattr(summary, "plan", None)

        def walk(node) -> None:
            if node is None:
                return
            if isinstance(node, dict):
                op = node.get("operatorType")
                children = node.get("children") or []
            else:
                op = getattr(node, "operator_type", None)
                children = getattr(node, "children", None) or []
            if op:
                operators.append(str(op))
            for child in children:
                walk(child)

        walk(plan)
        index_used = any("Index" in op for op in operators)

    before_prune = await _count_marker(connector)
    removed = await connector.prune_episodes(days=30, max_count=10000)
    after_prune = await _count_marker(connector)

    print(f"inseridos={inserted} em {insert_s:.3f}s ({n / insert_s:.0f} nos/s)")
    print(f"leitura(20)={len(recent)} itens em {read_s:.3f}s")
    print(f"indice usado no planner: {index_used}")
    print(f"plano (operadores): {', '.join(operators[:12])}")
    print(f"retencao: removidos={removed} | sinteticos antes={before_prune} depois={after_prune}")
    print("limpo" if after_prune == 0 else "ATENCAO: sobraram sinteticos")

    await connector.close()


if __name__ == "__main__":
    asyncio.run(main())
