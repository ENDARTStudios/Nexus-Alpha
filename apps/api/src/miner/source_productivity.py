"""Nexus-Alpha — Produtividade de extração por fonte (#058, read-only).

Transforma "a página retornou 200 mas ``entities_processed: 0``" em evidência
auditável: sentenças consideradas, triplas cruas, triplas canônicas, motivos de
rejeição e classificação ``productive | weak | unproductive``.

Regra de ouro: módulo **puro** — não grava em Neo4j/Qdrant, não chama
``/api/ingest``, não promove fato, não altera quórum. Só conta e classifica.
"""
from __future__ import annotations

import collections
import re
from typing import Any, Optional

from ..cognition.canonicalizer import SemanticCanonicalizer
from ..cognition.extractor import EntityExtractor, classify_sentence_candidate
from ..cognition.span_validator import fold_span
from ..cognition.triple_refiner import refine_triple_ex, score_candidate_sentence

MIN_CLEANED_TEXT = 500
MIN_PRODUCTIVE_TRIPLES = 3
SENTENCE_SCORE_THRESHOLD = 0.6
NAVIGATION_NOISE_SHARE = 0.7
TOP_N = 5

NAVIGATION_NOISE_REASONS = frozenset({
    "object_date_like",
    "object_prepositional_phrase",
    "object_adverbial_phrase",
    "object_pronoun",
    "object_clause_fragment",
    "object_punctuated",
    "subject_generic_phrase",
    "subject_clause_fragment",
    "subject_starts_with_stopword",
})

FOOTBALL_TERMS = frozenset({
    "santos", "pele", "garrincha", "botafogo", "vila belmiro", "caldeira",
    "estadio", "torcida", "torcedor", "futebol", "campeonato", "libertadores",
    "brasileirao", "jogador", "tecnico", "partida", "clube", "equipe",
    "stadium", "football", "striker",
})

FOOTBALL_VERBS = frozenset({
    "defendeu", "defender", "jogou", "jogar", "disputou", "disputar",
    "venceu", "vencer", "contratou", "contratar", "conquistou", "conquistar",
    "representou", "representar", "atuou", "atuar", "liderou", "liderar",
    "played", "scored", "won", "joined", "captained",
})

_WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)

_EXTRACTOR: Optional[EntityExtractor] = None
_CANONICALIZER: Optional[SemanticCanonicalizer] = None


def _default_extractor() -> EntityExtractor:
    global _EXTRACTOR
    if _EXTRACTOR is None:
        _EXTRACTOR = EntityExtractor(enable_fallback=True)
    return _EXTRACTOR


def _default_canonicalizer() -> SemanticCanonicalizer:
    global _CANONICALIZER
    if _CANONICALIZER is None:
        _CANONICALIZER = SemanticCanonicalizer()
    return _CANONICALIZER


def split_sentences_with_stats(text: str) -> tuple[list[str], dict[str, int]]:
    """Frases por sentença (``.``, ``!``, ``?``) + contagem de rejeições F3.

    #058.11.1: candidatos não-proposicionais (títulos, refs, captions,
    linhas de tabela/infobox) são descartados antes de virar candidata —
    a contagem em ``pre_filter_rejections`` separa esses descartes dos
    descartes por score.
    """
    parts = re.split(r"(?<=[.!?])\s+", str(text or "").strip())
    kept: list[str] = []
    rejected: collections.Counter = collections.Counter(
        {"too_short": 0, "noise_marker": 0, "non_propositional_fragment": 0}
    )
    for part in parts:
        part = re.sub(r"\s+", " ", part).strip()
        if not part:
            continue
        reason = classify_sentence_candidate(part)
        if reason is None:
            kept.append(part)
        else:
            rejected[reason] += 1
    return kept, dict(sorted(rejected.items()))


def split_sentences(text: str) -> list[str]:
    """Frases por sentença (``.``, ``!``, ``?``), colapsadas e não vazias."""
    return split_sentences_with_stats(text)[0]


def detect_football_verbs(text: str) -> list[str]:
    """Verbos de futebol presentes no texto (evidência para o backlog #045.1)."""
    words = {fold_match for fold_match in (_fold(w) for w in _WORD_RE.findall(str(text or "")))}
    return sorted(words & FOOTBALL_VERBS)


def _fold(value: Any) -> str:
    return fold_span(str(value or ""))


def _is_football_triple(subject: Any, obj: Any) -> bool:
    haystack = f"{_fold(subject)} {_fold(obj)}"
    return any(term in haystack for term in FOOTBALL_TERMS)


def _navigation_dominated(report: dict[str, Any]) -> bool:
    rejected = int(report.get("rejected_noise", 0))
    if rejected <= 0:
        return False
    reasons = report.get("rejection_reasons") or {}
    noise = sum(int(reasons.get(reason, 0)) for reason in NAVIGATION_NOISE_REASONS)
    return (noise / rejected) >= NAVIGATION_NOISE_SHARE


def classify_extractive_quality(report: dict[str, Any], require_football: bool = True) -> str:
    """``productive | weak | unproductive`` — determinístico e documentado.

    - ``unproductive``: texto limpo curto ou zero tripla canônica;
    - ``weak``: 1..2 canônicas, rejeição dominada por ruído de navegação, ou
      (com ``require_football``) nenhuma tripla com entidade esportiva;
    - ``productive``: >= 3 canônicas, sem domínio de ruído e, se exigido,
      >= 1 tripla esportiva plausível.
    """
    if int(report.get("cleaned_text_length", 0)) < MIN_CLEANED_TEXT:
        return "unproductive"
    canonical = int(report.get("canonical_triples", 0))
    if canonical == 0:
        return "unproductive"
    if canonical < MIN_PRODUCTIVE_TRIPLES:
        return "weak"
    if _navigation_dominated(report):
        return "weak"
    if require_football and int(report.get("football_related_hits", 0)) < 1:
        return "weak"
    return "productive"


