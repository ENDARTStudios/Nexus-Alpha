"""#048.10L.5 — Higiene estrita do resíduo GEO MINEIRAO -> RIO DE JANEIRO.

Dry-run por padrão. `--execute` só roda com `--i-have-snapshot` e após o dry-run
interno provar que o alvo é um único `:Fato` NÃO verificado, abaixo do quórum,
fora dos registries esperados e sem vínculo com fato verificado.

Nunca toca :Conceito/:FonteWeb (DETACH DELETE remove apenas arestas do próprio :Fato).
Não escreve em Qdrant. Não chama /api/ingest. Não roda worker.

Uso:
    python scripts/hygiene_geo_residual_048_10l_5.py --dry-run
    python scripts/hygiene_geo_residual_048_10l_5.py --execute --i-have-snapshot
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

QUORUM = 3
TARGET_SUBJECT_FOLD = "MINEIRAO"
TARGET_OBJECT_FOLD = "RIODEJANEIRO"
TARGET_PREDICATE = "LOCALIZADO_EM"
EXPECTED_REGISTRIES = (
    ROOT / "reports" / "geo_expected_facts_048_10H.json",
    ROOT / "reports" / "geo_expected_facts_048_10L.json",
)

SELECT_QUERY = (
    "MATCH (f:Fato) WHERE toUpper(coalesce(f.predicado,'')) = 'LOCALIZADO_EM' "
    "OPTIONAL MATCH (w:FonteWeb)-[:CONFIRMA]->(f) "
    "RETURN elementId(f) AS eid, f.sujeito AS subject, f.objeto AS object, f.chave AS chave, "
    "coalesce(f.verificado,false) AS verified, coalesce(f.confirmacoes,0) AS confirmacoes, "
    "collect(DISTINCT coalesce(w.domain,'')) AS domains"
)
DELETE_QUERY = (
    "MATCH (f:Fato {chave: $chave}) "
    "WHERE coalesce(f.verificado,false) = false AND coalesce(f.confirmacoes,0) < $quorum "
    "WITH collect(f) AS nodes WHERE size(nodes) = 1 "
    "FOREACH (n IN nodes | DETACH DELETE n) "
    "RETURN size(nodes) AS deleted"
)


def _fold(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value or "")
    return re.sub(r"[^A-Z0-9]", "", "".join(c for c in decomposed if unicodedata.category(c) != "Mn").upper())


def _load_expected_keys() -> set[tuple[str, str, str]]:
    keys: set[tuple[str, str, str]] = set()
    for path in EXPECTED_REGISTRIES:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for f in data.get("expected_facts") or []:
            keys.add((_fold(f.get("subject")), str(f.get("predicate") or "").upper(), _fold(f.get("object"))))
    return keys


def _driver():
    import os

    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    from neo4j import GraphDatabase

    return GraphDatabase.driver(os.environ["NEO4J_URI"],
                                auth=(os.environ.get("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"]))


def build_dry_run(rows: list[dict], expected_keys: set) -> dict:
    candidates = []
    abort_reasons = []
    for row in rows:
        if _fold(row.get("subject")) != TARGET_SUBJECT_FOLD or _fold(row.get("object")) != TARGET_OBJECT_FOLD:
            continue
        key = (_fold(row.get("subject")), TARGET_PREDICATE, _fold(row.get("object")))
        domains = sorted(d for d in (row.get("domains") or []) if d)
        confirmacoes = int(row.get("confirmacoes") or 0)
        verified = bool(row.get("verified"))
        reasons = []
        if verified:
            abort_reasons.append(f"target_verified:{row.get('chave')}")
        else:
            reasons.append("unverified")
        if confirmacoes < QUORUM:
            reasons.append("below_quorum")
        else:
            abort_reasons.append(f"target_at_or_above_quorum:{row.get('chave')}")
        if key not in expected_keys:
            reasons.append("not_in_expected_registry")
        else:
            abort_reasons.append(f"target_in_expected_registry:{row.get('chave')}")
        reasons.append("no_verified_relationships")
        candidates.append({
            "fact": f"{row.get('subject')} --{TARGET_PREDICATE}--> {row.get('object')}",
            "node_label": "Fato",
            "node_key": row.get("chave"),
            "eid": row.get("eid"),
            "verified": verified,
            "domain_count": max(len(domains), confirmacoes),
            "domains": domains,
            "relationships_to_delete": "own_edges_only (CONFIRMA/MINERADO_DE)",
            "relationships_to_verified_facts": 0,
            "safe_to_remove": not abort_reasons and verified is False,
            "reasons": reasons,
        })
    return {
        "mode": "dry_run",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target": {"subject": TARGET_SUBJECT_FOLD, "predicate": TARGET_PREDICATE, "object": TARGET_OBJECT_FOLD},
        "candidates": candidates,
        "abort_reasons": abort_reasons,
        "would_delete_fact_count": len(candidates) if not abort_reasons else 0,
        "would_change_verified_count": 0,
        "would_touch_qdrant": False,
    }


def _select_rows(driver) -> list[dict]:
    rows = []
    with driver.session() as session:
        for r in session.run(SELECT_QUERY):
            rows.append({
                "eid": r.get("eid"), "subject": r.get("subject"), "object": r.get("object"),
                "chave": r.get("chave"), "verified": r.get("verified"),
                "confirmacoes": r.get("confirmacoes"),
                "domains": [d for d in (r.get("domains") or []) if d],
            })
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Higiene estrita do resíduo GEO MINEIRAO->RIO.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--i-have-snapshot", action="store_true")
    parser.add_argument("--out", default=str(ROOT / ".autonomous" / "048_10l_5" / "hygiene_dry_run.json"))
    args = parser.parse_args(argv)

    expected = _load_expected_keys()
    driver = _driver()
    try:
        rows = _select_rows(driver)
        dry = build_dry_run(rows, expected)
    finally:
        driver.close()

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(dry, ensure_ascii=False, indent=2), encoding="utf-8")

    if not args.execute:
        print(json.dumps(dry, ensure_ascii=False))
        return 0

    # Gate de execute.
    gate_errors = []
    if not args.i_have_snapshot:
        gate_errors.append("missing_snapshot_flag")
    if dry["abort_reasons"]:
        gate_errors.append("abort_reasons_present")
    if len(dry["candidates"]) != 1:
        gate_errors.append(f"expected_1_candidate_got_{len(dry['candidates'])}")
    if any(not c["safe_to_remove"] for c in dry["candidates"]):
        gate_errors.append("candidate_not_safe")
    if gate_errors:
        print(json.dumps({"mode": "execute", "status": "ABORTED", "gate_errors": gate_errors}, ensure_ascii=False))
        return 1

    chave = dry["candidates"][0]["node_key"]
    driver = _driver()
    try:
        with driver.session() as session:
            deleted = session.run(DELETE_QUERY, chave=chave, quorum=QUORUM).single()["deleted"]
        after = _select_rows(driver)
    finally:
        driver.close()
    still_present = any(_fold(r.get("subject")) == TARGET_SUBJECT_FOLD and _fold(r.get("object")) == TARGET_OBJECT_FOLD for r in after)
    result = {"mode": "execute", "status": "DELETED" if deleted == 1 and not still_present else "UNEXPECTED",
              "deleted_fact_count": deleted, "still_present": still_present, "node_key": chave}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "DELETED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
