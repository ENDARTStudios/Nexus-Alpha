"""#058.5 — Botafogo EN extraction forensics (read-only).

Diagnostica **por que** a página EN do Botafogo produz `raw_triples=1`
(minerando a página 404 do Wikipedia) e classifica a etapa culpada entre:
fetch | cleaning | sentence_selection | extraction | span_validation |
predicate_mapping | entity_aliasing | persistence | unknown.

Não altera Neo4j/Qdrant, não chama o endpoint de ingestão, não faz reset,
não promove fato, não altera quórum, não altera seeds. Única escrita: JSON
local em ``reports/``.

Saída: ``reports/botafogo_en_extraction_forensics_YYYY-MM-DD.json``.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    load_dotenv(Path(__file__).resolve().parent.parent / ".env.local")
except ImportError:
    pass

from src.cognition.entity_linking_audit import (  # noqa: E402
    CREDENTIAL_MARKERS,
    assert_no_secret_markers,
)
from src.cognition.extraction_forensics import (  # noqa: E402
    build_comparison,
    build_forensics_report,
    build_source_forensics,
    evaluate_hypotheses,
)

# Alvo padrão: Botafogo (seed EN problemática + PT saudável para contraste).
DEFAULT_TARGETS: dict[str, dict[str, str]] = {
    "botafogo": {
        "canonical_entity": "BOTAFOGO DE FUTEBOL E REGATAS",
        "pt": "https://pt.wikipedia.org/wiki/Botafogo_de_Futebol_e_Regatas",
        "en": "https://en.wikipedia.org/wiki/Botafogo_F.C._%28Rio_de_Janeiro%29",
        # Candidatas EN verificadas (HTTP 200) — usadas só como evidência de
        # correção sugerida, não substituem a seed no forense.
        "en_candidates": [
            "https://en.wikipedia.org/wiki/Botafogo_FR",
            "https://en.wikipedia.org/wiki/Botafogo_de_Futebol_e_Regatas",
        ],
    },
}

READ_ONLY_CYPHER_MARKERS = (
    "MER" + "GE",
    "CRE" + "ATE",
    "SE" + "T ",
    "DELE" + "TE",
    "REMOV" + "E",
    "DRO" + "P",
    "DETACH " + "DELETE",
    "api/" + "ingest",
    "persist_" + "episodes",
)


def assert_read_only_source(source: str) -> None:
    """Falha se o script chamar APIs de escrita (AST), sem caçar strings de docstring."""
    tree = ast.parse(source)
    forbidden_attrs = {"ingest", "persist_episodes", "upsert", "detach_delete"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr.lower() in forbidden_attrs:
                raise ValueError(f"read-only violado: chamada .{node.func.attr}")


def _strip_html(html: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _fetch(url: str, *, timeout: float = 30.0) -> dict[str, Any]:
    import httpx

    headers = {"User-Agent": "Nexus-Alpha-Research/1.0 (read-only audit #058.5)"}
    try:
        resp = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
        return {
            "status": int(resp.status_code),
            "final_url": str(resp.url),
            "html": resp.text,
            "error": "",
        }
    except Exception as exc:
        return {
            "status": 0,
            "final_url": url,
            "html": "",
            "error": f"{type(exc).__name__}: {exc}",
        }


def forensics_one(url: str, *, timeout: float = 30.0) -> dict[str, Any]:
    """Fetch → clean → extract → refine → diagnose. Read-only, sem grafo."""
    from src.cognition.extractor import EntityExtractor
    from src.cognition.span_validator import fold_span
    from src.cognition.triple_refiner import refine_triple_ex
    from src.miner.source_productivity import (
        SENTENCE_SCORE_THRESHOLD,
        analyze_text,
        split_sentences,
    )
    from src.miner.source_productivity import score_candidate_sentence  # type: ignore
    from src.miner.web_miner import WebMiner

    fetch = _fetch(url, timeout=timeout)
    status = fetch["status"]
    html = fetch["html"]
    final_url = fetch["final_url"]
    content_length = len(html)

    if not html:
        return build_source_forensics(
            url=url,
            fetch_status=status,
            final_url=final_url,
            content_length=0,
            cleaned_text_length=0,
            sentences_considered=0,
            sentences_scored_above_threshold=0,
            raw_triples=0,
            canonical_triples=0,
            rejected_reasons={},
            text_sample="",
            ingested=False,
        )

    # Duas limpezas: WebMiner (produção) e _strip_html (parity dry-run).
    miner = WebMiner()
    cleaned = miner.clean_html(html, source_url=url)
    plain_webminer = cleaned.get("content") or ""
    plain_strip = _strip_html(html)
    # Prefere a limpeza mais longa (menos agressiva) para diagnóstico honesto.
    plain = plain_webminer if len(plain_webminer) >= len(plain_strip) else plain_strip
    text_sample = plain[:4000]

    sentences = split_sentences(plain)
    # score_candidate_sentence importado acima (via triple_refiner re-export).
    from src.cognition.triple_refiner import score_candidate_sentence as _score

    scored_count = sum(
        1 for s in sentences if _score(s) >= SENTENCE_SCORE_THRESHOLD
    )

    # Análise de produtividade (contadores canônicos).
    report = analyze_text(
        plain,
        url=final_url,
        status=status,
        content_length=content_length,
    )

    # Extração detalhada de spans (top raw subjects/objects/predicates).
    extractor = EntityExtractor(enable_fallback=True)
    raw = extractor.extract(plain)
    raw_subjects: list[str] = []
    raw_objects: list[str] = []
    raw_predicates: list[str] = []
    rejected_predicates: list[str] = []
    for t in raw:
        raw_subjects.append(t.subject)
        raw_objects.append(t.object)
        raw_predicates.append(t.predicate)

    # Contagem de rejeição de predicado no guard.
    from src.cognition.predicate_mapper import validate_predicate as _vp

    for pred in raw_predicates:
        _canon, reason = _vp(pred)
        if reason not in ("ok",) and reason:
            rejected_predicates.append(reason)

    # Top subjects rejeitados por span (aparecem nos rejected_reasons).
    top_subjects = _top_counts(raw_subjects)

    return build_source_forensics(
        url=url,
        fetch_status=status,
        final_url=final_url,
        content_length=content_length,
        cleaned_text_length=int(report.get("cleaned_text_length") or len(plain)),
        sentences_considered=int(report.get("sentences_considered") or len(sentences)),
        sentences_scored_above_threshold=int(
            report.get("sentences_scored_above_threshold") or scored_count
        ),
        raw_triples=int(report.get("raw_triples") or len(raw)),
        canonical_triples=int(report.get("canonical_triples") or 0),
        rejected_reasons=report.get("rejection_reasons") or {},
        top_raw_subjects=top_subjects[:5],
        top_raw_objects=_top_counts(raw_objects)[:5],
        top_raw_predicates=_top_counts(raw_predicates)[:5],
        top_rejected_predicates=_top_counts(rejected_predicates)[:5],
        persisted_fact_hashes=[],  # forense não consulta grafo por default
        fallback_used=False,
        masked_extraction_failure=False,
        text_sample=text_sample,
        ingested=False,
    )


def _top_counts(items: list[str], n: int = 5) -> list[str]:
    from collections import Counter

    return [k for k, _ in Counter(items).most_common(n)]


def _probe_en_candidates(urls: list[str], *, timeout: float = 20.0) -> list[dict[str, Any]]:
    """Sonda candidatas EN (apenas status/final_url — evidência de correção)."""
    out: list[dict[str, Any]] = []
    for url in urls:
        fetch = _fetch(url, timeout=timeout)
        out.append({
            "url": url,
            "fetch_status": fetch["status"],
            "final_url": fetch["final_url"],
            "content_length": len(fetch["html"]),
            "error": fetch["error"],
            "usable": fetch["status"] == 200 and len(fetch["html"]) > 10000,
        })
    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Forense de extração EN Botafogo (#058.5, read-only)"
    )
    parser.add_argument(
        "--target",
        default="botafogo",
        choices=list(DEFAULT_TARGETS.keys()),
        help="Alvo do forense",
    )
    parser.add_argument(
        "--out",
        default="",
        help="Caminho do relatório (default reports/botafogo_en_extraction_forensics_YYYY-MM-DD.json)",
    )
    parser.add_argument(
        "--no-candidates",
        action="store_true",
        help="Não sondar candidatas EN (só a seed problemática)",
    )
    parser.add_argument(
        "--quorum",
        type=int,
        default=int(os.environ.get("NEXUS_VERIFY_QUORUM", "3")),
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Timeout HTTP por URL (s)",
    )
    args = parser.parse_args()

    # Guard read-only do próprio script.
    source = Path(__file__).read_text(encoding="utf-8")
    assert_read_only_source(source)

    spec = DEFAULT_TARGETS[args.target]
    target_name = args.target

    print(f"[#058.5] Forense read-only — alvo={target_name}")
    print(f"  PT: {spec['pt']}")
    print(f"  EN (seed): {spec['en']}")

    pt = forensics_one(spec["pt"], timeout=args.timeout)
    en = forensics_one(spec["en"], timeout=args.timeout)

    comparison = build_comparison(pt, en)
    hypotheses = evaluate_hypotheses(pt, en)

    candidates: list[dict[str, Any]] = []
    if not args.no_candidates and spec.get("en_candidates"):
        print(f"  Sondando {len(spec['en_candidates'])} candidata(s) EN...")
        candidates = _probe_en_candidates(
            spec["en_candidates"], timeout=min(args.timeout, 20.0)
        )

    report = build_forensics_report(
        target=spec["canonical_entity"],
        sources=[pt, en],
        comparison=comparison,
        hypotheses=hypotheses,
        audit_id=f"botafogo_en_extraction_forensics_{datetime.now(timezone.utc):%Y-%m-%d}",
        quorum=args.quorum,
    )
    report["en_url_candidates"] = candidates
    report["seed_urls"] = {"pt": spec["pt"], "en": spec["en"]}
    report["suggested_en_url"] = next(
        (c["url"] for c in candidates if c.get("usable")), ""
    )

    text = json.dumps(report, ensure_ascii=False, indent=2)
    leaks = assert_no_secret_markers(text, CREDENTIAL_MARKERS)
    if leaks:
        raise SystemExit(
            f"[anti-leak] marcadores suspeitos no relatorio: {sorted(set(leaks))}"
        )

    out = Path(
        args.out
        or f"reports/botafogo_en_extraction_forensics_{datetime.now(timezone.utc):%Y-%m-%d}.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(text)
    print(f"\n[salvo em] {out}")

    # Resposta de sucesso do issue: diagnosis != unknown.
    primary = report["diagnosis_summary"]["primary_diagnosis"]
    if primary == "unknown":
        print(
            "[#058.5] AVISO: diagnosis=unknown — issue NAO concluido "
            "(exige causa identificada).",
            file=sys.stderr,
        )
        return 2
    print(
        f"[#058.5] diagnosis={primary} -> next="
        f"{report['diagnosis_summary']['next_issue_hint']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
