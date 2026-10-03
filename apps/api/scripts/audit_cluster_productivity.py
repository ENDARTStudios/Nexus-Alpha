"""Nexus-Alpha — CLI read-only: produtividade de clusters com fato-alvo (#048.5).

Para cada cluster curado: fetch (UA anti-block do ``WebMiner``, paridade com o
minerador em produção) → limpeza → métricas de produtividade → triplas refinadas
→ ``target_fact_hits`` (triplas canônicas relacionadas ao fato-alvo).

Matching do fato-alvo (duas camadas, ambas reportadas):
- ``target_fact_hits_exact``: fold_span(subject_any) AND fold_span(object_any)
  na tripla canônica (determinístico);
- ``--jev``: cada tripla canônica é julgada por um Noul do Jev (TypeSafe System
  One) com limiar ``JEV_HIT_THRESHOLD``; ``target_fact_hits`` passa a ser a
  contagem confirmada por Jev.

``fallback_used`` = extractor sem modelo spaCy (NER real ausente);
``spacy_sparse_band`` = spacy_triples < SPACY_SPARSE_MIN (banda que mescla o
fallback regex). ``meets_acceptance`` usa ``fallback_used`` (modelo);
``meets_acceptance_dense`` exige também banda denso.

Por URL: ``url, final_url, status, cleaned_text_length, sentences_considered,
raw_triples, canonical_triples, rejection_reasons, target_fact_hits,
fallback_used, productive, notes`` + limiares do #048.5.

Por cluster: domínios/publishers **entre URLs aceitas**, ``eligible`` e
motivos de inelegibilidade (≥3 domínios produtivos, ≥2 publishers, ≥1 não-wiki
aceita — independência editorial plena exige fonte não-Wikimedia).

**Não** grava em Neo4j/Qdrant, **não** chama ``/api/ingest``, **não** promove
fato, **não** altera quórum. Única escrita: o JSON local em ``reports/``.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx  # noqa: E402

from src.cognition.canonicalizer import SemanticCanonicalizer  # noqa: E402
from src.cognition.entity_linking_audit import (  # noqa: E402
    CREDENTIAL_MARKERS,
    assert_no_secret_markers,
)
from src.cognition.extractor import EntityExtractor  # noqa: E402
from src.cognition.span_validator import fold_span  # noqa: E402
from src.cognition.triple_refiner import refine_triple_ex  # noqa: E402
from src.miner.source_productivity import (  # noqa: E402
    analyze_text,
    classify_extractive_quality,
    split_sentences,
)
from src.miner.web_miner import WebMiner  # noqa: E402

TOP_TRIPLES_SAMPLE = 5
MAX_SENTENCE_HITS = 10
JEV_HIT_THRESHOLD = 0.7
JEV_MODEL = "jev-latest"
JEV_MAX_QUESTIONS_PER_URL = 30


def _host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


def _base_domain(host: str) -> str:
    host = host[4:] if host.startswith("www.") else host
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def _publisher(url: str) -> str:
    host = _host(url)
    if host.endswith("wikipedia.org"):
        return "wikimedia"
    return _base_domain(host) or host


def _is_wikipedia(url: str) -> bool:
    return _host(url).endswith("wikipedia.org")


def _fold(value: Any) -> str:
    return fold_span(str(value or ""))


_CANONICALIZER: Optional[SemanticCanonicalizer] = None


def _canonicalizer() -> SemanticCanonicalizer:
    global _CANONICALIZER
    if _CANONICALIZER is None:
        _CANONICALIZER = SemanticCanonicalizer()
    return _CANONICALIZER


def extract_triples_with_diagnostics(
    text: str,
    extractor: EntityExtractor,
    max_triples: int = 25,
) -> tuple[list[dict], dict[str, Any]]:
    """Triplas refinadas + diagnóstico NER/fallback.

    Espelha a banda sparse de ``EntityExtractor.extract`` (spacy < 10 mescla o
    fallback regex) para expor ``spacy_sparse_band`` no relatório.
    """
    spacy_triples = extractor.extract_spacy(text, max_triples=max_triples)
    spacy_count = len(spacy_triples)
    dense = spacy_count >= extractor.SPACY_SPARSE_MIN or not extractor.enable_fallback
    if dense:
        raw = spacy_triples
    else:
        fallback_triples = extractor.extract_fallback(text, max_triples=max_triples)
        if not spacy_triples:
            raw = fallback_triples
        else:
            seen: set[tuple[str, str, str]] = set()
            merged = []
            for triple in fallback_triples + spacy_triples:
                key = (triple.subject.casefold(), triple.predicate.casefold(), triple.object.casefold())
                if key in seen:
                    continue
                seen.add(key)
                merged.append(triple)
            raw = merged[:max_triples]

    canonical: list[dict] = []
    rejected = 0
    for triple in raw:
        refined, _reason = refine_triple_ex(triple.to_dict(), _canonicalizer())
        if refined is None:
            rejected += 1
            continue
        canonical.append(refined)

    diagnostics = {
        "spacy_triples": spacy_count,
        "spacy_available": extractor._nlp is not None,
        "fallback_used": extractor._nlp is None,
        "spacy_sparse_band": not dense,
        "rejected_in_pass": rejected,
    }
    return canonical, diagnostics


def _matches_target(text_folded: str, target: dict[str, Any]) -> bool:
    subject_terms = [_fold(t) for t in target.get("subject_any") or []]
    object_terms = [_fold(t) for t in target.get("object_any") or []]
    if subject_terms and not any(term in text_folded for term in subject_terms):
        return False
    if object_terms and not any(term in text_folded for term in object_terms):
        return False
    return bool(subject_terms or object_terms)


def _triple_text(triple: dict[str, Any]) -> str:
    return f"{_fold(triple.get('subject'))} {_fold(triple.get('predicate'))} {_fold(triple.get('object'))}"


def apply_acceptance(report: dict[str, Any]) -> None:
    """(Re)calcula ``acceptance_checks``/``meets_acceptance*`` do #048.5."""
    min_canonical = 2 if report.get("is_wikipedia") else 1
    checks = {
        "status_200": int(report.get("status", 0)) == 200,
        "cleaned_text": int(report.get("cleaned_text_length", 0)) > 0,
        "sentences": int(report.get("sentences_considered", 0)) > 0,
        "raw_triples_gte_5": int(report.get("raw_triples", 0)) >= 5,
        "canonical_ok": int(report.get("canonical_triples", 0)) >= min_canonical,
        "fallback_false": not bool(report.get("fallback_used", True)),
        "target_fact_hit": int(report.get("target_fact_hits", 0)) >= 1,
    }
    report["acceptance_checks"] = checks
    report["meets_acceptance"] = all(checks.values())
    report["meets_acceptance_dense"] = report["meets_acceptance"] and not bool(
        report.get("spacy_sparse_band", False)
    )
    report["productive"] = report["extractive_quality"] == "productive"


