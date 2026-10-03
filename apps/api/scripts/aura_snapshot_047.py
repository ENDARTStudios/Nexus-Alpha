"""Snapshot real do AuraDB antes de reset (re-ingest pós-#047)."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    load_dotenv(Path(__file__).resolve().parent.parent / ".env.local")
except Exception:
    pass


def _serialize(props: dict) -> dict:
    out = {}
    for k, v in (props or {}).items():
        if hasattr(v, "iso_format"):
            out[k] = str(v)
        elif isinstance(v, (str, int, float, bool)) or v is None:
            out[k] = v
        else:
            out[k] = str(v)
    return out


async def main() -> None:
    from neo4j import AsyncGraphDatabase

    out_path = Path(
        sys.argv[1] if len(sys.argv) > 1 else "reports/aura_snapshot_pre_reingest_047.json"
    )

    driver = AsyncGraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ.get("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"]),
    )
    nodes: list[dict] = []
    rels: list[dict] = []
    try:
        async with driver.session() as session:
            q_nodes = (
                "MATCH (n) RETURN elementId(n) AS eid, labels(n) AS labels, "
                "properties(n) AS props"
            )
            async for rec in await session.run(q_nodes):
                nodes.append(
                    {
                        "eid": rec["eid"],
                        "labels": list(rec["labels"]),
                        "props": _serialize(rec["props"]),
                    }
                )
            q_rels = (
                "MATCH (a)-[r]->(b) "
                "RETURN elementId(a) AS src, elementId(b) AS dst, type(r) AS type, "
                "properties(r) AS props, elementId(r) AS eid"
            )
            async for rec in await session.run(q_rels):
                rels.append(
                    {
                        "eid": rec["eid"],
                        "src": rec["src"],
                        "dst": rec["dst"],
                        "type": rec["type"],
                        "props": _serialize(rec["props"]),
                    }
                )
            summary_q = (
                "MATCH (n) WITH labels(n)[0] AS label, count(*) AS c RETURN label, c"
            )
            labels = {
                r["label"]: r["c"]
                for r in [x async for x in await session.run(summary_q)]
            }
    finally:
        await driver.close()

    report = {
        "report": "aura_snapshot_pre_reingest_047",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "neo4j_uri_host": (os.environ.get("NEO4J_URI") or "").split("//")[-1].split(".")[0]
        + ".databases.neo4j.io",
        "node_count": len(nodes),
        "relationship_count": len(rels),
        "label_counts": labels,
        "nodes": nodes,
        "relationships": rels,
        "restore_hint": "Recreate nodes by eid order, then rels by src/dst eid. For DR only.",
        "truthfulness_note": "Full graph export before scoped Fato reset. Read-only.",
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"nodes={len(nodes)} rels={len(rels)} labels={labels}")
    print(f"[salvo em] {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
