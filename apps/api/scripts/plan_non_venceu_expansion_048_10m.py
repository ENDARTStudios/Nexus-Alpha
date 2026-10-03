"""#048.10M — Planejamento READ-ONLY de expansão não-VENCEU.

Inventaria os fatos verificados e constrói um atlas de candidatos DEFENDEU
(todos `candidate_unverified`). NÃO roda worker, NÃO ativa seeds, NÃO escreve
em Neo4j/Qdrant, NÃO chama /api/ingest, NÃO treina.

Uso:
    python scripts/plan_non_venceu_expansion_048_10m.py --inventory-only
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

OUT_INVENTORY = ROOT / "reports" / "expansion_fact_inventory_048_10m.json"
OUT_ATLAS = ROOT / "reports" / "expansion_defendeu_atlas_048_10m.json"
BASELINE_PATH = ROOT / "reports" / "expansion_metrics_baseline_048_10m.json"

VERIFIED_QUERY = (
    "MATCH (f:Fato) WHERE f.verificado = true "
    "OPTIONAL MATCH (w:FonteWeb)-[:CONFIRMA]->(f) "
    "RETURN f.sujeito AS subject, f.predicado AS predicate, f.objeto AS object, "
    "coalesce(f.confirmacoes,0) AS confirmacoes, "
    "collect(DISTINCT coalesce(w.domain,'')) AS domains"
)
UNVERIFIED_DEFENDEU_QUERY = (
    "MATCH (f:Fato) WHERE toUpper(coalesce(f.predicado,'')) = 'DEFENDEU' "
    "AND coalesce(f.verificado,false) = false "
    "RETURN f.sujeito AS subject, f.objeto AS object, coalesce(f.confirmacoes,0) AS confirmacoes"
)


def _fold(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value or "")
    return re.sub(r"[^A-Z0-9]", "", "".join(c for c in decomposed if unicodedata.category(c) != "Mn").upper())


# Candidatos DEFENDEU ancorados (pessoa→clube). Exploratory (requires_readonly_probe).
# NÃO afirmam fato: são alvos a serem provados por 3 domínios em lote futuro.
DEFENDEU_CANDIDATE_SEEDS = (
    {"subject": "MANUEL FRANCISCO DOS SANTOS", "subject_aliases": ["Garrincha"], "object": "BOTAFOGO DE FUTEBOL E REGATAS", "object_aliases": ["Botafogo"], "risk_level": "low", "risks": ["D1_PLAYER_NAME_AMBIGUITY", "D2_CLUB_NAME_AMBIGUITY"], "origin": "entidade existente no grafo (DEFENDEU unverified)"},
    {"subject": "JAIRZINHO", "subject_aliases": ["Jair Ventura Filho"], "object": "BOTAFOGO DE FUTEBOL E REGATAS", "object_aliases": ["Botafogo"], "risk_level": "low", "risks": ["D2_CLUB_NAME_AMBIGUITY"], "origin": "entidade existente no grafo (DEFENDEU unverified)"},
    {"subject": "ZITO", "subject_aliases": ["José Ely de Miranda"], "object": "SANTOS FUTEBOL CLUBE", "object_aliases": ["Santos"], "risk_level": "low", "risks": ["D1_PLAYER_NAME_AMBIGUITY", "D2_CLUB_NAME_AMBIGUITY"], "origin": "entidade existente no grafo (DEFENDEU unverified)"},
    {"subject": "ARTHUR ANTUNES COIMBRA", "subject_aliases": ["Zico"], "object": "CLUBE DE REGATAS DO FLAMENGO", "object_aliases": ["Flamengo"], "risk_level": "low", "risks": ["D2_CLUB_NAME_AMBIGUITY"], "origin": "exploratory_candidate (entidade histórica inequívoca)"},
    {"subject": "SÓCRATES BRASILEIRO SAMPAIO DE SOUZA VIEIRA DE OLIVEIRA", "subject_aliases": ["Sócrates"], "object": "SPORT CLUB CORINTHIANS PAULISTA", "object_aliases": ["Corinthians"], "risk_level": "low", "risks": ["D3_LOAN_VS_DEFENDED"], "origin": "exploratory_candidate (entidade histórica inequívoca)"},
    {"subject": "ROMÁRIO DE SOUZA FARIA", "subject_aliases": ["Romário"], "object": "CLUBE DE REGATAS VASCO DA GAMA", "object_aliases": ["Vasco"], "risk_level": "low", "risks": ["D2_CLUB_NAME_AMBIGUITY", "D3_LOAN_VS_DEFENDED"], "origin": "exploratory_candidate (entidade histórica inequívoca)"},
    {"subject": "CARLOS ALBERTO TORRES", "subject_aliases": ["Carlos Alberto"], "object": "SANTOS FUTEBOL CLUBE", "object_aliases": ["Santos"], "risk_level": "low", "risks": ["D1_PLAYER_NAME_AMBIGUITY", "D2_CLUB_NAME_AMBIGUITY"], "origin": "exploratory_candidate (entidade histórica inequívoca)"},
    {"subject": "NILTON REIS DOS SANTOS", "subject_aliases": ["Nílton Santos"], "object": "BOTAFOGO DE FUTEBOL E REGATAS", "object_aliases": ["Botafogo"], "risk_level": "medium", "risks": ["D1_PLAYER_NAME_AMBIGUITY", "D2_CLUB_NAME_AMBIGUITY"], "origin": "exploratory_candidate (nome conflita com estádio Nilton Santos)"},
    {"subject": "RONALDO LUÍS NAZÁRIO DE LIMA", "subject_aliases": ["Ronaldo"], "object": "CRUZEIRO ESPORTE CLUBE", "object_aliases": ["Cruzeiro"], "risk_level": "medium", "risks": ["D1_PLAYER_NAME_AMBIGUITY", "D3_LOAN_VS_DEFENDED"], "origin": "exploratory_candidate (nome comum; múltiplos clubes na carreira)"},
    {"subject": "DENÍLSON DE OLIVEIRA ARAÚJO", "subject_aliases": ["Denílson"], "object": "SÃO PAULO FUTEBOL CLUBE", "object_aliases": ["São Paulo"], "risk_level": "medium", "risks": ["D1_PLAYER_NAME_AMBIGUITY", "D3_LOAN_VS_DEFENDED"], "origin": "exploratory_candidate (múltiplos clubes na carreira)"},
    {"subject": "GUSTAVO NERY", "subject_aliases": ["Guga"], "object": "SANTOS FUTEBOL CLUBE", "object_aliases": ["Santos"], "risk_level": "medium", "risks": ["D2_CLUB_NAME_AMBIGUITY"], "origin": "exploratory_candidate"},
    {"subject": "ROGÉRIO CENI", "subject_aliases": [], "object": "SÃO PAULO FUTEBOL CLUBE", "object_aliases": ["São Paulo"], "risk_level": "medium", "risks": ["D3_LOAN_VS_DEFENDED"], "origin": "exploratory_candidate"},
)

REQUIRED_DOMAINS = ["pt.wikipedia.org", "en.wikipedia.org", "rsssf.org"]
PREFERRED_FAMILIES = ["Wikimedia", "RSSSF"]


def aggregate_verified(rows: list[dict]) -> dict:
    by_predicate: dict[str, int] = {}
    by_family: dict[str, int] = {}
    by_domain: dict[str, int] = {}
    for r in rows:
        pred = str(r.get("predicate") or "").upper()
        by_predicate[pred] = by_predicate.get(pred, 0) + 1
        for d in r.get("domains") or []:
            if d:
                by_domain[d] = by_domain.get(d, 0) + 1
    try:
        from src.ops.publisher_family import classify_publisher_family

        for d, c in by_domain.items():
            fam = classify_publisher_family(d)
            by_family[fam] = by_family.get(fam, 0) + c
    except Exception:
        pass
    total = len(rows)
    non_venceu = sum(c for p, c in by_predicate.items() if p != "VENCEU")
    return {
        "total_verified_facts": total,
        "facts_by_predicate": by_predicate,
        "facts_by_domain": by_domain,
        "facts_by_publisher_family": by_family,
        "venceu_facts": by_predicate.get("VENCEU", 0),
        "defendeu_facts": by_predicate.get("DEFENDEU", 0),
        "localizado_em_facts": by_predicate.get("LOCALIZADO_EM", 0),
        "non_venceu_facts": non_venceu,
        "non_VENCEU_ratio": round(non_venceu / total, 4) if total else 0.0,
        "top_predicate_share": round(max(by_predicate.values()) / total, 4) if total and by_predicate else 0.0,
    }


def build_defendeu_candidates(unverified_rows: list[dict], verified_keys: set[tuple[str, str]]) -> list[dict]:
    candidates = []
    seen: set[tuple[str, str]] = set()
    for i, seed in enumerate(DEFENDEU_CANDIDATE_SEEDS, start=1):
        key = (_fold(seed["subject"]), _fold(seed["object"]))
        already = key in verified_keys
        if key in seen:
            continue
        seen.add(key)
        candidates.append({
            "candidate_id": f"defendeu_{_fold(seed['subject']).lower()[:24]}_{i:03d}",
            "fact_template": "SUBJECT --DEFENDEU--> OBJECT",
            "subject": seed["subject"],
            "subject_aliases": seed["subject_aliases"],
            "predicate": "DEFENDEU",
            "object": seed["object"],
            "object_aliases": seed["object_aliases"],
            "required_domains": REQUIRED_DOMAINS,
            "preferred_publisher_families": PREFERRED_FAMILIES,
            "evidence_status": "candidate_unverified",
            "already_verified": already,
            "risk_level": seed["risk_level"],
            "risks": seed["risks"],
            "source_policy": "allowed",
            "requires_ontology_change": False,
            "requires_readonly_probe": True,
            "eligible_for_future_worker": False,
            "notes": seed["origin"],
        })
    return candidates


def _baseline() -> dict:
    defaults = {
        "verified_facts_domain_independent": 20, "fact_count": 412, "concept_count": 2023,
        "quorum": 3, "graph_scoped_gap": 0, "fact_accounting_status": "ok",
        "canonical_to_fact_gap_same_scope": 0, "publisher_family_count": 3,
    }
    try:
        data = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return defaults
    acc = data.get("ingestion_accounting") or {}
    ver = data.get("verification") or {}
    defaults.update({
        "verified_facts_domain_independent": ver.get("verified_facts_domain_independent", defaults["verified_facts_domain_independent"]),
        "fact_count": data.get("fact_count", defaults["fact_count"]),
        "concept_count": data.get("concept_count", defaults["concept_count"]),
        "quorum": ver.get("quorum", 3),
        "graph_scoped_gap": acc.get("graph_scoped_gap", 0),
        "fact_accounting_status": acc.get("fact_accounting_status", "ok"),
        "canonical_to_fact_gap_same_scope": acc.get("canonical_to_fact_gap_same_scope", 0),
        "publisher_family_count": data.get("publisher_family_count", 3),
    })
    return defaults


def _fetch(query: str) -> list[dict]:
    import os

    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(os.environ["NEO4J_URI"],
                                  auth=(os.environ.get("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"]))
    rows: list[dict] = []
    try:
        with driver.session() as session:
            for r in session.run(query):
                rows.append(dict(r))
    finally:
        driver.close()
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Planejamento read-only de expansão não-VENCEU.")
    parser.add_argument("--inventory-only", action="store_true")
    parser.parse_args(argv)

    baseline = _baseline()
    try:
        verified_rows = _fetch(VERIFIED_QUERY)
        unverified_defendeu = _fetch(UNVERIFIED_DEFENDEU_QUERY)
    except Exception:  # noqa: BLE001
        verified_rows, unverified_defendeu = [], []

    agg = aggregate_verified(verified_rows)
    verified_keys = {(_fold(r.get("subject")), _fold(r.get("object"))) for r in verified_rows if str(r.get("predicate") or "").upper() == "DEFENDEU"}
    candidates = build_defendeu_candidates(unverified_defendeu, verified_keys)

    inventory = {
        "audit_id": "expansion_fact_inventory_048_10m",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "read_only",
        "baseline": baseline,
        "facts_by_predicate": agg["facts_by_predicate"],
        "facts_by_publisher_family": agg["facts_by_publisher_family"],
        "facts_by_domain": agg["facts_by_domain"],
        "verified_facts": [
            {"subject": r.get("subject"), "predicate": r.get("predicate"), "object": r.get("object"),
             "domain_count": len([d for d in (r.get("domains") or []) if d]), "domains": [d for d in (r.get("domains") or []) if d]}
            for r in verified_rows
        ],
        "summary": {
            "records_total": agg["total_verified_facts"],
            "unique_predicates": len(agg["facts_by_predicate"]),
            "non_VENCEU_ratio": agg["non_VENCEU_ratio"],
            "top_predicate_share": agg["top_predicate_share"],
            "publisher_family_count": baseline.get("publisher_family_count", 3),
            "effective_publisher_count": baseline.get("publisher_family_count", 3),
        },
    }
    OUT_INVENTORY.write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8")

    low = sum(1 for c in candidates if c["risk_level"] == "low")
    med = sum(1 for c in candidates if c["risk_level"] == "medium")
    high = sum(1 for c in candidates if c["risk_level"] == "high")
    atlas = {
        "audit_id": "expansion_defendeu_atlas_048_10m",
        "generated_at": inventory["generated_at"],
        "mode": "read_only",
        "predicate": "DEFENDEU",
        "supported_now": True,
        "candidates": candidates,
        "summary": {
            "total_candidates": len(candidates),
            "low_risk": low, "medium_risk": med, "high_risk": high,
            "eligible_for_future_worker": 0,
            "recommended_first_batch_size": min(10, low + med),
        },
    }
    OUT_ATLAS.write_text(json.dumps(atlas, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({"inventory": inventory["summary"], "atlas": atlas["summary"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
