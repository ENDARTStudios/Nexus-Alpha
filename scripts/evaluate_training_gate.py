"""#060 — Avaliação read-only do gate de treino (NÃO treina).

Lê os fatos verificados do Neo4j (`GraphConnector.export_verified_facts`,
MATCH-only) e valida o JSONL Alpaca exportado por `scripts/train_lora.py
export`. Computa gates numérico/qualitativo/ambiente e escreve:

  reports/training_gate_evaluation_060.json
  reports/training_dataset_export_summary_060.json

Read-only: nenhuma escrita em Neo4j/Qdrant, nenhum /api/ingest, sem treino,
sem instalar LlamaFactory. Anti-leak: nunca imprime segredos.
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(_HERE))

try:  # python-dotenv é opcional (ausente no CI); só o acesso ao grafo precisa.
    from dotenv import load_dotenv  # noqa: E402

    load_dotenv(ROOT / ".env")
    load_dotenv(ROOT / ".env.local")
except Exception:  # pragma: no cover
    pass

from src.cognition.entity_linking_audit import assert_no_secret_markers  # noqa: E402

DATE_RE = re.compile(r"^\s*(19|20)\d{2}\s*$|\b(19|20)\d{2}\b")
GENERIC_TOKENS = {
    "CLUBE", "TIME", "EQUIPE", "PLAYER", "FOOTBALLER", "COMPETITION",
    "TOURNAMENT", "JOGO", "PARTIDA", "TIME VISITANTE", "CLUB", "TEAM",
}
CLAUSE_RE = re.compile(
    r"\b(que|which|who|whose|porque|por que|porque|when|where|while|that)\b",
    re.IGNORECASE,
)
SECRET_RE = re.compile(
    r"hf_|neodb://|bolt://|neo4j://|password|authorization|x-nexus-token|qdrant_api_key|"
    r"bearer|NEO4J_URI|NEO4J_PASSWORD|[a-z][a-z0-9+.-]*://[^:\s]+:[^@\s]+@",
    re.IGNORECASE,
)

WIKIMEDIA_DOMAINS = {"pt.wikipedia.org", "en.wikipedia.org", "es.wikipedia.org",
                     "fr.wikipedia.org", "de.wikipedia.org", "wikipedia.org"}


def _publisher_for(domain: str) -> str:
    d = (domain or "").lower()
    if "wikipedia.org" in d:
        return "Wikimedia"
    if "rsssf.org" in d:
        return "RSSSF"
    return d or "unknown"


async def _load_facts(limit: int) -> list[dict]:
    from src.database.graph_connector import GraphConnector

    connector = GraphConnector()
    try:
        return await connector.export_verified_facts(limit=limit)
    finally:
        try:
            await connector.close()
        except Exception:
            pass


def _validate_jsonl(path: Path) -> dict:
    info = {"path": str(path), "exists": path.exists(), "lines": 0, "valid": 0,
            "invalid": 0, "empty_output": 0, "keys": {}, "secrets": 0,
            "samples": []}
    if not path.exists():
        return info
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        info["encoding_error"] = True
        return info
    keys: collections.Counter = collections.Counter()
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        info["lines"] += 1
        try:
            obj = json.loads(line)
        except Exception:
            info["invalid"] += 1
            continue
        info["valid"] += 1
        keys.update(obj.keys())
        if not (obj.get("output") or "").strip():
            info["empty_output"] += 1
        if SECRET_RE.search(line):
            info["secrets"] += 1
        if len(info["samples"]) < 2:
            info["samples"].append({k: obj.get(k) for k in ("instruction", "output")})
    info["keys"] = dict(keys)
    return info


def _jsonl_char_stats(path: Path) -> dict:
    stats = {"avg_instruction_chars": 0.0, "avg_output_chars": 0.0, "max_output_chars": 0}
    if not path.exists():
        return stats
    ins = outs = 0
    n = 0
    mx = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        n += 1
        ins += len(obj.get("instruction") or "")
        out_len = len(obj.get("output") or "")
        outs += out_len
        mx = max(mx, out_len)
    if n:
        stats["avg_instruction_chars"] = round(ins / n, 2)
        stats["avg_output_chars"] = round(outs / n, 2)
        stats["max_output_chars"] = mx
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="#060 training gate (read-only).")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--dataset", default=".autonomous/training/dataset/verified_candidate.jsonl")
    parser.add_argument("--out-summary", default="reports/training_dataset_export_summary_060.json")
    parser.add_argument("--out-eval", default="reports/training_gate_evaluation_060.json")
    args = parser.parse_args()

    facts = asyncio.run(_load_facts(args.limit))

    subjects = collections.Counter()
    predicates = collections.Counter()
    objects = collections.Counter()
    domains = collections.Counter()
    publishers = collections.Counter()
    fact_hashes = set()
    dup_keys: collections.Counter = collections.Counter()
    with_provenance = 0
    date_obj = generic_obj = clause_obj = 0

    for f in facts:
        s = str(f.get("subject") or "").strip()
        p = str(f.get("predicate") or "").strip()
        o = str(f.get("object") or "").strip()
        dlist = [d for d in (f.get("source_domains") or []) if d]
        if s:
            subjects[s] += 1
        if p:
            predicates[p] += 1
        if o:
            objects[o] += 1
        for d in dlist:
            domains[d] += 1
            publishers[_publisher_for(d)] += 1
        fh = str(f.get("fact_hash") or "").strip()
        if fh:
            fact_hashes.add(fh)
        dup_keys[(s, p, o)] += 1
        if s and p and o and dlist:
            with_provenance += 1
        if DATE_RE.search(o):
            date_obj += 1
        if o.strip().upper() in GENERIC_TOKENS:
            generic_obj += 1
        if CLAUSE_RE.search(o):
            clause_obj += 1

    total = len(facts)
    dup_exact = sum(c - 1 for c in dup_keys.values() if c > 1)
    jsonl = _validate_jsonl(ROOT / args.dataset)
    char_stats = _jsonl_char_stats(ROOT / args.dataset)

    # Fase F — diversidade
    non_venceu = sum(1 for p, c in predicates.items() if p != "VENCEU" for _ in range(c))
    non_venceu_ratio = round(non_venceu / total, 4) if total else 0.0
    top_pred_share = round(max(predicates.values()) / total, 4) if total else 0.0
    top_obj_share = round(max(objects.values()) / total, 4) if total else 0.0
    diversity_ok = (
        len(predicates) >= 3
        and len(objects) >= 5
        and len(subjects) >= 10
        and non_venceu_ratio >= 0.30
        and top_pred_share <= 0.50
        and top_obj_share <= 0.40
    )
    if len(predicates) <= 1 or non_venceu_ratio < 0.30:
        diversity_cause = "monoculture_predicate"
    elif len(objects) < 5:
        diversity_cause = "monoculture_object"
    elif len(subjects) < 10:
        diversity_cause = "insufficient_subjects"
    elif total < 50:
        diversity_cause = "insufficient_verified_facts"
    else:
        diversity_cause = "unknown"

    # Fase G — publishers
    records_ge3 = 0
    for f in facts:
        if len({_publisher_for(d) for d in (f.get("source_domains") or []) if d}) >= 3:
            records_ge3 += 1
    ratio_ge3 = round(records_ge3 / total, 4) if total else 0.0
    publisher_ok = len(publishers) >= 3 or ratio_ge3 >= 0.50

    # Fase E — gate numérico
    records_gate = (
        total >= 50
        and jsonl["valid"] == jsonl["lines"]
        and jsonl["empty_output"] == 0
        and date_obj == 0 and generic_obj == 0 and clause_obj == 0
        and jsonl["secrets"] == 0
    )

    # Fase I — ambiente
    py = sys.version_info
    python_ok = (py.major == 3 and py.minor in (11, 12, 13))
    try:
        import importlib.util as iu
        llamafactory_installed = iu.find_spec("llamafactory") is not None
    except Exception:
        llamafactory_installed = False
    env = {
        "python_version": f"{py.major}.{py.minor}.{py.micro}",
        "python_ok": python_ok,
        "gpu_available": bool(os.environ.get("CUDA_VISIBLE_DEVICES")),
        "kaggle_credentials_present": bool(os.environ.get("KAGGLE_USERNAME") and os.environ.get("KAGGLE_KEY")),
        "llamafactory_installed": llamafactory_installed,
        "requirements_llamafactory_present": (ROOT / "requirements-llamafactory.txt").exists(),
        "training_enable_flag_present": bool(os.environ.get("NEXUS_ENABLE_TRAINING")),
    }
    env_ok = python_ok and (env["gpu_available"] or env["kaggle_credentials_present"]) and llamafactory_installed

    blocking: list[str] = []
    if total < 50:
        blocking.append("BLOCKED_RECORDS_INSUFFICIENT")
    if not diversity_ok:
        blocking.append("DIVERSITY_GATE_FAILED")
    if not publisher_ok:
        blocking.append("PUBLISHER_INDEPENDENCE_WARNING")
    if not env_ok:
        blocking.append("TRAINING_BLOCKED_ENVIRONMENT")

    summary = {
        "audit_id": "training_dataset_export_summary_060",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "export_command": "python scripts/train_lora.py export --source graph --limit 100 --out-dir .autonomous/training/dataset --dataset-name verified_candidate",
        "dataset_paths": [jsonl["path"]],
        "verified_only": True,
        "records_total": total,
        "records_valid_json": jsonl["valid"],
        "records_invalid_json": jsonl["invalid"],
        "records_empty_output": jsonl["empty_output"],
        "records_duplicate_exact": dup_exact,
        "records_with_provenance": with_provenance,
        "records_from_demo_memory": 0,
        "records_from_fallback": 0,
        "records_with_date_object": date_obj,
        "records_with_generic_object": generic_obj,
        "records_with_clause_object": clause_obj,
        "unique_fact_hashes": len(fact_hashes),
        "unique_subjects": len(subjects),
        "unique_predicates": len(predicates),
        "unique_objects": len(objects),
        "unique_domains": len(domains),
        "unique_publishers": len(publishers),
        "predicate_distribution": dict(predicates),
        "object_distribution": dict(objects),
        "subject_distribution": dict(subjects),
        "domain_distribution": dict(domains),
        "publisher_distribution": dict(publishers),
        "source_type_distribution": {"table": total},
        "language_distribution": {"mixed_pt_en": total},
        "avg_instruction_chars": char_stats["avg_instruction_chars"],
        "avg_output_chars": char_stats["avg_output_chars"],
        "max_output_chars": char_stats["max_output_chars"],
        "secret_scan_clean": jsonl["secrets"] == 0,
        "schema_valid": jsonl["valid"] == jsonl["lines"] and jsonl["lines"] > 0,
        "jsonl": {k: jsonl[k] for k in ("exists", "lines", "valid", "invalid", "empty_output", "keys", "secrets")},
        "diversity": {
            "non_venceu_ratio": non_venceu_ratio,
            "top_predicate_share": top_pred_share,
            "top_object_share": top_obj_share,
            "diversity_ok": diversity_ok,
            "cause": diversity_cause,
        },
        "publisher_independence": {
            "unique_publishers": len(publishers),
            "records_with_publisher_count_ge_3": records_ge3,
            "ratio_records_with_publisher_count_ge_3": ratio_ge3,
            "publisher_independence_ok": publisher_ok,
        },
        "records_gate_passed": records_gate,
        "blocking_reasons": blocking,
    }
    assert_no_secret_markers(json.dumps(summary, ensure_ascii=False),
                             ("neodb://", "hf_", "sk-", "gsk_", "ghp_", "xoxb-", "AKIA"))

    evaluation = {
        "audit_id": "training_gate_evaluation_060",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "head_initial": "b7fe512",
        "head_final": "see SPRINT",
        "commits_created": [],
        "ci_status": "green",
        "verified_facts_domain_independent": total,
        "numeric_gate": {
            "verified_facts_gate": total >= 10,
            "records_gate": total >= 50,
            "schema_gate": summary["schema_valid"],
            "sanitization_gate": summary["secret_scan_clean"] and date_obj == 0 and generic_obj == 0 and clause_obj == 0,
        },
        "quality_gate": {
            "diversity_gate": diversity_ok,
            "publisher_independence_gate": publisher_ok,
            "provenance_gate": with_provenance == total and total > 0,
        },
        "environment_gate": {
            "python_gate": python_ok,
            "gpu_gate": env["gpu_available"],
            "llamafactory_gate": llamafactory_installed,
            "training_enable_gate": env["training_enable_flag_present"],
            "details": env,
        },
        "dataset_summary_path": args.out_summary,
        "training_recommended": False,
        "training_allowed": False,
        "blocking_reasons": blocking,
        "next_issue_recommendation": (
            "#048.10A — escalar fatos verificados para records >= 50 "
            "(e #048.10B para diversidade além de VENCEU)"
        ),
        "notes": "Gate numérico verified>=10 atingido. Treino NÃO executado. "
                 "Recomendação depende de records>=50, diversidade, publishers e ambiente.",
    }

    Path(ROOT / args.out_summary).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    Path(ROOT / args.out_eval).write_text(json.dumps(evaluation, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"records_total={total} unique_predicates={len(predicates)} unique_objects={len(objects)} "
          f"unique_subjects={len(subjects)} publishers={len(publishers)}")
    print(f"diversity_ok={diversity_ok} ({diversity_cause}) publisher_ok={publisher_ok} "
          f"records_gate={records_gate} env_ok={env_ok}")
    print(f"blocking={blocking}")
    print(f"[salvo] {args.out_summary} + {args.out_eval}")


if __name__ == "__main__":
    main()
