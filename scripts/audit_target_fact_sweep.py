"""Nexus-Alpha — CLI read-only: varredura de fatos-alvo alternativos (#048.5a).

Responde à pergunta do operador (#048.5 passo 2):

    Existe algum fato-alvo histórico que o extrator atual consiga converter
    em tripla canônica em 3+ domínios distintos?

Para cada fato-alvo candidato (spec ``targets``): fetch (UA anti-block do
``WebMiner``, paridade produção) → limpeza → triplas refinadas → mede, por
domínio:

- ``target_fact_sentences``: sentenças que expressam o fato (sentença-alvo);
- ``exact_hits``: match estrutural na tripla canônica — campo sujeito contém
  ``subject_any``, campo objeto contém ``object_any`` e predicado ∈
  ``predicates_ok`` (vocabulário controlado);
- ``jev``: cada tripla canônica julgada por Noul do Jev (TypeSafe System One),
  limiar ``SWEEP_JEV_THRESHOLD`` (0.65);
- ``hit`` = ``exact`` OU ``jev >= limiar``, com triplas de objeto date-like
  descartadas (regra de elegibilidade).

Elegibilidade (critério do operador, #048.5 passo 2):

    domains_with_target_canonical_triple >= 3
    E publishers distintos >= 2
    E ao menos 1 fora de Wikipedia
    E no máximo 1 domínio contribuindo apenas com predicado SER
    E nenhuma URL JS-only/paywall/404 entre as testadas
    E nenhuma tripla-alvo dependente de objeto date-like (descartadas)

**Não** grava em Neo4j/Qdrant, **não** chama ``/api/ingest``, **não** altera
``config/seed_clusters.yaml``. Única escrita: o JSON local em ``reports/``.
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

import httpx  # noqa: E402

import audit_cluster_productivity as base  # noqa: E402
from src.cognition.entity_linking_audit import (  # noqa: E402
    CREDENTIAL_MARKERS,
    assert_no_secret_markers,
)
from src.cognition.extractor import EntityExtractor  # noqa: E402
from src.cognition.span_validator import fold_span  # noqa: E402
from src.miner.source_productivity import analyze_text, split_sentences  # noqa: E402
from src.miner.web_miner import WebMiner  # noqa: E402

SWEEP_JEV_THRESHOLD = 0.65
MAX_JEV_TRIPLES = 30
MAX_SENTENCE_SAMPLES = 3
MAX_HIT_SAMPLES = 5

_MONTHS_PT = (
    "janeiro", "fevereiro", "marco", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)


def _fold(value: Any) -> str:
    return fold_span(str(value or ""))


def _is_date_like_object(obj: Any) -> bool:
    """Objeto que é data pura (ano isolado, dd/mm, mês por extenso).

    ``COPA LIBERTADORES DE 2024`` **não** é date-like (entidade de
    competição); ``1995`` e ``8 DE DEZEMBRO DE 2024`` são.
    """
    text = _fold(obj)
    if not text:
        return False
    if re.fullmatch(r"(18|19|20)\d{2}", text):
        return True
    if re.fullmatch(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", text):
        return True
    return any(re.search(rf"\b{month}\b", text) for month in _MONTHS_PT)


def _structural_exact_hit(triple: dict, target: dict, predicates_ok: set[str]) -> bool:
    """Match exato: sujeito↔subject_any, objeto↔object_any, predicado controlado."""
    subject_terms = [_fold(t) for t in target.get("subject_any") or []]
    object_terms = [_fold(t) for t in target.get("object_any") or []]
    triple_subject = _fold(triple.get("subject"))
    triple_object = _fold(triple.get("object"))
    triple_predicate = _fold(triple.get("predicate"))
    if not subject_terms or not any(t in triple_subject for t in subject_terms):
        return False
    if not object_terms or not any(t in triple_object for t in object_terms):
        return False
    if predicates_ok and triple_predicate not in predicates_ok:
        return False
    return True


def _body_has_subject(text: str, target: dict) -> bool:
    folded = _fold(text)
    subject_terms = [_fold(t) for t in target.get("subject_any") or []]
    return any(term in folded for term in subject_terms)


def jev_judge(target: dict, triples: list[dict]) -> list[float]:
    """Julga cada tripla com um Noul do Jev (TypeSafe) — limiar do sweep."""
    from typesafe_sdk import Noul, NoulCriteria, TypeSafeClient

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
        response = client.system_one(model=base.JEV_MODEL, state=state, questions=questions)
    return [float(response.answers[f"t{i}"].noul) for i in range(len(triples))]


def build_base(url: str, fetch_result: dict, extractor: EntityExtractor) -> dict:
    """Fetch + limpeza + métricas + triplas canônicas (independe do alvo)."""
    html = fetch_result.get("html") or ""
    final_url = fetch_result.get("final_url") or url
    if not html:
        return {
            "url": url,
            "final_url": final_url,
            "status": int(fetch_result.get("status") or 0),
            "fetch_error": fetch_result.get("error") or "fetch falhou",
            "fetch_issue": "http_error",
            "text": "",
            "report": None,
            "canonical_list": [],
            "diagnostics": None,
        }
    cleaned = WebMiner().clean_html(html, source_url=url)
    text = cleaned.get("content") or ""
    report = analyze_text(
        text,
        url=url,
        status=int(fetch_result.get("status") or 200),
        content_length=len(html),
    )
    canonical, diagnostics = base.extract_triples_with_diagnostics(text, extractor)
    return {
        "url": url,
        "final_url": final_url,
        "status": int(report.get("status") or 200),
        "fetch_error": "",
        "fetch_issue": "",
        "text": text,
        "report": report,
        "canonical_list": canonical,
        "diagnostics": diagnostics,
    }


def evaluate_domain(base_entry: dict, target: dict, predicates_ok: set[str]) -> dict:
    """Métricas de um domínio para um fato-alvo (sem Jev)."""
    text = base_entry["text"]
    report = base_entry.get("report") or {}
    subject_in_body = _body_has_subject(text, target) if text else False
    fetch_issue = base_entry["fetch_issue"]
    if not fetch_issue and base_entry["status"] == 200 and not subject_in_body:
        fetch_issue = "js_shell_no_subject"

    sentence_hits = [
        sentence for sentence in split_sentences(text)
        if base._matches_target(_fold(sentence), target)
    ] if text else []

    exact_hits = [
        triple for triple in base_entry["canonical_list"]
        if _structural_exact_hit(triple, target, predicates_ok)
    ]

    domain = {
        "url": base_entry["url"],
        "final_url": base_entry["final_url"],
        "status": base_entry["status"],
        "fetch_error": base_entry["fetch_error"],
        "fetch_issue": fetch_issue,
        "publisher": base._publisher(base_entry["final_url"]),
        "is_wikipedia": base._is_wikipedia(base_entry["final_url"]),
        "cleaned_text_length": int(report.get("cleaned_text_length", 0)),
        "sentences_considered": int(report.get("sentences_considered", 0)),
        "raw_triples": int(report.get("raw_triples", 0)),
        "canonical_triples_reported": int(report.get("canonical_triples", 0)),
        "canonical_triples": len(base_entry["canonical_list"]),
        "rejection_reasons": report.get("rejection_reasons") or {},
        "fallback_used": bool((base_entry.get("diagnostics") or {}).get("fallback_used", True)),
        "spacy_sparse_band": bool((base_entry.get("diagnostics") or {}).get("spacy_sparse_band", False)),
        "target_fact_sentences": len(sentence_hits),
        "target_fact_sentence_samples": [
            s.strip()[:200] for s in sentence_hits[:MAX_SENTENCE_SAMPLES]
        ],
        "exact_hits": exact_hits[:MAX_HIT_SAMPLES],
        "exact_hit_count": len(exact_hits),
        "jev_applied": False,
        "jev_max": None,
        "jev_scores": [],
        "jev_hits": [],
        "hit_triples": [],
        "date_like_hits": [],
        "hit_predicates": [],
        "hit": False,
        "ser_only_hit": False,
        "notes": "",
    }
    if fetch_issue == "http_error":
        domain["notes"] = f"fetch falhou ({base_entry['fetch_error']})"
    elif fetch_issue == "js_shell_no_subject":
        domain["notes"] = "HTML servido sem o sujeito do fato (corpo JS-only/paywall)"
    return domain


def apply_hits(domain: dict, target: dict, scores: Optional[list[float]]) -> None:
    """Combina exact + Jev, filtra date-like e deriva ``hit``/``ser_only_hit``."""
    canonical_list = domain.pop("_canonical_list", [])
    triple_by_index = canonical_list
    jev_hit_pairs: list[tuple[dict, float]] = []
    if scores is not None:
        domain["jev_applied"] = True
        domain["jev_scores"] = [round(s, 3) for s in scores]
        domain["jev_max"] = round(max(scores), 3) if scores else None
        jev_hit_pairs = [
            (triple, score)
            for triple, score in zip(triple_by_index, scores)
            if score >= SWEEP_JEV_THRESHOLD
        ]
        domain["jev_hits"] = [
            {"triple": triple, "jev_score": round(score, 3)}
            for triple, score in jev_hit_pairs[:MAX_HIT_SAMPLES]
        ]

    exact_keys = {
        (base._fold(t.get("subject")), base._fold(t.get("predicate")), base._fold(t.get("object")))
        for t in domain["exact_hits"]
    }
    merged: dict[tuple, dict] = {}
    for triple in triple_by_index:
        key = (
            base._fold(triple.get("subject")),
            base._fold(triple.get("predicate")),
            base._fold(triple.get("object")),
        )
        if key in exact_keys:
            merged[key] = {"triple": triple, "via": "exact", "jev_score": None}
    for triple, score in jev_hit_pairs:
        key = (
            base._fold(triple.get("subject")),
            base._fold(triple.get("predicate")),
            base._fold(triple.get("object")),
        )
        entry = merged.setdefault(key, {"triple": triple, "via": "jev", "jev_score": None})
        entry["jev_score"] = round(score, 3)
        if entry["via"] == "exact":
            entry["via"] = "exact+jev"

    valid: list[dict] = []
    date_like: list[dict] = []
    for entry in merged.values():
        if _is_date_like_object(entry["triple"].get("object")):
            date_like.append(entry)
        else:
            valid.append(entry)

    domain["hit_triples"] = valid[:MAX_HIT_SAMPLES]
    domain["date_like_hits"] = date_like[:MAX_HIT_SAMPLES]
    predicates = [base._fold(e["triple"].get("predicate")) for e in valid]
    domain["hit_predicates"] = predicates
    domain["hit"] = bool(valid)
    domain["ser_only_hit"] = bool(valid) and all(p == "ser" for p in predicates)


def evaluate_target(target: dict, cache: dict[str, dict], run_jev: bool) -> dict:
    target_fact = target.get("target_fact") or {}
    predicates_ok = {
        _fold(p) for p in target.get("predicates_ok") or []
    }
    domain_reports: list[dict] = []
    for url in target.get("urls") or []:
        if url not in cache:
            raise SystemExit(f"[spec] URL fora do pool: {url}")
        domain = evaluate_domain(cache[url], target_fact, predicates_ok)
        domain["_canonical_list"] = cache[url]["canonical_list"][:MAX_JEV_TRIPLES]
        domain_reports.append(domain)

    if run_jev:
        for domain in domain_reports:
            triples = domain.get("_canonical_list") or []
            if triples and domain["fetch_issue"] == "":
                domain["jev_scores_pending"] = jev_judge(target_fact, triples)
    for domain in domain_reports:
        scores = domain.pop("jev_scores_pending", None)
        apply_hits(domain, target, scores)
        domain.pop("_canonical_list", None)

    hit_domains = [d for d in domain_reports if d["hit"]]
    domains_hit = sorted({base._host(d["final_url"]) or base._host(d["url"]) for d in hit_domains} - {""})
    publishers_hit = sorted({d["publisher"] for d in hit_domains} - {""})
    nonwiki_hit = [d for d in hit_domains if not d["is_wikipedia"]]
    ser_only = sorted(
        {base._host(d["final_url"]) or base._host(d["url"]) for d in hit_domains if d["ser_only_hit"]} - {""}
    )
    fetch_problems = [
        {"url": d["url"], "issue": d["fetch_issue"], "error": d["fetch_error"]}
        for d in domain_reports
        if d["fetch_issue"]
    ]

    triples_per_domain: dict[str, int] = {}
    jev_max_per_domain: dict[str, Optional[float]] = {}
    for domain in domain_reports:
        host = base._host(domain["final_url"]) or base._host(domain["url"])
        triples_per_domain[host] = triples_per_domain.get(host, 0) + int(domain["canonical_triples"])
        value = domain.get("jev_max")
        if host not in jev_max_per_domain or (
            value is not None
            and (jev_max_per_domain[host] is None or value > jev_max_per_domain[host])
        ):
            jev_max_per_domain[host] = value

    predicate_counter: Counter = Counter()
    objects: set[str] = set()
    date_like_count = 0
    rejection: Counter = Counter()
    for domain in domain_reports:
        for entry in domain["hit_triples"]:
            predicate_counter[base._fold(entry["triple"].get("predicate"))] += 1
            objects.add(str(entry["triple"].get("object") or ""))
        date_like_count += len(domain["date_like_hits"])
        for reason, count in (domain.get("rejection_reasons") or {}).items():
            rejection[reason] += int(count)

    blocking: list[str] = []
    if len(domains_hit) < 3:
        blocking.append(f"dominios_com_tripla_alvo<3 ({len(domains_hit)})")
    if len(publishers_hit) < 2:
        blocking.append(f"publishers_com_tripla_alvo<2 ({len(publishers_hit)})")
    if not nonwiki_hit:
        blocking.append("nenhum dominio fora de Wikipedia com tripla-alvo")
    if len(ser_only) > 1:
        blocking.append(f"mais de 1 dominio contribuindo so com SER ({len(ser_only)})")
    if fetch_problems:
        blocking.append(f"url testada com fetch invalido (JS-only/paywall/404): {len(fetch_problems)}")

    return {
        "fact_id": target.get("fact_id"),
        "target_fact": target.get("target_fact"),
        "predicates_ok": sorted(target.get("predicates_ok") or []),
        "sources_tested": len(domain_reports),
        "domains_with_target_sentence": sorted(
            {
                base._host(d["final_url"]) or base._host(d["url"])
                for d in domain_reports
                if d["target_fact_sentences"] > 0
            }
            - {""}
        ),
        "domains_with_target_canonical_triple": domains_hit,
        "publishers_with_target_canonical_triple": publishers_hit,
        "non_wikipedia_with_target_canonical_triple": sorted(
            {d["publisher"] for d in nonwiki_hit} - {""}
        ),
        "ser_only_domains": ser_only,
        "triples_per_domain": triples_per_domain,
        "jev_max_per_domain": jev_max_per_domain,
        "predicate_canonical": dict(predicate_counter.most_common()),
        "object_canonical": sorted(objects - {""}),
        "rejection_reasons": dict(rejection.most_common()),
        "date_like_hits_count": date_like_count,
        "fetch_issues": fetch_problems,
        "eligible": not blocking,
        "blocking_reasons": blocking,
        "blocking_reason": "; ".join(blocking),
        "per_domain": domain_reports,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Varredura read-only de fatos-alvo (#048.5a).")
    parser.add_argument("--spec", required=True, help="JSON: {targets:[{fact_id,target_fact,predicates_ok,urls}]}")
    parser.add_argument("--out", required=True)
    parser.add_argument("--jev", action="store_true", help="Julga triplas canônicas com Jev (TypeSafe Noul)")
    args = parser.parse_args()

    with open(args.spec, "r", encoding="utf-8") as fh:
        spec = json.load(fh)
    targets = spec.get("targets") or []

    if args.jev:
        base._load_dotenv()
        if not os.environ.get("TYPESAFE_API_KEY"):
            raise SystemExit("[jev] TYPESAFE_API_KEY ausente (env ou .env)")

    miner = WebMiner()
    headers = miner.anti_block.generate_headers()
    extractor = EntityExtractor(enable_fallback=True)

    all_urls: list[str] = []
    for target in targets:
        for url in target.get("urls") or []:
            if url not in all_urls:
                all_urls.append(url)

    async def fetch_pool() -> dict[str, dict]:
        limits = httpx.Limits(max_keepalive_connections=5, max_connections=8)
        cache: dict[str, dict] = {}
        async with httpx.AsyncClient(limits=limits, follow_redirects=True, verify=True) as client:
            fetched = await asyncio.gather(*[base.fetch_one(client, url, headers) for url in all_urls])
        for url, fetch_result in zip(all_urls, fetched):
            cache[url] = build_base(url, fetch_result, extractor)
            entry = cache[url]
            print(
                f"[fetch] status={entry['status']:3d} canon={len(entry['canonical_list']):2d} "
                f"issue={entry['fetch_issue'] or '-':20s} | {url[:80]}"
            )
        return cache

    cache = asyncio.run(fetch_pool())

    sweep_reports = [evaluate_target(target, cache, args.jev) for target in targets]
    eligible = [t for t in sweep_reports if t["eligible"]]

    document = {
        "audit_id": "target_fact_sweep_048_5a",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "promote_automatically": False,
        "pipeline": {
            "fetch": "httpx + WebMiner.anti_block headers (paridade com minerador)",
            "extractor": "EntityExtractor(enable_fallback=True) + refine_triple_ex",
            "spacy_model": "pt_core_news_sm",
            "exact_hit_rule": (
                "campo sujeito contem subject_any E campo objeto contem object_any "
                "E predicado em predicates_ok (vocabulario controlado)"
            ),
            "jev": (
                f"Noul por tripla canonica, limiar {SWEEP_JEV_THRESHOLD}, modelo {base.JEV_MODEL}"
                if args.jev else "nao aplicado (--jev ausente)"
            ),
            "hit_rule": "hit = exact OU jev>=limiar; triplas com objeto date-like descartadas",
            "date_like_rule": (
                "ano isolado, dd/mm/aaaa ou mes por extenso no objeto; "
                "'COPA LIBERTADORES DE 2024' (entidade de competicao) NAO e date-like"
            ),
            "ser_rule": "no maximo 1 dominio cujas triplas-alvo sejam todas SER",
            "eligibility": (
                ">=3 dominios com tripla-alvo, >=2 publishers, >=1 fora de Wikipedia, "
                "<=1 dominio so-SER, nenhuma URL JS-only/paywall/404, "
                "nenhuma tripla-alvo com objeto date-like"
            ),
        },
        "targets": sweep_reports,
        "summary": {
            "targets_total": len(sweep_reports),
            "targets_eligible": len(eligible),
            "eligible_fact_ids": [t["fact_id"] for t in eligible],
            "jev_applied": bool(args.jev),
            "sweep_verdict": (
                "3_clusters_viable" if len(eligible) >= 3
                else ("partial_" + str(len(eligible)) if eligible else "no_viable_target")
            ),
        },
        "truthfulness_note": {
            "read_only": True,
            "no_neo4j_no_qdrant_no_ingest": True,
            "does_not_change_quorum_or_confirmacoes": True,
            "does_not_touch_seed_clusters_yaml": True,
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

    for target in sweep_reports:
        status = "ELIGIVEL" if target["eligible"] else "NAO-ELIGIVEL"
        print(
            f"[{status}] {target['fact_id']}: "
            f"dom_tripla={len(target['domains_with_target_canonical_triple'])} "
            f"dom_sentenca={len(target['domains_with_target_sentence'])} "
            f"publishers={len(target['publishers_with_target_canonical_triple'])} "
            f"so_SER={len(target['ser_only_domains'])}"
        )
        for reason in target["blocking_reasons"]:
            print(f"    - {reason}")
        for domain in target["per_domain"]:
            mark = "HIT " if domain["hit"] else "miss"
            jev = f" jev={domain['jev_max']:.2f}" if domain.get("jev_max") is not None else ""
            print(
                f"    [{mark}] sent={domain['target_fact_sentences']:2d} "
                f"canon={domain['canonical_triples']:2d} exact={domain['exact_hit_count']} "
                f"hits={len(domain['hit_triples'])} date={len(domain['date_like_hits'])}"
                f"{jev} issue={domain['fetch_issue'] or '-'} | {domain['url'][:74]}"
            )
    print(f"\n[salvo em] {args.out}")


if __name__ == "__main__":
    main()
