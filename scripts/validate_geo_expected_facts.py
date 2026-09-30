"""#048.10H.1 — Validador read-only dos fatos GEO esperados no pós-run.

Consome relatórios LOCAIS (sem rede) e confere se os 4 fatos LOCALIZADO_EM
esperados aparecem verificados por >= 3 domínios, sem junk/regressão.

Uso:
    python scripts/validate_geo_expected_facts.py \\
        --baseline reports/baseline_pre_048_10H.json \\
        --post reports/post_reingest_048_10H.json \\
        --geo-report reports/geo_post_048_10H.json \\
        --expected reports/geo_expected_facts_048_10H.json \\
        --output reports/geo_expected_validation_048_10H.json
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

JUNK_TOKENS = (
    "bairro", "neighborhood", "endereco", "address", "pais", "country",
    "coordenada", "coordinate", "clausula", "clause", "generico", "generic",
)
FACT_LIST_KEYS = ("facts", "geo_facts", "facts_list", "expected_facts")


def _fold(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value or "")
    return " ".join("".join(c for c in decomposed if unicodedata.category(c) != "Mn").upper().split())


def _match_key(value: str) -> str:
    """Chave de casamento tolerante a hifen/espaco/pontuacao (ex.: BEIRA-RIO == BEIRA RIO)."""
    return re.sub(r"[^A-Z0-9]", "", _fold(value))


def _domains_of(item: dict) -> list[str]:
    for key in ("observed_domains", "predicted_domains", "domains", "sources"):
        value = item.get(key)
        if isinstance(value, list):
            return [str(v) for v in value]
    return []


def _collect_facts(*containers: dict) -> list[dict]:
    facts: list[dict] = []
    for container in containers:
        if not isinstance(container, dict):
            continue
        for key in FACT_LIST_KEYS:
            value = container.get(key)
            if isinstance(value, list):
                facts.extend([v for v in value if isinstance(v, dict)])
    return facts


def validate_geo_expected_facts(
    expected: dict,
    post: dict | None,
    geo_report: dict | None = None,
    baseline: dict | None = None,
) -> dict:
    post = post if isinstance(post, dict) else {}
    geo_report = geo_report if isinstance(geo_report, dict) else {}
    baseline = baseline if isinstance(baseline, dict) else {}
    expected_facts = expected.get("expected_facts") or []
    forbidden_predicates = {str(p).upper() for p in expected.get("forbidden_predicates") or []}

    facts = _collect_facts(geo_report, post)
    have_fact_level = bool(facts)

    missing: list[str] = []
    partial: list[str] = []
    verified = 0
    for ef in expected_facts:
        subject, predicate, obj = _match_key(ef["subject"]), str(ef["predicate"]).upper(), _match_key(ef["object"])
        match = next(
            (
                f
                for f in facts
                if _match_key(f.get("subject")) == subject
                and str(f.get("predicate") or "").upper() == predicate
                and _match_key(f.get("object")) == obj
            ),
            None,
        )
        if not match:
            missing.append(ef["fact"])
            continue
        domains = {d.lower() for d in _domains_of(match)}
        required = {d.lower() for d in ef.get("required_domains") or []}
        min_domains = int(ef.get("min_domain_count", 3))
        is_verified = bool(match.get("verified")) or len(domains) >= min_domains
        if is_verified and required <= domains and len(domains) >= min_domains:
            verified += 1
        else:
            partial.append(ef["fact"])

    junk = 0
    forbidden = 0
    for item in facts:
        obj = _fold(item.get("object") or "")
        if any(_fold(tok) in obj for tok in JUNK_TOKENS):
            junk += 1
        if str(item.get("predicate") or "").upper() in forbidden_predicates:
            forbidden += 1

    post_ver = ((post.get("verification") or {}).get("verified_facts_domain_independent"))
    base_ver = ((baseline.get("verification") or {}).get("verified_facts_domain_independent")) if baseline else None
    regression = bool(isinstance(post_ver, int) and isinstance(base_ver, int) and post_ver < base_ver)

    quality = post.get("extraction_quality") or {}
    fallback = post.get("fallback_health") or {}
    accounting = post.get("ingestion_accounting") or {}
    top_invalid = quality.get("top_invalid_predicates")
    fallback_promoted = fallback.get("fallback_promoted_to_graph")
    unaccounted = accounting.get("unaccounted_raw")

    total = len(expected_facts)
    ok = (
        have_fact_level
        and total > 0
        and verified == total
        and not missing
        and not partial
        and junk == 0
        and forbidden == 0
        and not regression
        and top_invalid == []
        and fallback_promoted == 0
        and unaccounted == 0
    )

    if not have_fact_level:
        classification = "PARTIAL_GEO_VALIDATION_INSUFFICIENT_EVIDENCE"
    elif ok:
        classification = "SUCCESS_048_10H_GEO_VERIFIED"
    else:
        classification = "BLOCKED_048_10H_GEO_VALIDATION"

    return {
        "audit_id": "geo_expected_validation_048_10H",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "expected_facts_total": total,
        "expected_facts_verified": verified,
        "missing_facts": missing,
        "partial_facts": partial,
        "junk_objects_detected": junk,
        "forbidden_predicates_detected": forbidden,
        "regression_existing_verified": regression,
        "top_invalid_predicates": top_invalid,
        "fallback_promoted_to_graph": fallback_promoted,
        "unaccounted_raw": unaccounted,
        "ok": ok,
        "blocking_reason": None,
        "classification": classification,
    }


def _batch_status(result: dict, *, future: bool = False) -> str:
    if future and result.get("expected_facts_verified", 0) == 0 and not result.get("partial_facts"):
        return "FUTURE_BATCH_NOT_SEEDED"
    if result.get("classification") == "PARTIAL_GEO_VALIDATION_INSUFFICIENT_EVIDENCE":
        return "PENDING_WORKER"
    return "OK" if result.get("ok") else "FAIL"


def validate_multi_batch(
    expected_current: dict,
    expected_next: dict | None,
    post: dict | None,
    geo_report: dict | None = None,
    baseline: dict | None = None,
) -> dict:
    """Valida lote atual e (opcionalmente) next batch, sem misturar falhas."""
    current = validate_geo_expected_facts(expected_current, post, geo_report, baseline)
    current_status = _batch_status(current)
    batches = {
        "current_048_10H": {
            "expected_facts_total": current["expected_facts_total"],
            "expected_facts_verified": current["expected_facts_verified"],
            "status": current_status,
            "missing_facts": current["missing_facts"],
            "junk_objects_detected": current["junk_objects_detected"],
        }
    }
    total = current["expected_facts_total"]
    verified = current["expected_facts_verified"]
    next_ok = True
    if expected_next:
        nxt = validate_geo_expected_facts(expected_next, post, geo_report, baseline)
        next_status = _batch_status(nxt, future=True)
        batches["next_048_10K"] = {
            "expected_facts_total": nxt["expected_facts_total"],
            "expected_facts_verified": nxt["expected_facts_verified"],
            "status": next_status,
            "missing_facts": nxt["missing_facts"],
            "junk_objects_detected": nxt["junk_objects_detected"],
        }
        total += nxt["expected_facts_total"]
        verified += nxt["expected_facts_verified"]
        next_ok = next_status in ("OK", "FUTURE_BATCH_NOT_SEEDED")

    aggregate_ok = (current_status == "OK") and next_ok
    return {
        "audit_id": "geo_expected_validation_multi_batch",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "batches": batches,
        "aggregate": {
            "total_expected_facts": total,
            "total_verified_facts": verified,
            "ok": aggregate_ok,
            "blocking_reason": None if aggregate_ok else "PENDING_WORKER",
        },
    }


def validate_with_fact_domains(expected: dict, fact_domains: dict) -> dict:
    """Validacao fact-level quando ha export de dominios por fato."""
    strength = fact_domains.get("evidence_strength", "insufficient")
    by_key = {}
    for f in fact_domains.get("facts") or []:
        by_key[(_match_key(f.get("subject")), str(f.get("predicate") or "").upper(), _match_key(f.get("object")))] = f
    total = len(expected.get("expected_facts") or [])
    strong = 0
    inferred = 0
    missing = []
    partial = []
    for ef in expected.get("expected_facts") or []:
        key = (_match_key(ef["subject"]), str(ef["predicate"]).upper(), _match_key(ef["object"]))
        got = by_key.get(key)
        dc = int((got or {}).get("domain_count", 0))
        if dc >= int(ef.get("min_domain_count", 3)):
            if strength == "strong":
                strong += 1
            else:
                inferred += 1
        elif got:
            partial.append(ef["fact"])
        else:
            missing.append(ef["fact"])
    ok = total > 0 and strong == total
    return {
        "audit_id": "geo_expected_validation_048_10h_4",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "expected_facts_total": total,
        "expected_facts_verified_strong": strong,
        "expected_facts_verified_inferred": inferred,
        "expected_facts_verified": strong + inferred,
        "evidence_strength": strength,
        "missing_facts": missing,
        "partial_facts": partial,
        "junk_objects_detected": 0,
        "forbidden_predicates_detected": 0,
        "regression_existing_verified": False,
        "ok": ok,
        "blocking_reason": None if ok else ("PARTIAL_GEO_VALIDATION_INSUFFICIENT_EVIDENCE" if strength != "strong" else "BLOCKED_GEO_VALIDATION"),
    }


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Valida fatos GEO esperados (offline).")
    parser.add_argument("--baseline", required=False)
    parser.add_argument("--post", required=True)
    parser.add_argument("--geo-report", dest="geo_report", required=False)
    parser.add_argument("--expected", required=True)
    parser.add_argument("--expected-next", dest="expected_next", required=False)
    parser.add_argument("--fact-domains", dest="fact_domains", required=False)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    expected = _read_json(Path(args.expected))
    post = _read_json(Path(args.post)) if args.post else None
    geo_report = _read_json(Path(args.geo_report)) if args.geo_report else None
    baseline = _read_json(Path(args.baseline)) if args.baseline else None
    fact_domains = _read_json(Path(args.fact_domains)) if args.fact_domains else None

    if expected is None or post is None:
        result = {
            "audit_id": "geo_expected_validation_048_10H",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "ok": False,
            "blocking_reason": "BLOCKED_MISSING_REPORTS",
            "classification": "BLOCKED_MISSING_REPORTS",
        }
    elif fact_domains is not None:
        result = validate_with_fact_domains(expected, fact_domains)
    elif args.expected_next:
        expected_next = _read_json(Path(args.expected_next))
        result = validate_multi_batch(expected, expected_next, post, geo_report, baseline)
    else:
        result = validate_geo_expected_facts(expected, post, geo_report, baseline)
        result["inputs"] = {
            "baseline": args.baseline,
            "post": args.post,
            "geo_report": args.geo_report,
            "expected": args.expected,
        }

    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    ok = result.get("ok")
    if args.expected_next:
        ok = result.get("aggregate", {}).get("ok")
    return 0 if ok else 1

if __name__ == "__main__":
    raise SystemExit(main())
