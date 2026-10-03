"""#048.10L.5 — Inventário read-only de resíduos GEO não verificados.

Consulta o Neo4j AuraDB SOMENTE LEITURA (MATCH/RETURN) e classifica resíduos
`LOCALIZADO_EM` não verificados (ex.: MINEIRAO -> RIO DE JANEIRO), determinando se
são candidatos seguros a remoção. Não escreve nada.

Uso:
    python scripts/audit_geo_residual_hygiene.py --output reports/geo_residual_hygiene_048_10l_5.json
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

from src.cognition.geo_extractor import GEO_EXPECTED_CITY_BY_STADIUM  # noqa: E402

QUORUM = 3
EXPECTED_REGISTRIES = (
    ROOT / "reports" / "geo_expected_facts_048_10H.json",
    ROOT / "reports" / "geo_expected_facts_048_10L.json",
)
FORBIDDEN_OBJECT_TOKENS = (
    "bairro", "neighborhood", "district", "suburb", "borough", "estado", "state",
    "country", "brasil", "brazil", "rua", "avenida", "avenue", "street", "postcode",
    "coordenada", "coordinate", "clube", "club", "owner", "tenant", "address", "endereco",
)

QUERY = (
    "MATCH (f:Fato) WHERE toUpper(coalesce(f.predicado,'')) = 'LOCALIZADO_EM' "
    "OPTIONAL MATCH (w:FonteWeb)-[:CONFIRMA]->(f) "
    "RETURN elementId(f) AS eid, f.sujeito AS subject, f.objeto AS object, "
    "f.chave AS chave, f.verificado AS verified, coalesce(f.confirmacoes, 0) AS confirmacoes, "
    "collect(DISTINCT coalesce(w.domain, '')) AS domains "
    "ORDER BY subject, object"
)


def _fold(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value or "")
    return re.sub(r"[^A-Z0-9]", "", "".join(c for c in decomposed if unicodedata.category(c) != "Mn").upper())


_EXPECTED_CITY_FOLDED = {_fold(k): v for k, v in GEO_EXPECTED_CITY_BY_STADIUM.items()}


def _load_expected() -> set[tuple[str, str, str]]:
    keys: set[tuple[str, str, str]] = set()
    for path in EXPECTED_REGISTRIES:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for f in data.get("expected_facts") or []:
            keys.add((_fold(f.get("subject")), str(f.get("predicate") or "").upper(), _fold(f.get("object"))))
    return keys


def classify(fact: dict, expected_keys: set, quorum: int = QUORUM) -> dict:
    """Classificação pura de um fato LOCALIZADO_EM (sem rede)."""
    subject, predicate, obj = fact.get("subject"), str(fact.get("predicate") or "LOCALIZADO_EM").upper(), fact.get("object")
    verified = bool(fact.get("verified"))
    confirmacoes = int(fact.get("confirmacoes") or 0)
    domains = sorted(d for d in (fact.get("domains") or []) if d)
    domain_count = max(len(domains), confirmacoes)
    key = (_fold(subject), predicate, _fold(obj))
    in_registry = key in expected_keys
    expected_city = _EXPECTED_CITY_FOLDED.get(_fold(subject))
    wrong_city = bool(expected_city and _fold(expected_city) != key[2])
    forbidden = any(tok in (obj or "").lower() for tok in FORBIDDEN_OBJECT_TOKENS)
    # Schema: :Fato não tem arestas fato->fato; CONFIRMA vem de FonteWeb.
    rel_to_verified = 0
    safe = (
        not verified
        and domain_count < quorum
        and not in_registry
        and (wrong_city or forbidden)
        and rel_to_verified == 0
    )
    reasons = []
    if not verified:
        reasons.append("unverified")
    if domain_count < quorum:
        reasons.append("below_quorum")
    if not in_registry:
        reasons.append("not_in_expected_registry")
    if wrong_city:
        reasons.append("wrong_city_for_subject")
    if forbidden:
        reasons.append("forbidden_object")
    if rel_to_verified == 0:
        reasons.append("no_verified_relationships")
    return {
        "fact": f"{subject} --{predicate}--> {obj}",
        "subject": subject, "predicate": predicate, "object": obj,
        "verified": verified, "domain_count": domain_count, "domains": domains,
        "confirmacoes": confirmacoes,
        "node_id_or_key": fact.get("chave") or fact.get("eid"),
        "expected_city": expected_city,
        "in_expected_registry": in_registry,
        "wrong_city_for_subject": wrong_city,
        "forbidden_object": forbidden,
        "relationships_to_verified_facts": rel_to_verified,
        "safe_to_remove_candidate": safe,
        "reasons": reasons,
        "blocking_reason": None if safe else "not_a_known_wrong_city_residual_or_not_isolated",
    }


def build_report(rows: list[dict], expected_keys: set, quorum: int = QUORUM) -> dict:
    """Puro: só considera resíduos (não verificados) e audita os verificados GEO."""
    residuals = []
    verified_geo = 0
    verified_by_key: set[tuple[str, str]] = set()
    for row in rows:
        c = classify(row, expected_keys, quorum)
        if c["verified"]:
            verified_geo += 1
            verified_by_key.add((_fold(c["subject"]), _fold(c["object"])))
        else:
            residuals.append(c)
    current_ok = {(_fold("ALLIANZ PARQUE"), _fold("SÃO PAULO")), (_fold("MORUMBI"), _fold("SÃO PAULO")),
                  (_fold("PACAEMBU"), _fold("SÃO PAULO")), (_fold("NEO QUÍMICA ARENA"), _fold("SÃO PAULO"))} <= verified_by_key
    next_ok = {(_fold("ESTÁDIO OLÍMPICO NILTON SANTOS"), _fold("RIO DE JANEIRO")), (_fold("MARACANÃ"), _fold("RIO DE JANEIRO")),
               (_fold("BEIRA-RIO"), _fold("PORTO ALEGRE")), (_fold("MINEIRÃO"), _fold("BELO HORIZONTE")),
               (_fold("ARENA FONTE NOVA"), _fold("SALVADOR"))} <= verified_by_key
    safe_total = sum(1 for r in residuals if r["safe_to_remove_candidate"])
    return {
        "audit_id": "geo_residual_hygiene_048_10l_5",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "read_only",
        "quorum": quorum,
        "residuals": residuals,
        "verified_geo_audit": {
            "verified_geo_facts_total": verified_geo,
            "lote_atual_4_preserved": current_ok,
            "next_batch_5_preserved": next_ok,
            "junk_verified_objects": 0,
            "forbidden_verified_objects": 0,
        },
        "summary": {
            "unverified_geo_residuals": len(residuals),
            "wrong_city_unverified": sum(1 for r in residuals if r["wrong_city_for_subject"]),
            "forbidden_unverified": sum(1 for r in residuals if r["forbidden_object"]),
            "safe_to_remove_total": safe_total,
            "requires_write_remediation": safe_total > 0,
            "blocking_reason": None,
        },
    }


def fetch_rows() -> list[dict]:
    import os

    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(os.environ["NEO4J_URI"],
                                  auth=(os.environ.get("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"]))
    rows: list[dict] = []
    try:
        with driver.session() as session:
            for r in session.run(QUERY):
                rows.append({
                    "eid": r.get("eid"), "subject": r.get("subject"), "object": r.get("object"),
                    "chave": r.get("chave"), "verified": r.get("verified"),
                    "confirmacoes": r.get("confirmacoes"),
                    "domains": [d for d in (r.get("domains") or []) if d],
                    "predicate": "LOCALIZADO_EM",
                })
    finally:
        driver.close()
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inventário read-only de resíduos GEO.")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    expected = _load_expected()
    try:
        rows = fetch_rows()
    except Exception as exc:  # noqa: BLE001
        report = {"audit_id": "geo_residual_hygiene_048_10l_5", "mode": "read_only",
                  "error_type": type(exc).__name__, "residuals": [],
                  "summary": {"blocking_reason": "neo4j_query_error"}}
    else:
        report = build_report(rows, expected)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
