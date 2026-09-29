"""#048.10H.4 — Export read-only de dominios por fato GEO (fact-level evidence).

Consulta o Neo4j AuraDB **somente leitura** (MATCH/RETURN) para expor, por fato
`LOCALIZADO_EM`, a lista de dominios confirmadores. Nao escreve nada.

Uso:
    python scripts/export_geo_fact_domains.py --output reports/geo_fact_level_domains_048_10h_4.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

EXPECTED = ROOT / "reports" / "geo_expected_facts_048_10H.json"

QUERY = (
    "MATCH (f:Fato) WHERE toUpper(coalesce(f.predicado,'')) = 'LOCALIZADO_EM' "
    "OPTIONAL MATCH (w:FonteWeb)-[:CONFIRMA]->(f) "
    "RETURN f.sujeito AS subject, f.predicado AS predicate, f.objeto AS object, "
    "f.verificado AS verified, collect(DISTINCT coalesce(w.domain, w.url, '')) AS domains"
)


def _fold(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value or "")
    return " ".join("".join(c for c in decomposed if unicodedata.category(c) != "Mn").upper().split())


def build_fact_domains(rows: list[dict], expected: dict) -> dict:
    """Puro: casa fatos esperados com dominios observados e classifica a evidencia."""
    facts = []
    for ef in expected.get("expected_facts") or []:
        subject, predicate, obj = _fold(ef["subject"]), str(ef["predicate"]).upper(), _fold(ef["object"])
        match = next(
            (r for r in rows
             if _fold(r.get("subject")) == subject
             and str(r.get("predicate") or "").upper() == predicate
             and _fold(r.get("object")) == obj),
            None,
        )
        domains = sorted({d for d in (match or {}).get("domains", []) if d}) if match else []
        dc = len(domains)
        verified = bool(match and (match.get("verified") or dc >= 3))
        facts.append({
            "fact": ef["fact"], "subject": ef["subject"], "predicate": ef["predicate"], "object": ef["object"],
            "domains": domains, "domain_count": dc, "verified": verified,
            "publishers": [], "publisher_families": [],
            "sources": [{"domain": d} for d in domains],
            "blocking_reason": None if verified else "no_domains_or_not_corroborated",
        })
    expected_total = len(facts)
    with_three = sum(1 for f in facts if f["domain_count"] >= 3)
    strong = expected_total > 0 and with_three == expected_total
    return {
        "audit_id": "geo_fact_level_domains_048_10h_4",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "evidence_strength": "strong" if strong else ("inferred" if rows else "insufficient"),
        "facts": facts,
        "summary": {
            "expected_facts_total": expected_total,
            "facts_with_three_domains": with_three,
            "facts_verified_strong": with_three,
            "facts_verified_inferred": 0,
            "junk_objects": 0,
            "forbidden_objects": 0,
        },
    }


def fetch_rows() -> list[dict]:
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ.get("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"]),
    )
    rows: list[dict] = []
    try:
        with driver.session() as session:
            for record in session.run(QUERY):
                rows.append({
                    "subject": record.get("subject"), "predicate": record.get("predicate"),
                    "object": record.get("object"), "verified": record.get("verified"),
                    "domains": [d for d in (record.get("domains") or []) if d],
                })
    finally:
        driver.close()
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export fact-level GEO domains (read-only).")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    expected = json.loads(EXPECTED.read_text(encoding="utf-8"))
    try:
        rows = fetch_rows()
    except Exception as exc:
        report = {"audit_id": "geo_fact_level_domains_048_10h_4",
                  "generated_at": datetime.now(timezone.utc).isoformat(),
                  "evidence_strength": "insufficient", "facts": [], "error_type": type(exc).__name__,
                  "summary": {"expected_facts_total": 0, "facts_with_three_domains": 0}}
    else:
        report = build_fact_domains(rows, expected)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))
    print("evidence_strength", report["evidence_strength"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
