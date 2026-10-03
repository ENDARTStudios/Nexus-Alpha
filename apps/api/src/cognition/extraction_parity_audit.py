"""Nexus-Alpha — Paridade de extração PT/EN (#058.3, read-only).

Responde, por alvo de cluster, **onde** a cadeia PT/EN diverge antes de virar
``duplicate_cross_domain = 0``: fetch, extração, refino, alias, ou fallback
``demo-memory``.

Regra de ouro: similaridade/diagnóstico **não** verifica fato, **não** aumenta
quórum, **não** grava ``:Fato``, **não** altera ``confirmacoes``. Módulo puro,
sem Neo4j/Qdrant/embedding/LLM no caminho de teste.
"""
from __future__ import annotations

import collections
import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Iterable, Optional
from urllib.parse import urlparse

# Classificação de causa-raiz (matriz pós-#058.3).
ROOT_CAUSES: tuple[str, ...] = (
    "extraction_absence",
    "predicate_divergence",
    "entity_divergence",
    "span_rejection",
    "fallback_contamination",
    "true_content_difference",
)

NEXT_ISSUE_HINTS: dict[str, str] = {
    "extraction_absence": "#058.4",
    "span_rejection": "#058.4",
    "predicate_divergence": "#045.2",
    "entity_divergence": "#047.1",
    "fallback_contamination": "#063",
    "true_content_difference": "#055/#048.2/#065",
}

ROOT_CAUSE_PRIORITY: dict[str, str] = {
    "fallback_contamination": "high",
    "extraction_absence": "high",
    "span_rejection": "medium",
    "predicate_divergence": "medium",
    "entity_divergence": "medium",
    "true_content_difference": "low",
}

PRIORITY_ORDER: tuple[str, ...] = (
    "fallback_contamination",
    "extraction_absence",
    "span_rejection",
    "predicate_divergence",
    "entity_divergence",
    "true_content_difference",
)

_SPAN_REJECTION_REASONS = frozenset({
    "missing_entity",
    "subject_quantifier_phrase",
    "object_prepositional_phrase",
    "object_adverbial_phrase",
    "object_generic_phrase",
    "object_punctuated",
    "subject_generic_phrase",
    "subject_starts_with_stopword",
    "object_pronoun",
    "object_date_like",
    "object_clause_fragment",
    "subject_clause_fragment",
})


def fact_hash(subject: str, predicate: str, obj: str) -> str:
    """Hash estável da tripla (mesma forma do ``brain.memory.fact_hash``)."""
    raw = "|".join(part.strip() for part in (subject, predicate, obj)).lower()
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def domain_of(url: str) -> str:
    """Domínio normalizado (sem ``www.``) de uma URL."""
    host = urlparse(url or "").netloc.lower()
    return host[4:] if host.startswith("www.") else host


def fold_key(text: Any) -> str:
    """Fold simples para comparação de superfícies (sem acento/caixa)."""
    import unicodedata

    raw = unicodedata.normalize("NFKD", str(text or "").strip().lower())
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch))
    folded = re.sub(r"[^a-z0-9\s]+", " ", raw)
    return re.sub(r"\s+", " ", folded).strip()


def _norm_triplet(item: Any) -> dict[str, Any]:
    if hasattr(item, "to_dict"):
        item = item.to_dict()
    if not isinstance(item, dict):
        item = {
            "subject": str(getattr(item, "subject", "")),
            "predicate": str(getattr(item, "predicate", "")),
            "object": str(getattr(item, "object", "")),
        }
    subject = str(item.get("subject") or "")
    predicate = str(item.get("predicate") or "")
    obj = str(item.get("object") or "")
    domains = sorted({
        str(d).strip().lower() for d in (item.get("domains") or []) if str(d).strip()
    })
    if not domains and item.get("url"):
        domains = [domain_of(str(item.get("url")))]
    return {
        "subject": subject,
        "predicate": predicate,
        "object": obj,
        "fact_hash": str(item.get("fact_hash") or fact_hash(subject, predicate, obj)),
        "domains": domains,
        "url": str(item.get("url") or ""),
        "raw_subject": str(item.get("raw_subject") or subject),
        "raw_predicate": str(item.get("raw_predicate") or predicate),
        "raw_object": str(item.get("raw_object") or obj),
    }


