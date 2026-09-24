"""Nexus-Alpha — Forense de extração cross-lingual (#058.5, read-only).

Responde **em qual etapa** da cadeia fetch→clean→sentença→extração→span→
predicado→alias→persistência uma fonte (tipicamente EN) produz
``raw_triples`` estruturalmente pobre ou lixo.

Módulo puro: sem rede, sem Neo4j/Qdrant, sem ``/api/ingest``, sem LLM,
sem embedding promotor. Classificação determinística a partir de contadores
já observados.

Diagnóstico válido: qualquer valor de ``DIAGNOSIS_STAGES`` **exceto**
``unknown`` — se só ``unknown`` sobrar, o issue não está concluído.
"""
from __future__ import annotations

import collections
import re
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

# Ordem causal (mais cedo na cadeia → mais provável ser a causa raiz).
DIAGNOSIS_STAGES: tuple[str, ...] = (
    "fetch",
    "cleaning",
    "sentence_selection",
    "extraction",
    "span_validation",
    "predicate_mapping",
    "entity_aliasing",
    "persistence",
    "unknown",
)

# Hints de issue seguinte (mesma matriz do #058.3 + #058.5).
NEXT_STAGE_ISSUES: dict[str, str] = {
    "fetch": "#048.3",
    "cleaning": "#058.6",
    "sentence_selection": "#058.7",
    "extraction": "#058.8",
    "span_validation": "#058.9",
    "predicate_mapping": "#045.3",
    "entity_aliasing": "#047.2",
    "persistence": "#055/#048.2/#065",
    "unknown": "#058.5",
}

# Marcadores típicos da página 404 do MediaWiki (não é artigo).
WIKIPEDIA_404_MARKERS: tuple[str, ...] = (
    "if the page has been deleted",
    "check the deletion log",
    "consider adding a redirect here",
    "why was the page i created deleted",
)

# Motivos de rejeição de span (prefix subject_/object_).
_SPAN_REASONS = frozenset({
    "missing_entity",
    "subject_generic_phrase",
    "subject_clause_fragment",
    "subject_starts_with_stopword",
    "subject_quantifier_phrase",
    "subject_date_like",
    "subject_pronoun",
    "subject_too_long",
    "subject_punctuated",
    "object_generic_phrase",
    "object_clause_fragment",
    "object_prepositional_phrase",
    "object_adverbial_phrase",
    "object_pronoun",
    "object_date_like",
    "object_punctuated",
    "object_too_long",
    "object_numeric_only",
    "object_quantifier_phrase",
})

# Motivos de predicado (validate_predicate / refine_triple_ex).
_PREDICATE_REASONS = frozenset({
    "unmapped_predicate",
    "invalid_predicate",
    "modal_predicate",
    "ambiguous_predicate",
    "stopword_predicate",
    "nonverbal_predicate",
    "numeric_predicate",
    "url_or_code_predicate",
})

# Sinais de texto limpo “curto demais” para uma página de artigo.
MIN_ARTICLE_CLEANED_LEN = 500
# Se raw_triples > 0 mas todos vieram de página de erro 404 → fetch.
ERROR_PAGE_RAW_TRIPLES_MAX = 3


def looks_like_wikipedia_404(text: str) -> bool:
    """True se o texto limpo contém marcadores da página 404 do MediaWiki."""
    low = (text or "").lower()
    if not low:
        return False
    hits = sum(1 for marker in WIKIPEDIA_404_MARKERS if marker in low)
    return hits >= 2