def build_url_report(
    url: str,
    fetch_result: dict,
    target: dict[str, Any],
    extractor: EntityExtractor,
) -> dict[str, Any]:
    html = fetch_result.get("html") or ""
    if not html:
        report = analyze_text("", url=url, status=fetch_result.get("status", 0), content_length=0)
        report["final_url"] = fetch_result.get("final_url") or url
        report["error"] = fetch_result.get("error") or ""
        report["extractive_quality"] = "unproductive"
        report["notes"] = (
            f"fetch falhou ({report['error']})" if report["error"]
            else f"fetch falhou (status {report['status']})"
        )
        report["target_fact_hits"] = 0
        report["target_fact_hits_exact"] = 0
        report["target_fact_sentences"] = 0
        report["target_fact_sample"] = []
        report["canonical_list"] = []
        report["fallback_used"] = not (extractor._nlp is not None)
        report["spacy_sparse_band"] = False
        report["spacy_triples"] = 0
        report["spacy_available"] = extractor._nlp is not None
    else:
        cleaned = WebMiner().clean_html(html, source_url=url)
        text = cleaned.get("content") or ""
        report = analyze_text(
            text,
            url=url,
            status=fetch_result.get("status", 200),
            content_length=len(html),
        )
        report["final_url"] = fetch_result.get("final_url") or url
        report["error"] = ""

        canonical, diagnostics = extract_triples_with_diagnostics(text, extractor)
        exact_hits = [triple for triple in canonical if _matches_target(_triple_text(triple), target)]
        sentence_hits = [
            sentence for sentence in split_sentences(text)
            if _matches_target(_fold(sentence), target)
        ][:MAX_SENTENCE_HITS]
        report["canonical_list"] = canonical
        report["target_fact_hits_exact"] = len(exact_hits)
        report["target_fact_hits"] = len(exact_hits)
        report["target_fact_sentences"] = len(sentence_hits)
        report["target_fact_sample"] = exact_hits[:TOP_TRIPLES_SAMPLE]
        report["fallback_used"] = diagnostics["fallback_used"]
        report["spacy_sparse_band"] = diagnostics["spacy_sparse_band"]
        report["spacy_triples"] = diagnostics["spacy_triples"]
        report["spacy_available"] = diagnostics["spacy_available"]

    report["is_wikipedia"] = _is_wikipedia(report.get("final_url") or url)
    report["publisher"] = _publisher(report.get("final_url") or url)
    report["jev_applied"] = False
    report["masked_extraction_failure"] = False
    apply_acceptance(report)
    return report