def load_persisted_facts_by_domain(
    facts: Iterable[Any],
) -> dict[str, list[dict[str, Any]]]:
    """Agrupa fatos persistidos por domínio (``pt.wikipedia.org`` etc.)."""
    by_domain: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for item in facts:
        norm = _norm_triplet(item)
        domains = norm["domains"] or ["<unknown>"]
        for domain in domains:
            by_domain[domain].append(norm)
    return dict(by_domain)


def group_facts_by_target_alias(
    facts: Iterable[Any],
    aliases: dict[str, list[str]],
) -> dict[str, list[dict[str, Any]]]:
    """Agrupa fatos por alvo usando variantes curadas (fold em variante/canônico)."""
    lookup: dict[str, str] = {}
    for target, variants in (aliases or {}).items():
        lookup[fold_key(target)] = target
        for variant in variants or []:
            key = fold_key(variant)
            if key:
                lookup[key] = target

    grouped: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for item in facts:
        norm = _norm_triplet(item)
        haystack = " ".join([
            fold_key(norm["subject"]),
            fold_key(norm["object"]),
            fold_key(norm["raw_subject"]),
            fold_key(norm["raw_object"]),
        ])
        for key, target in lookup.items():
            if key and key in haystack:
                grouped[target].append(norm)
                break
    return dict(grouped)


def analyze_source_run(
    *,
    url: str,
    domain: str = "",
    fetch_status: int = 200,
    final_url: str = "",
    cleaned_text_length: int = 0,
    sentences_considered: int = 0,
    raw_triples: int = 0,
    canonical_triples: int = 0,
    rejected_reasons: Optional[dict[str, int]] = None,
    canonical_facts: Optional[list[Any]] = None,
    fallback_used: bool = False,
    fallback_type: str = "",
    fallback_written_to_graph: bool = False,
    entities_processed: Optional[int] = None,
    db_status: str = "",
    ingest_status: str = "",
) -> dict[str, Any]:
    """Normaliza o estado de uma fonte (PT ou EN) para comparação."""
    domain = (domain or domain_of(url)).lower()
    facts = [_norm_triplet(f) for f in (canonical_facts or [])]
    reasons = dict(rejected_reasons or {})
    span_rejections = sum(
        int(v) for k, v in reasons.items() if k in _SPAN_REJECTION_REASONS
    )
    return {
        "url": url,
        "final_url": final_url or url,
        "domain": domain,
        "language": "pt" if domain.startswith("pt.") else ("en" if domain.startswith("en.") else ""),
        "fetch_status": int(fetch_status or 0),
        "cleaned_text_length": int(cleaned_text_length or 0),
        "sentences_considered": int(sentences_considered or 0),
        "raw_triples": int(raw_triples or 0),
        "canonical_triples": int(canonical_triples if canonical_triples is not None else len(facts)),
        "rejected_reasons": reasons,
        "span_rejection_count": span_rejections,
        "canonical_facts": facts,
        "fact_hashes": sorted({f["fact_hash"] for f in facts if f.get("fact_hash")}),
        "fallback_used": bool(fallback_used),
        "fallback_type": fallback_type or ("demo-memory" if fallback_used else ""),
        "fallback_written_to_graph": bool(fallback_written_to_graph),
        "entities_processed": entities_processed,
        "db_status": db_status,
        "ingest_status": ingest_status,
    }


def _has_canonical(source: dict[str, Any]) -> bool:
    return int(source.get("canonical_triples") or 0) > 0 and bool(source.get("canonical_facts"))


def _predicates(source: dict[str, Any]) -> set[str]:
    return {fold_key(f.get("predicate")) for f in source.get("canonical_facts") or []}