def classify_diagnosis(source: dict[str, Any]) -> dict[str, Any]:
    """Classifica a causa raiz da cadeia de extração de uma fonte.

    Entrada esperada (contadores de uma fonte PT ou EN):
      - ``fetch_status``: HTTP status (0 = falha de rede)
      - ``final_url`` / ``url``
      - ``cleaned_text_length``
      - ``sentences_considered`` / ``sentences_scored_above_threshold``
      - ``raw_triples`` / ``canonical_triples``
      - ``rejected_reasons``: dict motivo→contagem (refine + extract guard)
      - ``text_sample`` (opcional): amostra do texto limpo p/ detecção 404
      - ``top_raw_subjects`` / ``top_raw_objects`` (opcional): spans dominantes
      - ``persisted_fact_hashes`` (opcional): fatos no grafo

    Retorna dict com ``diagnosis`` (uma de DIAGNOSIS_STAGES),
    ``next_issue_hint``, ``evidence`` (lista de strings) e
    ``secondary_candidates`` (estágios seguintes ainda plausíveis).
    """
    status = int(source.get("fetch_status") or 0)
    cleaned_len = int(source.get("cleaned_text_length") or 0)
    sentences = int(source.get("sentences_considered") or 0)
    scored = int(source.get("sentences_scored_above_threshold") or 0)
    raw = int(source.get("raw_triples") or 0)
    canonical = int(source.get("canonical_triples") or 0)
    reasons = dict(source.get("rejected_reasons") or {})
    text_sample = str(source.get("text_sample") or "")
    top_subjects = [str(s) for s in (source.get("top_raw_subjects") or [])]
    # None = grafo não consultado (forense default); list = checado.
    persisted_raw = source.get("persisted_fact_hashes")
    graph_checked = persisted_raw is not None
    persisted = list(persisted_raw or [])

    evidence: list[str] = []
    secondary: list[str] = []

    # --- fetch -----------------------------------------------------------
    if status == 0:
        evidence.append("fetch_status=0 (falha de rede/timeout)")
        return _result("fetch", evidence, secondary)
    if status >= 400:
        evidence.append(f"fetch_status={status} (HTTP não-2xx)")
        if looks_like_wikipedia_404(text_sample):
            evidence.append("texto contém marcadores de página 404 do MediaWiki")
            secondary.append("cleaning")
        return _result("fetch", evidence, secondary)

    # HTTP 200 mas corpo é página de erro (raro, redirects internos).
    if looks_like_wikipedia_404(text_sample):
        evidence.append("HTTP 200 com marcadores de página 404 no corpo")
        if raw <= ERROR_PAGE_RAW_TRIPLES_MAX:
            evidence.append(
                f"raw_triples={raw} consistente com página de erro (≤{ERROR_PAGE_RAW_TRIPLES_MAX})"
            )
        return _result("fetch", evidence, secondary)

    # --- cleaning --------------------------------------------------------
    if cleaned_len < MIN_ARTICLE_CLEANED_LEN:
        evidence.append(
            f"cleaned_text_length={cleaned_len} < {MIN_ARTICLE_CLEANED_LEN}"
        )
        if status == 200:
            secondary.append("extraction")
        return _result("cleaning", evidence, secondary)

    # --- sentence_selection ---------------------------------------------
    # Só culpamos sentença se há texto suficiente E extração não rodou.
    if sentences > 0 and scored == 0 and raw == 0:
        evidence.append(
            f"sentences_considered={sentences} mas sentences_above_threshold=0 e raw_triples=0"
        )
        return _result("sentence_selection", evidence, secondary)

    # --- extraction ------------------------------------------------------
    if raw == 0:
        evidence.append(
            f"texto limpo ok (len={cleaned_len}, sentences={sentences}) mas raw_triples=0"
        )
        if sentences > 0:
            secondary.append("sentence_selection")
        return _result("extraction", evidence, secondary)

    # --- span_validation / predicate_mapping / entity_aliasing ----------
    span_hits = sum(int(v) for k, v in reasons.items() if k in _SPAN_REASONS)
    pred_hits = sum(int(v) for k, v in reasons.items() if k in _PREDICATE_REASONS)
    missing_entity = int(reasons.get("missing_entity") or 0)
    total_rejected = sum(int(v) for v in reasons.values())

    if canonical == 0 and total_rejected > 0:
        # Todos os raw foram rejeitados — achar o motivo dominante.
        ranked = sorted(reasons.items(), key=lambda kv: (-int(kv[1]), kv[0]))
        top_reason, top_count = ranked[0]
        evidence.append(
            f"raw_triples={raw} mas canonical_triples=0; "
            f"motivo dominante={top_reason} ({top_count})"
        )
        # missing_entity = falha no dicionário canônico/alias (antes de span).
        if top_reason == "missing_entity":
            secondary.extend(["span_validation", "extraction"])
            return _result("entity_aliasing", evidence, secondary)
        if top_reason in _SPAN_REASONS:
            secondary.extend(["predicate_mapping", "entity_aliasing"])
            return _result("span_validation", evidence, secondary)
        if top_reason in _PREDICATE_REASONS:
            secondary.extend(["span_validation", "entity_aliasing"])
            return _result("predicate_mapping", evidence, secondary)
        secondary.append("span_validation")
        return _result("extraction", evidence, secondary)

    if canonical == 0 and raw > 0:
        evidence.append(f"raw_triples={raw} mas canonical_triples=0 sem motivos registrados")
        return _result("extraction", evidence, secondary)

    # --- entity divergence residual (spans genéricos viraram canônicos) ---
    # Sujeitos genéricos dominantes com canonical > 0 → span_validator
    # deixou passar; ainda é "span_validation" como causa estrutural.
    generic_subject_hits = sum(
        1 for s in top_subjects if _is_generic_subject(s)
    )
    if generic_subject_hits >= max(1, len(top_subjects) // 2) and top_subjects:
        evidence.append(
            f"sujeitos genéricos dominam top_raw_subjects: {top_subjects[:3]}"
        )
        secondary.append("entity_aliasing")
        return _result("span_validation", evidence, secondary)

    # --- persistence -----------------------------------------------------
    # Só se o grafo foi efetivamente consultado (persisted não-None).
    if canonical > 0 and graph_checked and not persisted:
        evidence.append(
            f"canonical_triples={canonical} mas persisted_fact_hashes vazio "
            f"(grafo checado)"
        )
        return _result("persistence", evidence, secondary)

    # Fonte saudável: não é caso para forense de falha.
    evidence.append(
        f"cadeia saudavel ate aqui: status={status}, cleaned={cleaned_len}, "
        f"raw={raw}, canonical={canonical}"
        + (f", persisted={len(persisted)}" if graph_checked else ", grafo nao checado")
    )
    return _result("unknown", evidence, secondary)


_GENERIC_SUBJECT_RE = re.compile(
    r"^(?:the|a|an|this|that|these|those|o|a|os|as|um|uma|este|esta|esse|essa)\s+"
    r"(?:club|team|side|squad|staff|page|article|group|association|federation|"
    r"clube|equipe|time|pagina|artigo|grupo|associacao|federacao|"
    r"brazilian|brasileiro|professional|profissional|football|futebol|"
    r"sports|esportivo|esportiva)\b",
    re.IGNORECASE,
)


def _is_generic_subject(span: str) -> bool:
    text = (span or "").strip()
    if not text:
        return True
    if len(text.split()) > 6:
        return True
    return bool(_GENERIC_SUBJECT_RE.match(text))


def _result(
    diagnosis: str,
    evidence: list[str],
    secondary: list[str],
) -> dict[str, Any]:
    ordered_secondary = [s for s in DIAGNOSIS_STAGES if s in secondary and s != diagnosis]
    return {
        "diagnosis": diagnosis,
        "next_issue_hint": NEXT_STAGE_ISSUES.get(diagnosis, "#058.5"),
        "evidence": evidence,
        "secondary_candidates": ordered_secondary,
        "is_unknown": diagnosis == "unknown",
    }


def build_source_forensics(
    *,
    url: str,
    fetch_status: int,
    final_url: str = "",
    content_length: int = 0,
    cleaned_text_length: int = 0,
    sentences_considered: int = 0,
    sentences_scored_above_threshold: int = 0,
    raw_triples: int = 0,
    canonical_triples: int = 0,
    rejected_reasons: Optional[dict[str, int]] = None,
    top_raw_subjects: Optional[Iterable[str]] = None,
    top_raw_objects: Optional[Iterable[str]] = None,
    top_raw_predicates: Optional[Iterable[str]] = None,
    top_rejected_predicates: Optional[Iterable[str]] = None,
    persisted_fact_hashes: Optional[Iterable[str]] = None,
    graph_checked: bool = False,
    fallback_used: bool = False,
    fallback_type: str = "",
    masked_extraction_failure: bool = False,
    text_sample: str = "",
    ingested: bool = False,
) -> dict[str, Any]:
    """Monta o registro forense de uma única fonte (PT ou EN)."""
    reasons = dict(rejected_reasons or {})
    sample = text_sample or ""
    # Grafo checado só se houver lista explícita (inclusive vazia) e flag.
    if graph_checked and persisted_fact_hashes is None:
        persisted_for_diag: Optional[list[str]] = []
    elif not graph_checked:
        persisted_for_diag = None
    else:
        persisted_for_diag = list(persisted_fact_hashes or [])
    diagnosis = classify_diagnosis({
        "fetch_status": fetch_status,
        "cleaned_text_length": cleaned_text_length,
        "sentences_considered": sentences_considered,
        "sentences_scored_above_threshold": sentences_scored_above_threshold,
        "raw_triples": raw_triples,
        "canonical_triples": canonical_triples,
        "rejected_reasons": reasons,
        "text_sample": sample,
        "top_raw_subjects": list(top_raw_subjects or []),
        "persisted_fact_hashes": persisted_for_diag,
    })
    rejection_reasons = dict(sorted(reasons.items(), key=lambda kv: (-int(kv[1]), kv[0])))
    return {
        "url": url,
        "final_url": final_url or url,
        "fetch_status": int(fetch_status),
        "content_length": int(content_length),
        "cleaned_text_length": int(cleaned_text_length),
        "sentences_considered": int(sentences_considered),
        "sentences_above_threshold": int(sentences_scored_above_threshold),
        "raw_triples": int(raw_triples),
        "canonical_triples": int(canonical_triples),
        "rejected_noise": sum(int(v) for v in reasons.values()),
        "rejection_reasons": rejection_reasons,
        "top_raw_subjects": list(top_raw_subjects or []),
        "top_raw_objects": list(top_raw_objects or []),
        "top_raw_predicates": list(top_raw_predicates or []),
        "top_rejected_predicates": list(top_rejected_predicates or []),
        "fallback_used": bool(fallback_used),
        "fallback_type": fallback_type or ("demo-memory" if fallback_used else ""),
        "masked_extraction_failure": bool(masked_extraction_failure),
        "ingested": bool(ingested),
        "graph_checked": bool(graph_checked),
        "persisted_fact_hashes": list(persisted_fact_hashes or []) if graph_checked else [],
        "looks_like_wikipedia_404": looks_like_wikipedia_404(sample),
        "diagnosis": diagnosis["diagnosis"],
        "next_issue_hint": diagnosis["next_issue_hint"],
        "diagnosis_evidence": diagnosis["evidence"],
        "diagnosis_secondary": diagnosis["diagnosis_secondary"] if "diagnosis_secondary" in diagnosis else diagnosis.get("secondary_candidates", []),
    }


def build_comparison(pt: dict[str, Any], en: dict[str, Any]) -> dict[str, Any]:
    """Compara PT vs EN e devolve status de colisão + candidatos de causa."""
    pt_raw = int(pt.get("raw_triples") or 0)
    en_raw = int(en.get("raw_triples") or 0)
    pt_can = int(pt.get("canonical_triples") or 0)
    en_can = int(en.get("canonical_triples") or 0)
    en_diag = str(en.get("diagnosis") or "unknown")
    pt_diag = str(pt.get("diagnosis") or "unknown")

    if en_can == 0 and en_diag == "fetch":
        collision = "en_fetch_failed"
        root = ["fetch"]
    elif en_can == 0 and pt_can > 0:
        collision = "no_en_canonical_triples"
        root = [en_diag] if en_diag != "unknown" else ["unknown"]
    elif pt_can == 0 and en_can > 0:
        collision = "no_pt_canonical_triples"
        root = [pt_diag] if pt_diag != "unknown" else ["unknown"]
    elif pt_can == 0 and en_can == 0:
        collision = "no_canonical_triples_either_side"
        root = [en_diag if en_diag != "unknown" else pt_diag]
    else:
        # Ambos com canônicas — hash overlap ou divergência estrutural.
        pt_hashes = set(pt.get("persisted_fact_hashes") or [])
        # Para forense usamos fact hashes derivados das canonical se disponíveis.
        # Aqui comparamos contagens e diagnóstico residual.
        if en_raw <= ERROR_PAGE_RAW_TRIPLES_MAX and en.get("looks_like_wikipedia_404"):
            collision = "en_fetch_failed"
            root = ["fetch"]
        else:
            collision = "both_extracted"
            root = [en_diag] if en_diag != "unknown" else ["unknown"]

    # Dedup preservando ordem causal.
    ordered = [s for s in DIAGNOSIS_STAGES if s in set(root)]
    hints = list(dict.fromkeys(
        NEXT_STAGE_ISSUES.get(s, "#058.5") for s in ordered if s != "unknown"
    ))
    return {
        "pt_raw_triples": pt_raw,
        "en_raw_triples": en_raw,
        "pt_canonical_triples": pt_can,
        "en_canonical_triples": en_can,
        "collision_status": collision,
        "root_cause_candidates": ordered,
        "next_issue_hints": hints,
        "en_diagnosis": en_diag,
        "pt_diagnosis": pt_diag,
    }


def build_forensics_report(
    *,
    target: str,
    sources: list[dict[str, Any]],
    comparison: dict[str, Any],
    hypotheses: Optional[list[dict[str, Any]]] = None,
    audit_id: str = "",
    generated_at: Optional[str] = None,
    quorum: int = 3,
) -> dict[str, Any]:
    """Relatório consolidado do forense #058.5."""
    ts = generated_at or datetime.now(timezone.utc).isoformat()
    primary = comparison.get("root_cause_candidates") or ["unknown"]
    return {
        "audit_id": audit_id or f"botafogo_en_extraction_forensics_{datetime.now(timezone.utc):%Y-%m-%d}",
        "generated_at": ts,
        "target": target,
        "quorum": quorum,
        "sources": sources,
        "comparison": comparison,
        "hypotheses": hypotheses or [],
        "diagnosis_summary": {
            "primary_diagnosis": primary[0] if primary else "unknown",
            "next_issue_hint": (
                NEXT_STAGE_ISSUES.get(primary[0], "#058.5")
                if primary and primary[0] != "unknown"
                else "#058.5"
            ),
            "is_unknown": primary == ["unknown"] or not primary,
        },
        "truthfulness_note": (
            "Read-only extraction forensics. Does not promote facts, does not "
            "change quorum/confirmacoes, does not write Neo4j/Qdrant, does not "
            "call /api/ingest. Diagnosis is diagnostic only."
        ),
    }


# Hypotheses H1–H7 da proposta do issue (matriz de decisão).
def evaluate_hypotheses(
    pt: dict[str, Any],
    en: dict[str, Any],
) -> list[dict[str, Any]]:
    """Avalia H1–H7 com base nos contadores das duas fontes."""
    en_diag = str(en.get("diagnosis") or "unknown")
    en_status = int(en.get("fetch_status") or 0)
    en_cleaned = int(en.get("cleaned_text_length") or 0)
    en_raw = int(en.get("raw_triples") or 0)
    en_can = int(en.get("canonical_triples") or 0)
    en_404 = bool(en.get("looks_like_wikipedia_404"))
    en_reasons = dict(en.get("rejected_reasons") or {})
    span_hits = sum(int(v) for k, v in en_reasons.items() if k in _SPAN_REASONS)
    pred_hits = sum(int(v) for k, v in en_reasons.items() if k in _PREDICATE_REASONS)
    missing = int(en_reasons.get("missing_entity") or 0)

    rows: list[dict[str, Any]] = [
        {
            "id": "H1",
            "title": "Pagina EN improdutiva (URL/404/fonte)",
            "supported": en_status >= 400 or en_404 or (
                en_status == 200 and en_cleaned < MIN_ARTICLE_CLEANED_LEN
            ),
            "signals": {
                "fetch_status": en_status,
                "looks_like_404": en_404,
                "cleaned_text_length": en_cleaned,
            },
            "next_issue": "#048.3" if (en_status >= 400 or en_404) else "",
            "reading": (
                "URL seed EN improdutiva/404 — problema de fonte, não de alias."
                if (en_status >= 400 or en_404)
                else "Sem evidencia de 404/URL morta."
            ),
        },
        {
            "id": "H2",
            "title": "Limpeza HTML agressiva demais",
            "supported": (
                en_status == 200
                and not en_404
                and en_cleaned < MIN_ARTICLE_CLEANED_LEN
                and int(en.get("content_length") or 0) > 5000
            ),
            "signals": {
                "content_length": en.get("content_length"),
                "cleaned_text_length": en_cleaned,
            },
            "next_issue": "#058.6",
            "reading": "",
        },
        {
            "id": "H3",
            "title": "Sentence scoring enviesado (PT vs EN)",
            "supported": (
                en_status == 200
                and not en_404
                and en_cleaned >= MIN_ARTICLE_CLEANED_LEN
                and int(en.get("sentences_considered") or 0) > 0
                and int(en.get("sentences_above_threshold") or 0) == 0
                and en_raw == 0
            ),
            "signals": {
                "sentences_considered": en.get("sentences_considered"),
                "sentences_above_threshold": en.get("sentences_above_threshold"),
            },
            "next_issue": "#058.7",
            "reading": "",
        },
        {
            "id": "H4",
            "title": "Extractor nao entende sintaxe EN",
            "supported": en_diag == "extraction",
            "signals": {
                "raw_triples": en_raw,
                "cleaned_text_length": en_cleaned,
                "diagnosis": en_diag,
            },
            "next_issue": "#058.8",
            "reading": "",
        },
        {
            "id": "H5",
            "title": "Span validator aceita sujeitos genericos",
            "supported": (
                en_can > 0
                and any(_is_generic_subject(s) for s in (en.get("top_raw_subjects") or []))
            )
            or (en_diag == "span_validation" and span_hits > 0),
            "signals": {
                "top_raw_subjects": en.get("top_raw_subjects"),
                "span_rejection_hits": span_hits,
                "diagnosis": en_diag,
            },
            "next_issue": "#058.9",
            "reading": (
                "Sujeitos genericos poluem o grafo e matam corroboracao."
                if en_can > 0
                else "Span rejects dominam — validador rejeitando em vez de aceitar lixo."
            ),
        },
        {
            "id": "H6",
            "title": "Predicate mapper sem cobertura EN basica",
            "supported": pred_hits > 0 and en_diag == "predicate_mapping",
            "signals": {
                "predicate_rejection_hits": pred_hits,
                "rejection_reasons": en_reasons,
            },
            "next_issue": "#045.3",
            "reading": "",
        },
        {
            "id": "H7",
            "title": "Alias ainda falta (apos H1–H6 resolvidos)",
            "supported": (
                en_can > 0
                and en_diag not in ("fetch", "cleaning", "extraction", "span_validation", "predicate_mapping")
                and missing > 0
            ),
            "signals": {"missing_entity": missing, "diagnosis": en_diag},
            "next_issue": "#047.2",
            "reading": "",
        },
    ]
    return rows
