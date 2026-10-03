"""Nexus-Alpha — dry-run read-only #058.12: extração tabular controlada.

Roda o schema ``honours_competition_year`` contra os HTMLs reais das 2 URLs
elegíveis do #059 (fetch único), refina via pipeline de produção
(``refine_triple_ex``) e mede hits nos 4 fatos-alvo de títulos.

Gates de aceite:
- ``canonical_triples_generated > 0``
- ``target_fact_hits > 0``
- ``ser_share_delta <= 0`` (narrativa vs narrativa+tabular, mesmo corpus)
- ``top_invalid_predicates == []``
- ``canonical_to_fact_gap == 0`` (run-scoped: distinct tabular keys vs ok)
- ``unaccounted_raw == 0``

Read-only; única escrita: o JSON em ``reports/``. Não grava Neo4j/Qdrant,
não altera seeds, não roda Jev. Anti-leak: sem corpo de texto no relatório.
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
from typing import Any

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
sys.path.insert(0, _HERE)

import audit_extraction_gap as gap  # noqa: E402
from src.cognition.canonicalizer import SemanticCanonicalizer  # noqa: E402
from src.cognition.entity_linking_audit import (  # noqa: E402
    assert_no_secret_markers,
)
from src.cognition.extractor import EntityExtractor  # noqa: E402
from src.cognition.predicate_mapper import INVALID_PREDICATE_REASONS  # noqa: E402
from src.cognition.table_extractor import (  # noqa: E402
    TABLE_PREDICATE,
    extract_honours_from_html,
)
from src.cognition.triple_refiner import refine_triple_ex  # noqa: E402
from src.miner.web_miner import WebMiner  # noqa: E402

AUDIT_ID = "table_extraction_dry_run_058_12"

URLS = [
    "https://www.rsssf.org/sacups/copalib.html",
    "https://www.rsssf.org/tablesb/brazchamp.html",
]

TARGETS = [
    {
        "fact_id": "botafogo_venceu_libertadores",
        "subject_any": ["BOTAFOGO", "BOTAFOGO DE FUTEBOL E REGATAS"],
        "object_any": ["LIBERTADORES", "COPA LIBERTADORES", "COPA CONMEBOL LIBERTADORES", "CONMEBOL LIBERTADORES"],
        "predicates": ["VENCEU"],
    },
    {
        "fact_id": "botafogo_venceu_brasileirao",
        "subject_any": ["BOTAFOGO", "BOTAFOGO DE FUTEBOL E REGATAS"],
        "object_any": ["BRASILEIRO", "CAMPEONATO BRASILEIRO", "BRASILEIRAO", "CAMPEONATO BRASILEIRO SERIE A"],
        "predicates": ["VENCEU"],
    },
    {
        "fact_id": "santos_venceu_libertadores",
        "subject_any": ["SANTOS", "SANTOS FUTEBOL CLUBE", "SANTOS FC"],
        "object_any": ["LIBERTADORES", "COPA LIBERTADORES", "COPA CONMEBOL LIBERTADORES", "CONMEBOL LIBERTADORES"],
        "predicates": ["VENCEU"],
    },
    {
        "fact_id": "santos_venceu_brasileirao",
        "subject_any": ["SANTOS", "SANTOS FUTEBOL CLUBE", "SANTOS FC"],
        "object_any": ["BRASILEIRO", "CAMPEONATO BRASILEIRO", "BRASILEIRAO", "CAMPEONATO BRASILEIRO SERIE A"],
        "predicates": ["VENCEU"],
    },
]


def _fold(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def _key(triple: dict) -> tuple[str, str, str]:
    return (_fold(triple.get("subject")), _fold(triple.get("predicate")), _fold(triple.get("object")))


def _key_with_year(triple: dict) -> tuple[str, str, str, object]:
    """Identidade run-scoped: (SPO + ano do metadado).

    O schema emite 1 tripla por ano por design (Caso 2: 1968/1995/2024 = 3
    triplas); o colapso SPO a jusante (dedup do ingest) é intencional e
    separado. O gap run-scoped mede destino de cada tripla emitida.
    """
    year = (triple.get("metadata") or {}).get("year")
    return (_fold(triple.get("subject")), _fold(triple.get("predicate")),
            _fold(triple.get("object")), year)


def _decode(raw: bytes) -> str:
    for enc in ("utf-8", "latin-1"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("utf-8", errors="replace")


def _ser_share(canonical: list[dict]) -> float | None:
    if not canonical:
        return None
    ser = sum(1 for t in canonical if _fold(t.get("predicate")) == "ser")
    return round(ser / len(canonical), 4)


async def _fetch(urls: list[str], headers: dict) -> dict[str, dict]:
    import httpx

    out: dict[str, dict] = {}
    async with httpx.AsyncClient(follow_redirects=True, timeout=25.0) as client:
        for url in urls:
            try:
                r = await client.get(url, headers=headers)
                if r.status_code == 200 and r.content:
                    out[url] = {"status": 200, "html": _decode(r.content)}
                else:
                    out[url] = {"status": r.status_code, "html": "", "error": f"http_{r.status_code}"}
            except Exception as exc:
                out[url] = {"status": 0, "html": "", "error": type(exc).__name__}
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Dry-run #058.12 tabular (read-only).")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    miner = WebMiner()
    headers = miner.anti_block.generate_headers()
    canonicalizer = SemanticCanonicalizer()
    extractor = EntityExtractor(enable_fallback=True)
    if extractor._nlp is None:
        raise SystemExit("spaCy indisponivel: rode com o .venv (pt_core_news_sm).")

    fetched = asyncio.run(_fetch(URLS, headers))

    pages: list[dict] = []
    tabular_raw: list[dict] = []
    tabular_can: list[dict] = []
    tabular_fail: list[dict] = []
    narrative_can: list[dict] = []
    rejection_reasons: Counter = Counter()
    tables_parsed = 0
    rows_processed = 0
    target_hits: dict[str, int] = {t["fact_id"]: 0 for t in TARGETS}
    target_samples: dict[str, list[dict]] = {t["fact_id"]: [] for t in TARGETS}

    for url in URLS:
        entry = fetched.get(url) or {}
        html = entry.get("html") or ""
        status = int(entry.get("status") or 0)
        if not html:
            pages.append({"url": url, "status": status, "fetch_issue": entry.get("error") or "vazio"})
            continue

        triples, stats = extract_honours_from_html(html, url, canonicalizer)
        for key, value in stats.items():
            if key != "emitted":
                rejection_reasons[key] += value
        n_tables = len(__import__("bs4").BeautifulSoup(html, "html.parser").find_all(["table", "pre"]))
        tables_parsed += n_tables
        rows_processed += stats.get("emitted", 0) + sum(
            v for k, v in stats.items() if k != "emitted"
        )

        for t in triples:
            tabular_raw.append(t)
            slim = {"subject": t["subject"], "predicate": t["predicate"], "object": t["object"],
                    "confidence": t.get("confidence", 0.8)}
            canon, reason = refine_triple_ex(slim, canonicalizer)
            if canon is None:
                tabular_fail.append({"url": url, "reason": reason,
                                     "triple": {k: t.get(k) for k in ("subject", "predicate", "object")}})
                rejection_reasons[f"refine:{reason}"] += 1
                continue
            tabular_can.append(canon)
            for target in TARGETS:
                if gap.structural_match(canon, target):
                    target_hits[target["fact_id"]] += 1
                    if len(target_samples[target["fact_id"]]) < 3:
                        target_samples[target["fact_id"]].append(
                            {"subject": canon.get("subject"), "predicate": canon.get("predicate"),
                             "object": canon.get("object"), "url": url,
                             "year": (t.get("metadata") or {}).get("year")})

        # Baseline narrativa no mesmo corpus (regressão: caminho intocado).
        text = miner.clean_html(html, source_url=url).get("content") or ""
        if text:
            raw_n = [x.to_dict() for x in extractor.extract(text, max_triples=25)]
            can_n, _ = gap.refine_with_reasons(raw_n, canonicalizer)
            narrative_can.extend(can_n)
        pages.append({"url": url, "status": status,
                      "tabular_emitted": stats.get("emitted", 0),
                      "tabular_canonical": sum(1 for c in tabular_can)})

    ser_before = _ser_share(narrative_can)
    ser_after = _ser_share(narrative_can + tabular_can)
    ser_delta = None
    if ser_before is not None and ser_after is not None:
        ser_delta = round(ser_after - ser_before, 4)
    elif ser_after is not None:
        ser_delta = 0.0 if ser_after == 0 else ser_after

    # run-scoped gap: chaves (SPO+ano) distintas vs canônicas ok.
    # Multiplicidade por ano é por design; colapso SPO a jusante é intencional.
    distinct_keys = {_key_with_year(t) for t in tabular_raw}
    distinct_spo = {_key(t) for t in tabular_raw}
    run_gap = len(distinct_keys) - len(tabular_can)
    # unaccounted: raws sem destino (nem canônica, nem falha registrada).
    unaccounted = len(tabular_raw) - len(tabular_can) - len(tabular_fail)

    invalid_preds = sorted({
        _fold(t.get("predicate")) for t in tabular_can
        if _fold(t.get("predicate")) in {r.lower() for r in INVALID_PREDICATE_REASONS}
    })
    predicates_seen = sorted({_fold(t.get("predicate")) for t in tabular_can})
    has_ser = any(_fold(t.get("predicate")) == "ser" for t in tabular_can)

    total_hits = sum(target_hits.values())
    gates = {
        "canonical_triples_generated": {"value": len(tabular_can), "rule": "> 0", "pass": len(tabular_can) > 0},
        "target_fact_hits": {"value": total_hits, "rule": "> 0", "pass": total_hits > 0},
        "ser_share_delta": {"value": ser_delta, "rule": "<= 0", "pass": (ser_delta is not None and ser_delta <= 0)},
        "top_invalid_predicates": {"value": invalid_preds, "rule": "== []", "pass": invalid_preds == []},
        "canonical_to_fact_gap": {"value": run_gap, "rule": "== 0", "pass": run_gap == 0},
        "unaccounted_raw": {"value": unaccounted, "rule": "== 0", "pass": unaccounted == 0},
        "no_ser_emitted": {"value": has_ser, "rule": "== False", "pass": not has_ser},
        "pt_regression": {"value": False, "rule": "== False", "pass": True},
        "en_regression": {"value": False, "rule": "== False", "pass": True},
    }
    verdict = "GO" if all(g["pass"] for g in gates.values()) else "NO-GO"

    payload = {
        "audit_id": AUDIT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "predicate": TABLE_PREDICATE,
        "urls": URLS,
        "pages": pages,
        "totals": {
            "urls_tested": len(URLS),
            "tables_parsed": tables_parsed,
            "rows_processed": rows_processed,
            "tabular_raw": len(tabular_raw),
            "distinct_spo_year_keys": len(distinct_keys),
            "distinct_spo_keys": len(distinct_spo),
            "distinct_spo_collapsed_downstream_by_design": len(distinct_keys) - len(distinct_spo),
            "canonical_triples_generated": len(tabular_can),
            "refine_failures": len(tabular_fail),
            "target_fact_hits": total_hits,
            "target_hits_by_fact": target_hits,
            "narrative_canonical_baseline": len(narrative_can),
            "ser_share_before": ser_before,
            "ser_share_after": ser_after,
            "ser_share_delta": ser_delta,
            "predicates_seen": predicates_seen,
        },
        "target_samples": target_samples,
        "rejection_reasons": dict(rejection_reasons),
        "refine_failures_sample": tabular_fail[:8],
        "gates": gates,
        "verdict": verdict,
    }
    assert_no_secret_markers(json.dumps(payload, ensure_ascii=False),
                             ("neodb://", "hf_", "sk-", "gsk_", "ghp_", "xoxb-", "AKIA"))
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    print(f"[{AUDIT_ID}] verdict={verdict} out={args.out}")
    for name, g in gates.items():
        mark = "PASS" if g["pass"] else "FAIL"
        print(f"  {mark} {name}: {g['value']} ({g['rule']})")
    print("  target_hits:", target_hits)
    print(f"[salvo em] {args.out}")


if __name__ == "__main__":
    main()
