"""Captura pos-re-ingest pos-#048.4 (read-only)."""
from __future__ import annotations

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


async def main() -> None:

    import httpx
    from neo4j import AsyncGraphDatabase

    out_path = Path(
        sys.argv[1] if len(sys.argv) > 1 else "reports/post_reingest_048_4.json"
    )
    worker_run_id = sys.argv[2] if len(sys.argv) > 2 else ""

    driver = AsyncGraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ.get("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"]),
    )
    graph: dict = {}
    try:
        async with driver.session() as session:
            labels = [
                r
                async for r in await session.run(
                    "MATCH (n) WITH labels(n)[0] AS label, count(*) AS c "
                    "RETURN label, c ORDER BY c DESC"
                )
            ]
            graph["label_counts"] = {r["label"]: r["c"] for r in labels}

            rec = await (
                await session.run(
                    """
                    MATCH (f:Fato)
                    OPTIONAL MATCH (fw:FonteWeb)-[:CONFIRMA]->(f)
                    WITH f, count(DISTINCT fw.domain) AS doms, count(fw) AS confs
                    RETURN count(f) AS facts,
                           sum(CASE WHEN confs >= 2 THEN 1 ELSE 0 END) AS facts_with_two_or_more_confirmations,
                           sum(CASE WHEN doms >= 2 THEN 1 ELSE 0 END) AS facts_with_two_or_more_domains,
                           sum(CASE WHEN doms >= 3 THEN 1 ELSE 0 END) AS facts_with_three_or_more_domains,
                           coalesce(max(confs), 0) AS max_domain_confirmations,
                           sum(CASE WHEN confs >= 3 AND doms >= 2 THEN 1 ELSE 0 END) AS verified_facts_domain_independent
                    """
                )
            ).single()
            graph.update({k: rec[k] for k in rec.keys()})

            rec2 = await (
                await session.run(
                    """
                    MATCH (f:Fato)
                    OPTIONAL MATCH (fw:FonteWeb)-[:CONFIRMA]->(f)
                    WITH f, collect(DISTINCT fw.domain) AS domains, collect(fw.url) AS urls
                    WHERE size([d IN domains WHERE d IS NOT NULL]) >= 2
                    RETURN count(*) AS duplicate_cross_domain
                    """
                )
            ).single()
            graph["duplicate_cross_domain"] = rec2["duplicate_cross_domain"] or 0

            # conceptual entity naming before/after aliases (sample)
            rec3 = await (
                await session.run(
                    """
                    MATCH (c:Conceito)
                    WHERE c.nome IN ['SANTOS FC', 'SANTOS FUTEBOL CLUBE', 'PELE',
                                     'EDSON ARANTES DO NASCIMENTO',
                                     'ESTADIO URBANO CALDEIRA', 'ESTÁDIO URBANO CALDEIRA']
                    RETURN c.nome AS nome, count(*) AS c
                    ORDER BY c.nome
                    """
                )
            ).data()
            graph["alias_entity_counts"] = rec3
    finally:
        await driver.close()

    space_url = (
        os.environ.get("NEXUS_SPACE_URL") or os.environ.get("HF_SPACE_URL") or ""
    ).rstrip("/")
    space_metrics: dict = {}
    space_health: dict = {}
    if space_url:
        headers = {}
        hf = os.environ.get("HF_TOKEN", "")
        if hf:
            headers["Authorization"] = f"Bearer {hf}"
        nexus = os.environ.get("NEXUS_API_TOKEN", "")
        if nexus:
            headers["X-Nexus-Token"] = nexus
        try:
            async with httpx.AsyncClient() as client:
                hr = await client.get(f"{space_url}/health", headers=headers, timeout=30.0)
                space_health = {
                    "status_code": hr.status_code,
                    "body": hr.json()
                    if hr.headers.get("content-type", "").startswith("application/json")
                    else hr.text[:200],
                }
                mr = await client.get(f"{space_url}/api/metrics", headers=headers, timeout=30.0)
                if mr.status_code == 200:
                    space_metrics = mr.json()
                else:
                    space_metrics = {"error": mr.status_code, "text": mr.text[:300]}
        except Exception as exc:
            space_health = {"error": str(exc)}

    eq = space_metrics.get("extraction_quality", {}) if isinstance(space_metrics, dict) else {}
    reasons = eq.get("rejection_reasons", {}) or {}
    ver = space_metrics.get("verification", {}) if isinstance(space_metrics, dict) else {}
    acct = (
        space_metrics.get("ingestion_accounting", {})
        if isinstance(space_metrics, dict)
        else {}
    )

    report = {
        "report": out_path.stem,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "build_space_commit": "732ff3e (git 0b5bc32)",
        "worker_run_id": worker_run_id,
        "quorum": int(os.environ.get("NEXUS_VERIFY_QUORUM", "3")),
        "workflow_after": "disabled_manually",
        "space_health": space_health,
        "graph": graph,
        "space_metrics_present": bool(space_metrics and "error" not in (space_metrics or {})),
        "extraction_quality": {
            "raw_triples": eq.get("raw_triples"),
            "canonical_triples": eq.get("canonical_triples"),
            "rejected_noise": eq.get("rejected_noise"),
            "rejection_reasons": reasons,
            "top_unmapped_predicates": eq.get("top_unmapped_predicates"),
            "top_invalid_predicates": eq.get("top_invalid_predicates"),
        },
        "verification": ver,
        "ingestion_accounting": acct,
        "vectors_count": (space_metrics or {}).get("vectors"),
        "truthfulness_note": "Read-only post-reingest; no Neo4j writes from this script.",
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\n[salvo em] {out_path}")


if __name__ == "__main__":
    asyncio = __import__("asyncio")
    asyncio.run(main())