def _entities(source: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for fact in source.get("canonical_facts") or []:
        out.add(fold_key(fact.get("subject")))
        out.add(fold_key(fact.get("object")))
    return {e for e in out if e}


def _exact_hash_overlap(pt: dict[str, Any], en: dict[str, Any]) -> set[str]:
    pt_hashes = set(pt.get("fact_hashes") or [])
    en_hashes = set(en.get("fact_hashes") or [])
    return pt_hashes & en_hashes


def classify_pair(pt: dict[str, Any], en: dict[str, Any]) -> dict[str, Any]:
    """Classifica o par PT/EN de uma fonte-alvo.

    Retorna ``collision_status``, ``root_cause_candidates`` e
    ``next_issue_hint`` ordenados por prioridade operacional.
    """
    pt_has = _has_canonical(pt)
    en_has = _has_canonical(en)
    pt_raw = int(pt.get("raw_triples") or 0)
    en_raw = int(en.get("raw_triples") or 0)
    causes: list[str] = []

    fallback_mask = bool(
        (en.get("fallback_used") or pt.get("fallback_used"))
        and (
            (en.get("fallback_used") and not en_has)
            or (pt.get("fallback_used") and not pt_has)
        )
    )
    fallback_graph = bool(
        en.get("fallback_written_to_graph") or pt.get("fallback_written_to_graph")
    )

    if fallback_graph:
        causes.append("fallback_contamination")
    elif fallback_mask:
        causes.append("extraction_absence")

    if not pt_has and not en_has:
        collision = "no_canonical_triples_either_side"
        if not causes:
            if pt_raw == 0 and en_raw == 0:
                causes.append("extraction_absence")
            else:
                causes.append("span_rejection")
                if int((pt.get("span_rejection_count") or 0)) or int(
                    (en.get("span_rejection_count") or 0)
                ):
                    pass
                else:
                    causes.append("extraction_absence")
    elif pt_has and not en_has:
        collision = "no_en_canonical_triples"
        if "extraction_absence" not in causes:
            causes.append("extraction_absence")
        if int(en.get("span_rejection_count") or 0) > 0 and en_raw > 0:
            causes.append("span_rejection")
    elif en_has and not pt_has:
        collision = "no_pt_canonical_triples"
        causes.append("extraction_absence")
        if int(pt.get("span_rejection_count") or 0) > 0 and pt_raw > 0:
            causes.append("span_rejection")
    else:
        overlap = _exact_hash_overlap(pt, en)
        if overlap:
            collision = "exact_collision"
        else:
            pt_preds, en_preds = _predicates(pt), _predicates(en)
            pt_ents, en_ents = _entities(pt), _entities(en)
            shared_pred = pt_preds & en_preds
            shared_ent = pt_ents & en_ents
            # Predicados dominantes divergem (interseção menor que o lado PT)
            # com entidades compartilhadas → predicado é o gap.
            if shared_ent and not shared_pred:
                collision = "predicate_divergence"
                causes.append("predicate_divergence")
            elif shared_pred and not shared_ent:
                collision = "entity_divergence"
                causes.append("entity_divergence")
            elif shared_ent and shared_pred and shared_pred != pt_preds:
                # Há predicado em comum, mas o set PT tem predicados sem par EN.
                collision = "predicate_divergence"
                causes.append("predicate_divergence")
            elif shared_ent and shared_pred:
                collision = "near_collision_structural"
                causes.append("entity_divergence")
            else:
                collision = "no_shared_surface"
                causes.append("true_content_difference")
            if not causes:
                causes.append("true_content_difference")

    # Dedup preservando ordem PRIORITY_ORDER quando possível.
    unique = list(dict.fromkeys(causes))
    ordered = [c for c in PRIORITY_ORDER if c in unique]
    ordered += [c for c in unique if c not in ordered]
    hints = list(dict.fromkeys(NEXT_ISSUE_HINTS.get(c, "") for c in ordered if NEXT_ISSUE_HINTS.get(c)))

    return {
        "collision_status": collision,
        "root_cause_candidates": ordered,
        "next_issue_hint": hints[0] if hints else "",
        "priority": ROOT_CAUSE_PRIORITY.get(ordered[0], "medium") if ordered else "medium",
        "exact_fact_hash_overlap": sorted(overlap := _exact_hash_overlap(pt, en)),
        "shared_predicates": sorted(_predicates(pt) & _predicates(en)),
        "shared_entities": sorted(_entities(pt) & _entities(en)),
        "pt_canonical": pt.get("canonical_triples") or 0,
        "en_canonical": en.get("canonical_triples") or 0,
        "pt_raw": pt_raw,
        "en_raw": en_raw,
        "fallback_used": bool(pt.get("fallback_used") or en.get("fallback_used")),
        "fallback_written_to_graph": fallback_graph,
    }


def parse_worker_ingest_log(text: str) -> dict[str, dict[str, Any]]:
    """Extrai por URL: telemetria + resposta de ingest do log do worker.

    Detecta ``partial_success`` / ``db_status=demo-memory`` sem gravar nada.
    """
    out: dict[str, dict[str, Any]] = {}
    # Formato: Resposta [url]: CODE <separador> {...json...}
    # O separador pode ser em-dash, hyphen ou mojibake de encoding do log GH.
    for match in re.finditer(
        r"Resposta \[(?P<url>[^\]]+)\]: (?P<code>\d+)\s*(?:[^\s{]\s*)*(?P<body>\{.*?\})(?=\s*(?:\n|$))",
        text or "",
        flags=re.DOTALL,
    ):
        url = match.group("url").strip()
        code = int(match.group("code"))
        body_raw = match.group("body")
        entry = out.setdefault(
            url,
            {
                "url": url,
                "domain": domain_of(url),
                "fetch_status": code,
                "ingest_status": "",
                "db_status": "",
                "entities_processed": None,
                "fallback_used": False,
                "fallback_type": "",
                "fallback_written_to_graph": False,
                "quality": "",
                "raw_triples": None,
                "canonical_triples": None,
                "notes": "",
                "masked_extraction_failure": False,
            },
        )
        entry["fetch_status"] = code
        try:
            import json

            body = json.loads(body_raw)
        except Exception:
            body = {}
        entry["ingest_status"] = str(body.get("status") or "")
        entry["db_status"] = str(body.get("db_status") or "")
        if body.get("entities_processed") is not None:
            entry["entities_processed"] = int(body.get("entities_processed") or 0)
        if body.get("masked_extraction_failure") is not None:
            entry["masked_extraction_failure"] = bool(body.get("masked_extraction_failure"))
        fallback_statuses = {"partial_success", "degraded", "failed"}
        if (
            entry["db_status"] == "demo-memory"
            or entry["ingest_status"] in fallback_statuses
            or entry.get("masked_extraction_failure")
        ):
            entry["fallback_used"] = True
            entry["fallback_type"] = "demo-memory"
            # Escrita no grafo exige refined entities + cluster-active.
            entry["fallback_written_to_graph"] = bool(
                entry["db_status"] == "cluster-active"
                and (entry["entities_processed"] or 0) > 0
            )

    for match in re.finditer(
        r"telemetria\s+(?P<body>\{.*?\})(?=\s*(?:\n|$))",
        text or "",
        flags=re.DOTALL,
    ):
        try:
            import json

            body = json.loads(match.group("body"))
        except Exception:
            continue
        url = str(body.get("url") or "")
        if not url:
            continue
        entry = out.setdefault(
            url,
            {
                "url": url,
                "domain": domain_of(url),
                "fetch_status": 0,
                "ingest_status": "",
                "db_status": "",
                "entities_processed": None,
                "fallback_used": False,
                "fallback_type": "",
                "fallback_written_to_graph": False,
                "quality": "",
                "raw_triples": None,
                "canonical_triples": None,
                "notes": "",
                "masked_extraction_failure": False,
            },
        )
        entry["quality"] = str(body.get("quality") or "")
        entry["raw_triples"] = body.get("raw_triples")
        entry["canonical_triples"] = body.get("canonical_triples")
        entry["notes"] = str(body.get("notes") or "")

    return out


def build_target_report(
    *,
    target: str,
    canonical_entity: str = "",
    pt_source: Optional[dict[str, Any]] = None,
    en_source: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Monta a entrada de um alvo no relatório de paridade."""
    pt = pt_source or analyze_source_run(url="", domain="pt.wikipedia.org", fetch_status=0)
    en = en_source or analyze_source_run(url="", domain="en.wikipedia.org", fetch_status=0)
    classification = classify_pair(pt, en)
    return {
        "target": target,
        "canonical_entity": canonical_entity,
        "sources": [pt, en],
        "collision_status": classification["collision_status"],
        "root_cause_candidates": classification["root_cause_candidates"],
        "next_issue_hint": classification["next_issue_hint"],
        "priority": classification["priority"],
        "diagnostics": {
            "exact_fact_hash_overlap": classification["exact_fact_hash_overlap"],
            "shared_predicates": classification["shared_predicates"],
            "shared_entities": classification["shared_entities"],
            "pt_canonical": classification["pt_canonical"],
            "en_canonical": classification["en_canonical"],
            "pt_raw": classification["pt_raw"],
            "en_raw": classification["en_raw"],
            "fallback_used": classification["fallback_used"],
            "fallback_written_to_graph": classification["fallback_written_to_graph"],
        },
    }


def build_parity_report(
    targets: list[dict[str, Any]],
    *,
    build_space_commit: str = "",
    worker_run_id: str = "",
    quorum: int = 3,
    generated_at: Optional[str] = None,
) -> dict[str, Any]:
    """Relatório consolidado de paridade (#058.3)."""
    rows = [build_target_report(**t) for t in targets]
    summary = {
        "targets_total": len(rows),
        "targets_with_pt_canonical": sum(
            1 for r in rows if any(
                s["domain"].startswith("pt.") and int(s.get("canonical_triples") or 0) > 0
                for s in r["sources"]
            )
        ),
        "targets_with_en_canonical": sum(
            1 for r in rows if any(
                s["domain"].startswith("en.") and int(s.get("canonical_triples") or 0) > 0
                for s in r["sources"]
            )
        ),
        "targets_with_both_canonical": sum(
            1 for r in rows
            if r["diagnostics"]["pt_canonical"] > 0 and r["diagnostics"]["en_canonical"] > 0
        ),
        "targets_with_exact_collision": sum(
            1 for r in rows if r["collision_status"] == "exact_collision"
        ),
        "targets_with_near_collision": sum(
            1 for r in rows if r["collision_status"] == "near_collision_structural"
        ),
        "fallback_used_targets": sum(
            1 for r in rows if r["diagnostics"]["fallback_used"]
        ),
        "fallback_contamination_suspected": sum(
            1 for r in rows if r["diagnostics"]["fallback_written_to_graph"]
        ),
        "root_cause_counts": dict(
            collections.Counter(
                cause for r in rows for cause in r["root_cause_candidates"]
            )
        ),
        "next_issue_hints": dict(
            collections.Counter(
                r["next_issue_hint"] for r in rows if r.get("next_issue_hint")
            )
        ),
    }
    return {
        "audit_id": f"extraction_parity_pt_en_{(generated_at or datetime.now(timezone.utc).date()).isoformat() if isinstance(generated_at, datetime) else (generated_at or datetime.now(timezone.utc).strftime('%Y-%m-%d'))}",
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "build_space_commit": build_space_commit,
        "worker_run_id": worker_run_id,
        "quorum": quorum,
        "targets": rows,
        "summary": summary,
        "truthfulness_note": (
            "Read-only source-level parity audit. Does not promote facts, does not "
            "change quorum/confirmacoes, does not write Neo4j/Qdrant, does not call "
            "/api/ingest. Similarity/diagnostics only."
        ),
    }


def classify_log_fallback(entry: dict[str, Any]) -> dict[str, Any]:
    """Avalia uma entrada de log de ingest quanto a contaminação demo-memory."""
    used = bool(entry.get("fallback_used"))
    written = bool(entry.get("fallback_written_to_graph"))
    entities = entry.get("entities_processed")
    if used and written:
        root = "fallback_contamination"
        priority = "high"
        hint = NEXT_ISSUE_HINTS["fallback_contamination"]
    elif used:
        root = "extraction_absence"
        priority = "high"
        hint = NEXT_ISSUE_HINTS["extraction_absence"]
    else:
        root = ""
        priority = "low"
        hint = ""
    return {
        "url": entry.get("url"),
        "fallback_used": used,
        "fallback_type": entry.get("fallback_type") or ("demo-memory" if used else ""),
        "fallback_written_to_graph": written,
        "entities_processed": entities,
        "root_cause": root,
        "priority": priority,
        "next_issue_hint": hint,
        "masked_extraction_failure": bool(used and not (entities or 0)),
    }