async def fetch_one(client: httpx.AsyncClient, url: str, headers: dict) -> dict:
    last_error = ""
    for attempt in (1, 2):
        try:
            response = await client.get(url, headers=headers, timeout=25.0)
            if response.status_code == 200:
                return {
                    "status": 200,
                    "final_url": str(response.url),
                    "html": response.text,
                    "error": "",
                }
            last_error = f"status {response.status_code}"
            if response.status_code not in (403, 408, 429, 500, 502, 503, 504):
                break
        except Exception as exc:
            last_error = type(exc).__name__
        if attempt == 1:
            await asyncio.sleep(2.0)
    return {"status": 0, "final_url": url, "html": "", "error": last_error}


def jev_verify_report(report: dict[str, Any], target: dict[str, Any]) -> None:
    """Julga as triplas canônicas da URL com Noul do Jev (TypeSafe)."""
    from typesafe_sdk import Noul, NoulCriteria, TypeSafeClient

    canonical: list[dict] = report.get("canonical_list") or []
    if not canonical:
        return
    triples = canonical[:JEV_MAX_QUESTIONS_PER_URL]
    state = {
        "target_fact": {
            "description": target.get("description"),
            "subject_any": target.get("subject_any"),
            "object_any": target.get("object_any"),
        }
    }
    criteria = NoulCriteria(
        true=(
            "A tripla afirma, implica ou é diretamente sobre o fato-alvo "
            "(mesma entidade principal e mesma conquista/relação do fato)"
        ),
        false=(
            "A tripla é sobre outro assunto, é ruído de navegação, ou não "
            "permite concluir nada sobre o fato-alvo"
        ),
    )
    questions = {
        f"t{i}": Noul(
            instructions={
                "triple": triple,
                "question": "A tripla `triple` expressa ou afirma o fato-alvo `target_fact`?",
            },
            criteria=criteria,
        )
        for i, triple in enumerate(triples)
    }
    with TypeSafeClient() as client:
        response = client.system_one(model=JEV_MODEL, state=state, questions=questions)
    scores = [float(response.answers[f"t{i}"].noul) for i in range(len(triples))]
    hits = [triple for triple, score in zip(triples, scores) if score >= JEV_HIT_THRESHOLD]
    report["jev_applied"] = True
    report["jev_threshold"] = JEV_HIT_THRESHOLD
    report["jev_scores"] = [round(s, 3) for s in scores]
    report["jev_hit_triples"] = hits[:TOP_TRIPLES_SAMPLE]
    report["target_fact_hits"] = len(hits)


def cluster_summary(cluster: dict[str, Any], reports: list[dict]) -> dict[str, Any]:
    accepted = [r for r in reports if r["meets_acceptance"]]
    accepted_nonwiki = [r for r in accepted if not r["is_wikipedia"]]
    accepted_wiki = [r for r in accepted if r["is_wikipedia"]]

    domains_all = sorted({_host(r.get("final_url") or r["url"]) or _host(r["url"]) for r in reports} - {""})
    domains_accepted = sorted(
        {_host(r.get("final_url") or r["url"]) or _host(r["url"]) for r in accepted} - {""}
    )
    publishers_accepted = sorted({_publisher(r.get("final_url") or r["url"]) for r in accepted} - {""})

    reasons: list[str] = []
    if len(domains_accepted) < 3:
        reasons.append(f"dominios_aceitos<3 ({len(domains_accepted)})")
    if len(publishers_accepted) < 2:
        reasons.append(f"publishers_aceitos<2 ({len(publishers_accepted)})")
    if not accepted_nonwiki:
        reasons.append("nenhuma fonte nao-Wikimedia aceita (independencia editorial plena)")
    if not accepted:
        reasons.append("nenhuma URL atingiu os limiares de aceitacao")

    return {
        "cluster_id": cluster.get("cluster_id"),
        "target_fact": cluster.get("target_fact"),
        "urls_evaluated": len(reports),
        "accepted": len(accepted),
        "accepted_wikipedia": [r["url"] for r in accepted_wiki],
        "accepted_non_wikipedia": [r["url"] for r in accepted_nonwiki],
        "domains_evaluated": domains_all,
        "domains_accepted": domains_accepted,
        "domain_count": len(domains_accepted),
        "publishers_accepted": publishers_accepted,
        "publisher_count": len(publishers_accepted),
        "accepted_dense": sum(1 for r in accepted if r["meets_acceptance_dense"]),
        "eligible": not reasons,
        "ineligible_reasons": reasons,
        "per_url": reports,
    }