def _notes(report: dict[str, Any]) -> str:
    if int(report.get("status", 200) or 0) not in (200, 0):
        return f"fetch falhou (status {report.get('status')})"
    if int(report.get("cleaned_text_length", 0)) < MIN_CLEANED_TEXT:
        return "texto limpo insuficiente (provavel JS/listing/marketing)"
    if int(report.get("raw_triples", 0)) == 0:
        return "extrator nao produziu triplas (sem predicados detectados)"
    if int(report.get("canonical_triples", 0)) == 0:
        return "todas as triplas cruas rejeitadas no refino"
    if _navigation_dominated(report):
        return "rejeicoes dominadas por ruido de navegacao"
    return ""


def analyze_text(
    text: str,
    url: str = "",
    status: int = 200,
    content_length: int = 0,
    extractor: Optional[EntityExtractor] = None,
    canonicalizer: Optional[SemanticCanonicalizer] = None,
) -> dict[str, Any]:
    """Métricas de produtividade de ``text`` — sem escrita de nenhum tipo."""
    extractor = extractor or _default_extractor()
    canonicalizer = canonicalizer or _default_canonicalizer()

    sentences, pre_filter_rejections = split_sentences_with_stats(text)
    scored = [
        sentence for sentence in sentences
        if score_candidate_sentence(sentence, canonicalizer) >= SENTENCE_SCORE_THRESHOLD
    ]

    guard_before = collections.Counter(extractor.rejection_reasons)
    raw_triples = extractor.extract(text)
    guard_delta = collections.Counter(extractor.rejection_reasons) - guard_before

    reasons: collections.Counter = collections.Counter(guard_delta)
    subjects: collections.Counter = collections.Counter()
    objects: collections.Counter = collections.Counter()
    predicates: collections.Counter = collections.Counter()
    canonical = 0
    rejected = 0
    football_hits = 0

    for triple in raw_triples:
        raw = triple.to_dict()
        refined, reason = refine_triple_ex(raw, canonicalizer)
        if refined is None:
            rejected += 1
            reasons[reason] += 1
            continue
        canonical += 1
        subjects[refined["subject"]] += 1
        predicates[refined["predicate"]] += 1
        objects[refined["object"]] += 1
        if _is_football_triple(raw.get("subject"), raw.get("object")):
            football_hits += 1

    report: dict[str, Any] = {
        "url": url,
        "status": status,
        "content_length": content_length,
        "cleaned_text_length": len(text or ""),
        "sentences_considered": len(sentences),
        "sentences_scored_above_threshold": len(scored),
        "pre_filter_rejections": pre_filter_rejections,
        "raw_triples": len(raw_triples),
        "canonical_triples": canonical,
        "rejected_noise": rejected,
        "rejection_reasons": dict(sorted(reasons.items(), key=lambda kv: (-kv[1], kv[0]))),
        "top_subjects": dict(subjects.most_common(TOP_N)),
        "top_objects": dict(objects.most_common(TOP_N)),
        "top_predicates": dict(predicates.most_common(TOP_N)),
        "football_related_hits": football_hits,
        "football_verb_hits": len(detect_football_verbs(text)),
        "detected_football_verbs": detect_football_verbs(text),
    }
    report["extractive_quality"] = classify_extractive_quality(report)
    report["notes"] = _notes(report)
    return report


def payload_telemetry(
    payload: dict[str, Any],
    extractor: Optional[EntityExtractor] = None,
    canonicalizer: Optional[SemanticCanonicalizer] = None,
) -> dict[str, Any]:
    """Contadores por payload para o worker — só log local, nunca público."""
    return analyze_text(
        payload.get("content") or "",
        url=str(payload.get("source_url") or ""),
        extractor=extractor,
        canonicalizer=canonicalizer,
    )


def summarize(reports: list[dict[str, Any]]) -> dict[str, Any]:
    """Agregação determinística do lote de URLs avaliadas."""
    quality: collections.Counter = collections.Counter()
    by_domain: collections.Counter = collections.Counter()
    reasons: collections.Counter = collections.Counter()
    for report in reports:
        quality[report.get("extractive_quality", "unproductive")] += 1
        host = str(report.get("url") or "").split("/")[2] if "://" in str(report.get("url") or "") else ""
        if host:
            by_domain[host[4:] if host.startswith("www.") else host] += 1
        for reason, count in (report.get("rejection_reasons") or {}).items():
            reasons[reason] += int(count)
    return {
        "urls_evaluated": len(reports),
        "quality": {
            "productive": int(quality.get("productive", 0)),
            "weak": int(quality.get("weak", 0)),
            "unproductive": int(quality.get("unproductive", 0)),
        },
        "productive_urls": [
            r["url"] for r in reports if r.get("extractive_quality") == "productive"
        ],
        "unproductive_urls": [
            r["url"] for r in reports if r.get("extractive_quality") == "unproductive"
        ],
        "urls_by_domain": dict(sorted(by_domain.items(), key=lambda kv: (-kv[1], kv[0]))),
        "rejection_reasons": dict(sorted(reasons.items(), key=lambda kv: (-kv[1], kv[0]))),
        "total_canonical_triples": sum(int(r.get("canonical_triples", 0)) for r in reports),
        "total_football_related_hits": sum(int(r.get("football_related_hits", 0)) for r in reports),
    }
