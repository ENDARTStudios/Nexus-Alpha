"""Nexus-Alpha — dry-run read-only F1: extração nominal/copular gateada (#058.11.2).

Compara, sobre o MESMO corpus (fetch único compartilhado), o pipeline de
produção (``extractor.extract`` cap=25 + ``refine_triple_ex``) com o extractor
antes (``enable_nominal_copular=False``) e depois (``True``) da F1.

Gates de commit (falha => NÃO commitar):
- ``new_triples_generated > 0``
- ``target_fact_hits > 0`` (novos hits canônicos alvo-alvo)
- ``ser_share_after <= 0.84`` (baseline ~0.81; anti-monocultura SER)
- ``generic_objects_rejected > 0``
- ``clause_like_residual == 0``
- ``pt_regression == False`` (keys before ⊆ keys after no corpus PT fixo)
- ``top_invalid_predicates == []``
- ``canonical_to_fact_gap == 0`` (todo raw-alvo novo sobrevive ao refine)
- ``unaccounted_raw == 0`` (integridade do próprio dry-run)

Read-only; única escrita: o JSON em ``reports/``. Não grava Neo4j/Qdrant,
não altera seeds, não roda Jev. Anti-leak: sem corpo de texto nos relatórios.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
sys.path.insert(0, _HERE)

import audit_extraction_gap as gap  # noqa: E402  (fetch_all, structural_match, refine)
from src.cognition.canonicalizer import SemanticCanonicalizer  # noqa: E402
from src.cognition.entity_linking_audit import (  # noqa: E402
    CREDENTIAL_MARKERS,
    assert_no_secret_markers,
)
from src.cognition.extractor import EntityExtractor  # noqa: E402
from src.cognition.predicate_mapper import INVALID_PREDICATE_REASONS  # noqa: E402
from src.cognition.triple_refiner import refine_triple_ex  # noqa: E402
from src.miner.web_miner import WebMiner  # noqa: E402

AUDIT_ID = "nominal_copular_dry_run_058_11_2"
SER_SHARE_MAX = 0.84
SER_SHARE_DELTA_MAX = 0.03  # <= ser_share_before + 3 p.p. (regra do usuário)
CLAUSE_RE = re.compile(
    r"\b(that|which|who|whom|whose|because|while|whereas|to be|was being|is being|"
    r"has been|have been|there (?:is|are|was|were))\b",
    re.IGNORECASE,
)

# Corpus PT fixo (não depende de rede): regressão garantida por construção.
PT_CORPUS = [
    "O Botafogo é sediado no Rio de Janeiro.",
    "Garrincha jogou no Botafogo por 12 anos, a maior parte de sua carreira.",
    "Pelé defendeu o Santos durante toda a sua carreira.",
    "O Santos FC é um clube brasileiro fundado em 1912.",
    "A sede é o Estádio Urbano Caldeira.",
    "O Botafogo conquistou seu terceiro título brasileiro após vencer o São Paulo.",
    "Garrincha também é pai de um filho sueco: Ulf Lindberg.",
    "O Santos é um dos maiores clubes do Brasil.",
]


def _fold(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def _key(triple: dict) -> tuple[str, str, str]:
    return (_fold(triple.get("subject")), _fold(triple.get("predicate")),
            _fold(triple.get("object")))


def _extract_page(extractor: EntityExtractor, text: str, canonicalizer: SemanticCanonicalizer
                  ) -> tuple[list[dict], list[dict], list[dict]]:
    """Pipeline de produção: extract cap=25 -> refine 1:1 (canonical, failures)."""
    raw = [t.to_dict() for t in extractor.extract(text, max_triples=25)]
    canonical, failures = gap.refine_with_reasons(raw, canonicalizer)
    return raw, canonical, failures


def _hit_keys(raw: list[dict], target: dict) -> set[tuple[str, str, str]]:
    return {_key(t) for t in raw if gap.structural_match(t, target)}


def _clause_like(triples: list[dict]) -> list[dict]:
    bad = []
    for t in triples:
        for field in ("subject", "object"):
            if CLAUSE_RE.search(str(t.get(field) or "")):
                bad.append(t)
                break
    return bad


def _ser_share(canonical: list[dict]) -> Optional[float]:
    if not canonical:
        return None
    ser = sum(1 for t in canonical if _fold(t.get("predicate")) == "ser")
    return round(ser / len(canonical), 4)


def _gate(value: Any, rule: str, passed: bool) -> dict:
    return {"value": value, "rule": rule, "pass": bool(passed)}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dry-run F1 nominal/copular gateado (#058.11.2, read-only)."
    )
    parser.add_argument("--spec", required=True,
                        help="JSON: {cases:[{case_id,fact_id,target_fact,url}]}")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    with open(args.spec, "r", encoding="utf-8") as fh:
        spec = json.load(fh)
    cases = spec.get("cases") or []

    miner = WebMiner()
    headers = miner.anti_block.generate_headers()
    canonicalizer = SemanticCanonicalizer()
    extractor_off = EntityExtractor(enable_fallback=True, enable_nominal_copular=False)
    extractor_on = EntityExtractor(enable_fallback=True, enable_nominal_copular=True)
    if extractor_on._nlp is None or extractor_off._nlp is None:
        raise SystemExit("spaCy indisponivel: rode com o venv311 (pt_core_news_sm).")

    urls = list(dict.fromkeys(case["url"] for case in cases))
    fetched = asyncio.run(gap.fetch_all(urls, headers))

    pages: list[dict] = []
    page_data: dict[str, dict] = {}
    before_raw: list[dict] = []
    after_raw: list[dict] = []
    before_can: list[dict] = []
    after_can: list[dict] = []
    before_fail: list[dict] = []
    after_fail: list[dict] = []
    per_case: list[dict] = []
    fetch_issues = 0

    for url in urls:
        entry = fetched.get(url) or {}
        html = entry.get("html") or ""
        status = int(entry.get("status") or 0)
        if not html:
            fetch_issues += 1
            pages.append({"url": url, "status": status, "fetch_issue": entry.get("error") or "fetch falhou",
                          "text_length": 0})
            continue
        text = miner.clean_html(html, source_url=url).get("content") or ""
        if not text:
            fetch_issues += 1
            pages.append({"url": url, "status": status, "fetch_issue": "empty_text",
                          "text_length": 0})
            continue
        b_raw, b_can, b_fail = _extract_page(extractor_off, text, canonicalizer)
        a_raw, a_can, a_fail = _extract_page(extractor_on, text, canonicalizer)
        page_data[url] = {"b_raw": b_raw, "b_can": b_can, "a_raw": a_raw, "a_can": a_can}
        before_raw.extend(b_raw); after_raw.extend(a_raw)
        before_can.extend(b_can); after_can.extend(a_can)
        before_fail.extend(b_fail); after_fail.extend(a_fail)
        pages.append({
            "url": url, "status": status, "fetch_issue": "", "text_length": len(text),
            "raw_before": len(b_raw), "raw_after": len(a_raw),
            "canonical_before": len(b_can), "canonical_after": len(a_can),
            "refine_failures_before": len(b_fail), "refine_failures_after": len(a_fail),
        })

    page_by_url = {p["url"]: p for p in pages}
    for case in cases:
        url = case["url"]
        page = page_by_url.get(url) or {}
        target = case.get("target_fact") or {}
        if page.get("fetch_issue") or url not in page_data:
            per_case.append({"case_id": case.get("case_id"), "fact_id": case.get("fact_id"),
                             "url": url, "fetch_issue": page.get("fetch_issue") or "missing",
                             "target_hits_before": 0, "target_hits_after": 0,
                             "target_hits_new": 0})
            continue
        data = page_data[url]
        hb_c, ha_c = _hit_keys(data["b_can"], target), _hit_keys(data["a_can"], target)
        hb_r, ha_r = _hit_keys(data["b_raw"], target), _hit_keys(data["a_raw"], target)
        per_case.append({
            "case_id": case.get("case_id"), "fact_id": case.get("fact_id"), "url": url,
            "target_hits_before": len(hb_c), "target_hits_after": len(ha_c),
            "target_hits_new": len(ha_c - hb_c),
            "target_hits_new_raw": len(ha_r - hb_r),
            "target_hits_lost": len(hb_c - ha_c),
        })

    # --- novas triplas (after \ before) ------------------------------------
    keys_before_raw = {_key(t) for t in before_raw}
    keys_before_can = {_key(t) for t in before_can}
    new_raw = [t for t in after_raw if _key(t) not in keys_before_raw]
    new_can = [t for t in after_can if _key(t) not in keys_before_can]

    # --- alvos --------------------------------------------------------------
    new_raw_hits: list[dict] = []
    new_can_hits: list[dict] = []
    facts = {c.get("fact_id"): c.get("target_fact") or {} for c in cases}
    for t in new_raw:
        if any(gap.structural_match(t, target) for target in facts.values()):
            new_raw_hits.append(t)
    for t in new_can:
        if any(gap.structural_match(t, target) for target in facts.values()):
            new_can_hits.append(t)
    target_fact_hits_new = sum(c.get("target_hits_new") or 0 for c in per_case)
    target_hits_lost = sum(c.get("target_hits_lost") or 0 for c in per_case)

    # --- refine dos novos raws --------------------------------------------
    new_failures: list[dict] = []
    for t in new_raw:
        refined, reason = refine_triple_ex(t, canonicalizer)
        if refined is None:
            new_failures.append({"triple": t, "reason": reason})
    gap_new_hits = sum(
        1 for f in new_failures
        if any(gap.structural_match(f["triple"], target) for target in facts.values())
    )
    invalid_preds = Counter(
        f["triple"].get("predicate") for f in new_failures
        if f.get("reason") in INVALID_PREDICATE_REASONS
    )
    top_invalid = [p for p, _ in invalid_preds.most_common(5)]

    # --- regressão PT fixa --------------------------------------------------
    pt_before: set[tuple[str, str, str]] = set()
    pt_after: set[tuple[str, str, str]] = set()
    for sentence in PT_CORPUS:
        for t in extractor_off.extract(sentence, max_triples=25):
            pt_before.add(_key(t.to_dict()))
        for t in extractor_on.extract(sentence, max_triples=25):
            pt_after.add(_key(t.to_dict()))
    pt_lost = sorted(pt_before - pt_after)
    pt_regression = bool(pt_lost)

    # --- contadores ---------------------------------------------------------
    gates: dict[str, dict] = {}
    ser_before = _ser_share(before_can)
    ser_after = _ser_share(after_can)
    generic_rejected = int(
        extractor_on.nominal_gate_reasons.get("nominal_object_generic", 0)
        + extractor_on.nominal_gate_reasons.get("nominal_object_weak", 0)
    )
    clause_bad = _clause_like(new_raw) + _clause_like(new_can)
    unaccounted = sum(
        int(p.get("raw_before", 0)) - int(p.get("canonical_before", 0))
        - int(p.get("refine_failures_before", 0)) for p in pages
    ) + sum(
        int(p.get("raw_after", 0)) - int(p.get("canonical_after", 0))
        - int(p.get("refine_failures_after", 0)) for p in pages
    )

    gates["new_triples_generated"] = _gate(len(new_raw), "> 0", len(new_raw) > 0)
    gates["target_fact_hits"] = _gate(target_fact_hits_new, "> 0",
                                       target_fact_hits_new > 0)
    gates["ser_share_after"] = _gate(ser_after, f"<= {SER_SHARE_MAX}",
                                     ser_after is not None and ser_after <= SER_SHARE_MAX)
    ser_delta = (round(ser_after - ser_before, 4)
                 if ser_after is not None and ser_before is not None else None)
    gates["ser_share_delta_pp"] = _gate(
        ser_delta,
        f"<= +{SER_SHARE_DELTA_MAX} (after - before)",
        ser_delta is not None and ser_delta <= SER_SHARE_DELTA_MAX,
    )
    gates["generic_objects_rejected"] = _gate(generic_rejected, "> 0",
                                              generic_rejected > 0)
    gates["clause_like_residual"] = _gate(len(clause_bad), "== 0", not clause_bad)
    gates["pt_regression"] = _gate(pt_regression, "== False", not pt_regression)
    gates["top_invalid_predicates"] = _gate(top_invalid, "== []", not top_invalid)
    gates["canonical_to_fact_gap"] = _gate(gap_new_hits, "== 0", gap_new_hits == 0)
    gates["unaccounted_raw"] = _gate(unaccounted, "== 0", unaccounted == 0)

    all_pass = all(g["pass"] for g in gates.values())
    document = {
        "audit_id": AUDIT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "promote_automatically": False,
        "verdict": "GO" if all_pass else "NO-GO",
        "pass": all_pass,
        "pipeline": {
            "fetch": "httpx + WebMiner.anti_block headers (paridade com minerador)",
            "extract": "extractor.extract(text, max_triples=25) + refine_triple_ex",
            "before": "EntityExtractor(enable_fallback=True, enable_nominal_copular=False)",
            "after": "EntityExtractor(enable_fallback=True, enable_nominal_copular=True)",
            "shared_corpus": "fetch unico; texto limpo uma vez por URL para before/after",
            "ser_share": "predicate == 'SER' no conjunto canonico agregado",
            "target_hits": "structural_match(subject_any/object_any) sem exigir predicado",
            "pt_regression": (
                "keys before \\ after do corpus PT fixo (deve ser vazio); por "
                "construcao: extract_spacy e por sentença com verbal primeiro "
                "(nao ha deslocamento em doc de 1 sentenca) e a flag off e "
                "byte-identica ao pre-F1"
            ),
        },
        "spec": {"cases": len(cases), "facts": sorted(facts)},
        "pages": pages,
        "fetch_issues": fetch_issues,
        "per_case": per_case,
        "totals": {
            "raw_before": len(before_raw), "raw_after": len(after_raw),
            "raw_new": len(new_raw),
            "canonical_before": len(before_can), "canonical_after": len(after_can),
            "canonical_new": len(new_can),
            "refine_failures_before": len(before_fail),
            "refine_failures_after": len(after_fail),
            "new_refine_failures": len(new_failures),
            "new_raw_target_hits": len(new_raw_hits),
            "new_canonical_target_hits": len(new_can_hits),
            "target_fact_hits_new": target_fact_hits_new,
            "target_hits_lost": target_hits_lost,
            "ser_share_before": ser_before, "ser_share_after": ser_after,
        },
        "new_triples_sample": new_raw[:30],
        "new_target_hits_sample": new_raw_hits[:20],
        "new_refine_failures": new_failures[:20],
        "clause_like_sample": clause_bad[:10],
        "pt_regression": {"lost_keys": pt_lost, "before_keys": len(pt_before),
                          "after_keys": len(pt_after)},
        "extractor_counters": {
            "before": {"rejection_reasons": dict(extractor_off.rejection_reasons),
                       "nominal_gate_reasons": dict(extractor_off.nominal_gate_reasons)},
            "after": {"rejection_reasons": dict(extractor_on.rejection_reasons),
                      "nominal_gate_reasons": dict(extractor_on.nominal_gate_reasons)},
        },
        "gates": gates,
    }

    text = json.dumps(document, ensure_ascii=False, indent=2)
    leaks = assert_no_secret_markers(text, CREDENTIAL_MARKERS)
    if leaks:
        raise SystemExit(f"[anti-leak] marcadores suspeitos no relatorio: {sorted(set(leaks))}")

    out_path = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(text)

    print(f"[{AUDIT_ID}] verdict={document['verdict']} out={out_path}")
    for name, gate in gates.items():
        print(f"  {'PASS' if gate['pass'] else 'FAIL'} {name}: "
              f"{gate['value']!r} ({gate['rule']})")
    if not all_pass:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