def _load_dotenv() -> None:
    if os.environ.get("TYPESAFE_API_KEY"):
        return
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(root, ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            if key == "TYPESAFE_API_KEY" and key not in os.environ:
                os.environ[key] = value.strip().strip('"').strip("'")


def main() -> None:
    parser = argparse.ArgumentParser(description="Produtividade de clusters com fato-alvo (read-only).")
    parser.add_argument("--spec", required=True, help="JSON: {clusters:[{cluster_id,target_fact,urls}]}")
    parser.add_argument("--out", required=True)
    parser.add_argument("--jev", action="store_true", help="Julga triplas candidatas com Jev (TypeSafe Noul)")
    args = parser.parse_args()

    with open(args.spec, "r", encoding="utf-8") as fh:
        spec = json.load(fh)
    clusters = spec.get("clusters") or []

    if args.jev:
        _load_dotenv()
        if not os.environ.get("TYPESAFE_API_KEY"):
            raise SystemExit("[jev] TYPESAFE_API_KEY ausente (env ou .env)")

    miner = WebMiner()
    headers = miner.anti_block.generate_headers()
    extractor = EntityExtractor(enable_fallback=True)

    async def run() -> list[dict]:
        limits = httpx.Limits(max_keepalive_connections=5, max_connections=8)
        summaries = []
        async with httpx.AsyncClient(limits=limits, follow_redirects=True, verify=True) as client:
            for cluster in clusters:
                target = cluster.get("target_fact") or {}
                urls = cluster.get("urls") or []
                fetched = await asyncio.gather(*[fetch_one(client, url, headers) for url in urls])
                reports = [
                    build_url_report(url, result, target, extractor)
                    for url, result in zip(urls, fetched)
                ]
                if args.jev:
                    for report in reports:
                        jev_verify_report(report, target)
                        apply_acceptance(report)
                reports.sort(key=lambda r: (not r["meets_acceptance"], r["url"]))
                summaries.append(cluster_summary(cluster, reports))
        return summaries

    cluster_reports = asyncio.run(run())
    eligible = [c for c in cluster_reports if c["eligible"]]

    document = {
        "audit_id": "cluster_productivity_048_5",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "promote_automatically": False,
        "pipeline": {
            "fetch": "httpx + WebMiner.anti_block headers (paridade com minerador)",
            "extractor": "EntityExtractor(enable_fallback=True)",
            "spacy_model": "pt_core_news_sm",
            "target_fact_matching_exact": "fold_span(subject_any) AND fold_span(object_any) em tripla canonica",
            "target_fact_matching_jev": (
                f"Noul por tripla canonica, limiar {JEV_HIT_THRESHOLD}, modelo {JEV_MODEL}"
                if args.jev else "nao aplicado (--jev ausente)"
            ),
            "fallback_used_meaning": "modelo spaCy indisponivel (NER real ausente)",
            "spacy_sparse_band_meaning": "spacy_triples < 10 — banda que mescla fallback regex (aceitacao alternativa: meets_acceptance_dense)",
        },
        "clusters": cluster_reports,
        "summary": {
            "clusters_total": len(cluster_reports),
            "clusters_eligible": len(eligible),
            "eligible_cluster_ids": [c["cluster_id"] for c in eligible],
            "jev_applied": bool(args.jev),
        },
        "truthfulness_note": {
            "read_only": True,
            "no_neo4j_no_qdrant_no_ingest": True,
            "does_not_change_quorum_or_confirmacoes": True,
            "classification_is_diagnostic_only": True,
        },
    }

    text = json.dumps(document, ensure_ascii=False, indent=2)
    leaks = assert_no_secret_markers(text, CREDENTIAL_MARKERS)
    if leaks:
        raise SystemExit(f"[anti-leak] marcadores suspeitos no relatorio: {sorted(set(leaks))}")

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(text)

    for cluster in cluster_reports:
        status = "ELIGIVEL" if cluster["eligible"] else "NAO-ELIGIVEL"
        print(f"[{status}] {cluster['cluster_id']}: dominios_aceitos={cluster['domain_count']} publishers={cluster['publisher_count']} aceitas={cluster['accepted']} (wiki={len(cluster['accepted_wikipedia'])}, nao-wiki={len(cluster['accepted_non_wikipedia'])}, dense={cluster['accepted_dense']})")
        for reason in cluster["ineligible_reasons"]:
            print(f"    - {reason}")
        for report in cluster["per_url"]:
            mark = "OK  " if report["meets_acceptance"] else "FAIL"
            jev = f" jev={max(report['jev_scores']):.2f}" if report.get("jev_scores") else ""
            print(
                f"    [{mark}] q={report['extractive_quality']:12s} raw={report['raw_triples']:2d} canon={report['canonical_triples']:2d} "
                f"hits={report['target_fact_hits']} (exato={report['target_fact_hits_exact']}) fb={int(report['fallback_used'])} sparse={int(report['spacy_sparse_band'])}{jev} | {report['url'][:78]}"
            )
    print(f"\n[salvo em] {args.out}")


if __name__ == "__main__":
    main()
