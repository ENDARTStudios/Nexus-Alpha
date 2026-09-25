"""Nexus-Alpha — CLI read-only: diagnóstico sentença-alvo → tripla-alvo (#058.11).

Responde, por caso (fato-alvo × URL), por que ``target_fact_sentences > 0``
não converge em tripla canônica contendo o fato-alvo. Read-only; nenhuma
mudança de código de extração é feita aqui (experimentos de cap alto são
em memória, apenas para medir ``max_triples_truncation``).

Experimentos por caso:
- ``raw25``/``canon25``: pipeline de produção (``extractor.extract`` cap=25);
- ``raw500``/``canon500``: idem com cap=500 (só diagnóstico);
- sonda por sentença-alvo (espelho da árvore de decisão de ``extract_spacy``
  no contexto do documento e isolada) → classe de causa mecânica;
- refine de triplas-alvo cruas → motivo → classe (mapper/span validator).

Classes de causa: ``sentence_not_considered``, ``sentence_score_below_threshold``,
``max_triples_truncation``, ``missing_subject_entity``, ``missing_object_entity``,
``no_relation_pattern``, ``predicate_unmapped``, ``object_rejected_by_span_validator``,
``duplicate_or_wrong_key``, ``table_without_narrative``, ``anaphora_unresolved``,
``long_or_composed_sentence``, ``date_or_list_contamination``, ``unknown``.

**Não** grava em Neo4j/Qdrant, **não** altera ``extractor.py`` nem seeds.
Única escrita: o JSON local em ``reports/``.
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
import audit_target_fact_sweep as sweep  # noqa: E402
from src.cognition.canonicalizer import SemanticCanonicalizer  # noqa: E402
from src.cognition.entity_linking_audit import (  # noqa: E402
    CREDENTIAL_MARKERS,
    assert_no_secret_markers,
)
from src.cognition.extractor import (  # noqa: E402
    EntityExtractor,
    is_function_word_span,
    rescue_truncated_toponym,
    strip_boundary_noise,
)
from src.cognition.predicate_mapper import (  # noqa: E402
    INVALID_PREDICATE_REASONS,
    validate_predicate,
)
from src.cognition.triple_refiner import refine_triple_ex, score_candidate_sentence  # noqa: E402
from src.miner.source_productivity import SENTENCE_SCORE_THRESHOLD, split_sentences  # noqa: E402
from src.miner.web_miner import WebMiner  # noqa: E402

MAX_TARGET_SENTENCES = 6
GENERIC_SUBJECTS = frozenset({
    "clube", "club", "time", "team", "equipe", "side", "elenco", "squad",
    "ele", "ela", "eles", "elas", "he", "she", "they", "it", "isso", "isto",
    "aquilo", "jogador", "player", "ano", "year", "titulo", "title",
})
CLASS_PRIORITY = [
    "predicate_unmapped",
    "max_triples_truncation",
    "object_rejected_by_span_validator",
    "missing_subject_entity",
    "missing_object_entity",
    "anaphora_unresolved",
    "long_or_composed_sentence",
    "date_or_list_contamination",
    "no_relation_pattern",
    "sentence_not_considered",
    "unknown",
]


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", base._fold(value)).strip()


def _terms(target: dict, key: str) -> list[str]:
    return [_norm(t) for t in target.get(key) or []]


def structural_match(fields: dict, target: dict, require_predicate: bool = False,
                     predicates_ok: Optional[set[str]] = None) -> bool:
    subject_terms = _terms(target, "subject_any")
    object_terms = _terms(target, "object_any")
    subject = _norm(fields.get("subject"))
    obj = _norm(fields.get("object"))
    if not subject_terms or not any(t in subject for t in subject_terms):
        return False
    if not object_terms or not any(t in obj for t in object_terms):
        return False
    if require_predicate:
        predicate = _norm(fields.get("predicate"))
        if predicates_ok and predicate not in predicates_ok:
            return False
    return True


def refine_with_reasons(raw: list, canonicalizer: SemanticCanonicalizer) -> tuple[list, list]:
    canonical: list = []
    failures: list = []
    for triple in raw:
        raw_dict = triple.to_dict() if hasattr(triple, "to_dict") else dict(triple)
        refined, reason = refine_triple_ex(raw_dict, canonicalizer)
        if refined is None:
            failures.append({"triple": raw_dict, "reason": reason})
        else:
            canonical.append(refined)
    return canonical, failures


def map_refine_reason(failure: dict) -> str:
    reason = str(failure.get("reason") or "")
    triple = failure.get("triple") or {}
    if reason in INVALID_PREDICATE_REASONS or reason == "unmapped_predicate":
        return "predicate_unmapped"
    if reason.startswith("object_"):
        return "object_rejected_by_span_validator"
    if reason.startswith("subject_"):
        return "missing_subject_entity"
    if reason == "missing_entity":
        if not _norm(triple.get("subject")):
            return "missing_subject_entity"
        if not _norm(triple.get("object")):
            return "missing_object_entity"
        return "unknown"
    if reason == "self_loop":
        return "duplicate_or_wrong_key"
    return "unknown"


def _is_generic(term: str) -> bool:
    folded = _norm(term)
    return folded in GENERIC_SUBJECTS


def _extract_term(extractor: EntityExtractor, token, full_text: str) -> Optional[str]:
    term = extractor._normalize_term(strip_boundary_noise(extractor._phrase_text(token)))
    term = rescue_truncated_toponym(term, full_text)
    if is_function_word_span(term) or not extractor._valid_term(term):
        return None
    return term


def probe_sentence(extractor: EntityExtractor, target: dict, tokens, full_text: str) -> dict:
    """Espelho da árvore de decisão de ``extract_spacy`` para um segmento."""
    tokens = list(tokens)
    root = next((t for t in tokens if t.dep_ == "ROOT"), None)
    evidence: dict[str, Any] = {
        "root": root.text if root else None,
        "root_pos": root.pos_ if root else None,
        "root_lemma": root.lemma_ if root else None,
        "nsubj": None,
        "obj_dep": None,
        "extracted_subject": None,
        "extracted_object": None,
        "subject_term_ok": False,
        "object_term_ok": False,
    }
    if root is None or root.pos_ not in ("VERB", "AUX"):
        evidence["class"] = "no_relation_pattern"
        evidence["reason"] = "root_ausente_ou_nao_verbal"
        return evidence
    predicate, predicate_reason = validate_predicate(root.lemma_)
    evidence["predicate"] = predicate
    if predicate_reason in INVALID_PREDICATE_REASONS:
        evidence["class"] = "predicate_unmapped"
        evidence["reason"] = predicate_reason
        return evidence
    subj_tok = next(
        (c for c in root.children if c.dep_ in ("nsubj", "nsubj:pass")), None
    )
    obj_tok = next(
        (
            c for c in root.children
            if c.dep_ in ("obj", "dobj", "iobj", "attr", "obl", "xcomp")
        ),
        None,
    )
    evidence["nsubj"] = subj_tok.text if subj_tok else None
    evidence["obj_dep"] = obj_tok.dep_ if obj_tok else None
    if subj_tok is None or obj_tok is None:
        evidence["class"] = "no_relation_pattern"
        evidence["reason"] = "sem_nsubj" if subj_tok is None else "sem_obj"
        return evidence
    subject = _extract_term(extractor, subj_tok, full_text)
    obj = _extract_term(extractor, obj_tok, full_text)
    if subject is None or obj is None:
        evidence["class"] = "no_relation_pattern"
        evidence["reason"] = "guarda_de_span_na_extracao"
        evidence["extracted_subject"] = subject
        evidence["extracted_object"] = obj
        return evidence
    evidence["extracted_subject"] = subject
    evidence["extracted_object"] = obj
    subject_terms = _terms(target, "subject_any")
    object_terms = _terms(target, "object_any")
    subject_ok = any(t in _norm(subject) for t in subject_terms)
    object_ok = any(t in _norm(obj) for t in object_terms)
    evidence["subject_term_ok"] = subject_ok
    evidence["object_term_ok"] = object_ok
    if subject_ok and object_ok:
        evidence["class"] = "converted_in_probe"
        evidence["reason"] = ""
        return evidence
    if not subject_ok:
        if subj_tok.pos_ == "PRON" or _is_generic(subject):
            evidence["class"] = "anaphora_unresolved"
            evidence["reason"] = "sujeito_pronominal_ou_generico"
        else:
            evidence["class"] = "missing_subject_entity"
            evidence["reason"] = "sujeito_extraido_sem_o_termo_alvo"
        return evidence
    if sweep._is_date_like_object(obj):
        evidence["class"] = "date_or_list_contamination"
        evidence["reason"] = "objeto_date_like"
    elif obj_tok.dep_ in ("xcomp", "ccomp") or obj_tok.pos_ == "VERB":
        evidence["class"] = "long_or_composed_sentence"
        evidence["reason"] = "objeto_clausal"
    elif obj_tok.pos_ == "PRON" or _is_generic(obj):
        evidence["class"] = "anaphora_unresolved"
        evidence["reason"] = "objeto_pronominal_ou_generico"
    else:
        evidence["class"] = "missing_object_entity"
        evidence["reason"] = "objeto_extraido_sem_o_termo_alvo"
    return evidence


def find_doc_sent(doc, sentence: str):
    key = _norm(sentence)[:60]
    if not key:
        return None
    for sent in doc.sents:
        text = _norm(sent.text)
        if text[:60] == key or key[:40] in text or text[:40] in key:
            return sent
    return None


def dominant_class(classes: list[str]) -> str:
    counts = Counter(classes)
    if not counts:
        return "unknown"
    return sorted(
        counts,
        key=lambda cls: (-counts[cls], CLASS_PRIORITY.index(cls) if cls in CLASS_PRIORITY else 99),
    )[0]


def diagnose_case(case: dict, extractor: EntityExtractor, canonicalizer: SemanticCanonicalizer,
                  fetch_cache: dict[str, dict]) -> dict:
    target = case.get("target_fact") or {}
    url = case["url"]
    entry = fetch_cache[url]
    text = entry["text"]

    sentences = split_sentences(text)
    target_sentences = [
        (idx, sentence)
        for idx, sentence in enumerate(sentences)
        if base._matches_target(_norm(sentence), target)
    ][:MAX_TARGET_SENTENCES]

    raw25 = extractor.extract(text, max_triples=25)
    raw500 = extractor.extract(text, max_triples=500)
    canon25, fail25 = refine_with_reasons(raw25, canonicalizer)
    canon500, fail500 = refine_with_reasons(raw500, canonicalizer)

    raw25_hits = [t.to_dict() for t in raw25 if structural_match(t.to_dict(), target)]
    raw500_hits = [t.to_dict() for t in raw500 if structural_match(t.to_dict(), target)]
    canon25_hits = [t for t in canon25 if structural_match(t, target)]
    canon500_hits = [t for t in canon500 if structural_match(t, target)]
    target_failures = [
        {**failure, "mapped_class": map_refine_reason(failure)}
        for failure in fail500
        if structural_match(failure["triple"], target)
    ]

    doc = extractor._nlp(text) if extractor._nlp is not None else None
    probes: list[dict] = []
    for idx, sentence in target_sentences:
        iso_raw = extractor.extract_spacy(sentence, max_triples=50)
        iso_target = any(structural_match(t.to_dict(), target) for t in iso_raw)
        if extractor._nlp is not None:
            isolated = probe_sentence(extractor, target, extractor._nlp(sentence), sentence)
        else:
            isolated = {"class": "unknown", "reason": "sem_modelo"}
        sent_doc = find_doc_sent(doc, sentence) if doc is not None else None
        doc_probe = (
            probe_sentence(extractor, target, sent_doc, text)
            if sent_doc is not None else None
        )
        score = score_candidate_sentence(sentence, canonicalizer)
        probes.append({
            "sentence_index": idx,
            "sentence": sentence[:240],
            "token_count": len(sentence.split()),
            "score": round(score, 3),
            "above_score_threshold": score >= SENTENCE_SCORE_THRESHOLD,
            "is_long": len(sentence.split()) >= 40,
            "has_parenthetical": "(" in sentence,
            "has_coordination": bool(re.search(r"[^,],\s*\w+\s+e\s+\w+", sentence)),
            "isolated_spacy_target": iso_target,
            "isolated": isolated,
            "doc_sent_matched": sent_doc is not None,
            "doc": doc_probe,
        })

    if canon500_hits and not canon25_hits:
        classification = "max_triples_truncation"
        evidence = "tripla-alvo aparece so com cap=500 (ausente no cap=25)"
    elif target_failures:
        classification = dominant_class([f["mapped_class"] for f in target_failures])
        evidence = f"refino rejeitou tripla-alvo crua: {Counter(f['reason'] for f in target_failures)}"
    else:
        classes = []
        for probe in probes:
            for layer in ("doc", "isolated"):
                layer_probe = probe.get(layer) or {}
                layer_class = layer_probe.get("class")
                if layer_class and layer_class != "converted_in_probe":
                    classes.append(layer_class)
                    break
        if classes:
            classification = dominant_class(classes)
            evidence = f"sonda mecanica por sentenca: {Counter(classes)}"
        elif probes and any(
            (p.get("doc") or {}).get("class") == "converted_in_probe"
            or (p.get("isolated") or {}).get("class") == "converted_in_probe"
            for p in probes
        ):
            classification = "unknown"
            evidence = "sonda espelhada diz que a sentenca produziria a tripla, mas raw500 nao a contem (divergencia espelho/real)"
        elif not target_sentences:
            classification = "sentence_not_considered"
            evidence = "nenhuma sentenca com sujeito+objeto do fato"
        else:
            classification = "unknown"
            evidence = "sem classificacao mecanica"

    return {
        "case_id": case.get("case_id"),
        "fact_id": case.get("fact_id"),
        "url": url,
        "final_url": entry["final_url"],
        "status": entry["status"],
        "fetch_issue": entry["fetch_issue"],
        "fallback_used": bool((entry.get("diagnostics") or {}).get("fallback_used", True)),
        "spacy_sparse_band": bool((entry.get("diagnostics") or {}).get("spacy_sparse_band", False)),
        "sentences_total": len(sentences),
        "target_sentences_count": len(target_sentences),
        "raw25_count": len(raw25),
        "raw500_count": len(raw500),
        "canon25_count": len(canon25),
        "canon500_count": len(canon500),
        "raw_target_hits_25": raw25_hits,
        "raw_target_hits_500": raw500_hits,
        "canonical_target_hits_25": canon25_hits,
        "canonical_target_hits_500": canon500_hits,
        "refine_target_failures": target_failures,
        "probes": probes,
        "classification": classification,
        "classification_evidence": evidence,
    }


QUESTIONS = {
    "q1_sentence_considered": "probes[].doc (sonda na sentenca dentro do doc do spaCy) e probes[].isolated",
    "q2_score_below_threshold": (
        "probes[].score/above_score_threshold — EVIDENCIA: extract_spacy nao filtra por "
        "score_candidate_sentence (so analyze_text usa SENTENCE_SCORE_THRESHOLD); nao causa o gap"
    ),
    "q3_max_triples_truncation": (
        "raw_target_hits_25 vs raw_target_hits_500 e canonical_target_hits_* "
        "(cap=500 e experimento em memoria, sem mudar codigo)"
    ),
    "q4_subject_entity": "probes[].doc.subject_term_ok/extracted_subject",
    "q5_object_entity": "probes[].doc.object_term_ok/extracted_object",
    "q6_any_triple_from_sentence": "probes[].doc.{root,nsubj,obj_dep} + isolated_spacy_target",
    "q7_predicate_captured": "probes[].doc.predicate (quando a sonda chega na construcao da tripla)",
    "q8_predicate_mapper_rejection": "refine_target_failures[].reason (classe predicate_unmapped)",
    "q9_span_validator_rejection": "refine_target_failures[].reason (classes object_rejected_by_span_validator / missing_*_entity)",
    "q10_duplicate_or_collapsed": "refine_target_failures[] classe duplicate_or_wrong_key",
    "q11_table_without_narrative": "target_sentences_count==0 caracteriza tabela/sem narrativa (casos aqui tem sentenca-alvo)",
    "q12_anaphora": "probes[].doc.class==anaphora_unresolved (sujeito/objeto pronominal ou generico no lugar do termo-alvo)",
    "q13_long_or_composed": "probes[].is_long/has_coordination + classe long_or_composed_sentence (objeto clausal)",
    "q14_date_or_list": "probes[].has_parenthetical + classe date_or_list_contamination (objeto date-like)",
}


async def fetch_all(urls: list[str], headers: dict) -> dict[str, dict]:
    limits = httpx.Limits(max_keepalive_connections=5, max_connections=8)
    async with httpx.AsyncClient(limits=limits, follow_redirects=True, verify=True) as client:
        fetched = await asyncio.gather(*[base.fetch_one(client, url, headers) for url in urls])
    return dict(zip(urls, fetched))


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnostico sentenca->triplo (#058.11, read-only).")
    parser.add_argument("--spec", required=True, help="JSON: {cases:[{case_id,fact_id,target_fact,url}]}")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    with open(args.spec, "r", encoding="utf-8") as fh:
        spec = json.load(fh)
    cases = spec.get("cases") or []

    miner = WebMiner()
    headers = miner.anti_block.generate_headers()
    extractor = EntityExtractor(enable_fallback=True)
    canonicalizer = SemanticCanonicalizer()

    urls = list(dict.fromkeys(case["url"] for case in cases))
    fetched = asyncio.run(fetch_all(urls, headers))
    fetch_cache = {}
    for url in urls:
        fetch_cache[url] = sweep.build_base(url, fetched[url], extractor)
        entry = fetch_cache[url]
        print(f"[fetch] status={entry['status']:3d} issue={entry['fetch_issue'] or '-'} | {url[:90]}")

    reports = [diagnose_case(case, extractor, canonicalizer, fetch_cache) for case in cases]
    by_class = Counter(r["classification"] for r in reports)
    by_fact: dict[str, Counter] = {}
    for report in reports:
        by_fact.setdefault(report["fact_id"], Counter())[report["classification"]] += 1

    document = {
        "audit_id": "extraction_gap_058_11",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "promote_automatically": False,
        "pipeline": {
            "fetch": "httpx + WebMiner.anti_block headers (paridade com minerador)",
            "prod_path": "extractor.extract(text, max_triples=25) + refine_triple_ex",
            "truncation_experiment": "extractor.extract(text, max_triples=500) em memoria (codigo intocado)",
            "probe": (
                "espelho da arvore de decisao de extract_spacy (ROOT VERB/AUX, "
                "validate_predicate, nsubj, obj/attr/obl/xcomp, guards) no doc e isolado"
            ),
            "class_priority": CLASS_PRIORITY,
            "score_note": (
                "SENTENCE_SCORE_THRESHOLD (0.6) nao filtra a extracao — so alimenta "
                "analyze_text; registrado como evidencia em probes[].score"
            ),
        },
        "questions": QUESTIONS,
        "cases": reports,
        "summary": {
            "cases_total": len(reports),
            "by_class": dict(by_class.most_common()),
            "by_fact": {fact: dict(counter.most_common()) for fact, counter in by_fact.items()},
        },
        "truthfulness_note": {
            "read_only": True,
            "no_neo4j_no_qdrant_no_ingest": True,
            "extractor_code_untouched": True,
            "seed_clusters_yaml_untouched": True,
            "diagnosis_only_no_fix": True,
        },
    }

    text = json.dumps(document, ensure_ascii=False, indent=2)
    leaks = assert_no_secret_markers(text, CREDENTIAL_MARKERS)
    if leaks:
        raise SystemExit(f"[anti-leak] marcadores suspeitos no relatorio: {sorted(set(leaks))}")

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(text)

    for report in reports:
        print(
            f"[{report['classification']:32s}] sent_alvo={report['target_sentences_count']:2d} "
            f"raw25={report['raw25_count']:2d} raw500={report['raw500_count']:2d} "
            f"hits500={len(report['canonical_target_hits_500'])} | {report['case_id']}"
        )
        print(f"    evidencia: {report['classification_evidence'][:160]}")
    print(f"\n[classes] {dict(by_class.most_common())}")
    print(f"[salvo em] {args.out}")


if __name__ == "__main__":
    main()
