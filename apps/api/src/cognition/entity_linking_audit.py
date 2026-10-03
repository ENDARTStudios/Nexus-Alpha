"""Nexus-Alpha — Entity linking read-only (#057, diagnóstico, sem promoção).

Responde: dos fatos persistidos, quantos pares **cross-domain** são candidatos
plausíveis à mesma entidade/objeto/relação, e quantos atingiriam quórum por
domínio se unificados por **alias curado**.

Regra de ouro: similaridade **sugere vínculo**; similaridade **não** verifica
fato, **não** aumenta quórum, **não** grava ``:Fato``, **não** altera
``confirmacoes``, **não** mescla nós. Módulo puro, sem Neo4j/Qdrant/embedding.

Limitação declarada: ``medium`` é **limite superior teórico** (pode inflar por
``mesmo predicado + um campo idêntico``); apenas ``high`` alimenta revisão de
alias curado. Entity linking não corrige páginas que retornaram
``entities_processed: 0`` (#048).
"""
from __future__ import annotations

import collections
import re
from datetime import datetime, timezone
from typing import Any, Optional

from .cross_source_audit import _norm, _union_find, domain_coverage, similarity

HIGH_CONFIDENCE = 0.85
MEDIUM_CONFIDENCE = 0.60
DEFAULT_MAX_EXAMPLES = 20

_ABBREVIATIONS: dict[str, tuple[str, ...]] = {
    "fc": ("futebol", "clube"),
    "cr": ("clube", "regatas"),
    "ec": ("esporte", "clube"),
}

_RANK: dict[str, int] = {"high": 3, "medium": 2, "low": 1}

_FORBIDDEN_CYPHER = re.compile(
    r"\b(?:MERGE|CREATE|SET|DELETE|REMOVE|DROP|LOAD\s+CSV|CALL\s+db\.)\b",
    re.IGNORECASE,
)

FORBIDDEN_MARKERS: tuple[str, ...] = (
    "hf_",
    "neo4j",
    "password",
    "token",
    "Authorization",
    "X-Nexus-Token",
    "NEO4J_URI",
    "QDRANT_API_KEY",
)

CREDENTIAL_MARKERS: tuple[str, ...] = (
    "hf_",
    "neo4j+s://",
    "bolt://",
    "Authorization",
    "X-Nexus-Token",
    "NEO4J_URI",
    "NEO4J_PASSWORD",
    "QDRANT_API_KEY",
    "HF_TOKEN",
    "NEXUS_API_TOKEN",
    "auth-token",
    "api-key",
)


def assert_read_only_cypher(query: str) -> None:
    """Levanta ``ValueError`` se a query tiver escrita (MERGE/CREATE/SET/...)."""
    match = _FORBIDDEN_CYPHER.search(query or "")
    if match:
        raise ValueError(f"query read-only violada: {match.group(0)}")


def assert_no_secret_markers(payload: str, markers: tuple[str, ...] = FORBIDDEN_MARKERS) -> list[str]:
    """Retorna a lista de marcadores de segredo encontrados (case-insensitive)."""
    haystack = (payload or "").lower()
    return [marker for marker in markers if marker.lower() in haystack]


def _prepare(fact: dict[str, Any]) -> dict[str, Any]:
    domains = sorted({
        str(d).strip().lower() for d in (fact.get("domains") or []) if str(d).strip()
    })
    return {
        "fact_hash": str(fact.get("fact_hash") or ""),
        "subject": fact.get("subject"),
        "predicate": fact.get("predicate"),
        "object": fact.get("object"),
        "domains": domains,
    }


def _tokens(text: Any) -> set[str]:
    return set(_norm(text).split())


def alias_deterministic(left: Any, right: Any) -> bool:
    """Sigla expandida **no outro campo** + núcleo comum fora da sigla.

    ``Santos FC`` ↔ ``Santos Futebol Clube`` → True. ``Fortaleza EC`` sem núcleo
    compartilhado com a expansão → False (cai para ``medium``).
    """
    a, b = _tokens(left), _tokens(right)
    if not a or not b:
        return False
    for short, expansion in _ABBREVIATIONS.items():
        expected = set(expansion)
        if short in a and expected <= b and (a - {short}) & b:
            return True
        if short in b and expected <= a and (b - {short}) & a:
            return True
    return False


def _field_rank(value: float, exact: bool, alias: bool) -> float:
    if exact:
        return 1.0
    if alias:
        return max(value, 0.9)
    return value


def score_pair(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Pontuação determinística do par (lexical + sinal de alias), 0..1."""
    subject_similarity = similarity(left.get("subject"), right.get("subject"))
    object_similarity = similarity(left.get("object"), right.get("object"))
    subject_exact = bool(_norm(left.get("subject"))) and _norm(left.get("subject")) == _norm(right.get("subject"))
    object_exact = bool(_norm(left.get("object"))) and _norm(left.get("object")) == _norm(right.get("object"))
    subject_alias = alias_deterministic(left.get("subject"), right.get("subject"))
    object_alias = alias_deterministic(left.get("object"), right.get("object"))
    predicate_equal = bool(_norm(left.get("predicate"))) and _norm(left.get("predicate")) == _norm(right.get("predicate"))
    score = round(max(
        _field_rank(subject_similarity, subject_exact, subject_alias),
        _field_rank(object_similarity, object_exact, object_alias),
    ), 4)
    return {
        "subject_similarity": subject_similarity,
        "object_similarity": object_similarity,
        "subject_exact": subject_exact,
        "object_exact": object_exact,
        "subject_alias": subject_alias,
        "object_alias": object_alias,
        "predicate_equal": predicate_equal,
        "score": score,
    }


def _eligible(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_domains = set(left.get("domains") or [])
    right_domains = set(right.get("domains") or [])
    if not left_domains or not right_domains:
        return False
    if left_domains & right_domains:
        return False
    left_hash = left.get("fact_hash") or ""
    right_hash = right.get("fact_hash") or ""
    if left_hash and right_hash and left_hash == right_hash:
        return False
    return True


def classify_link_candidate(
    left: dict[str, Any],
    right: dict[str, Any],
    high: float = HIGH_CONFIDENCE,
    medium: float = MEDIUM_CONFIDENCE,
) -> Optional[tuple[str, str]]:
    """Classifica o par como ``(confiança, tipo)`` ou ``None`` (não candidato).

    Exige domínios **disjuntos** e ``fact_hash`` distintos. Predicado diferente
    **nunca** vira ``high``.
    """
    if not _eligible(left, right):
        return None
    scores = score_pair(left, right)

    if scores["predicate_equal"]:
        if scores["subject_exact"] and scores["object_exact"]:
            return None
        if scores["subject_exact"] and (scores["object_alias"] or scores["object_similarity"] >= high):
            return "high", "object_variant"
        if scores["object_exact"] and (scores["subject_alias"] or scores["subject_similarity"] >= high):
            return "high", "subject_variant"
        if scores["subject_similarity"] >= high and scores["object_similarity"] >= high:
            if scores["subject_similarity"] <= scores["object_similarity"]:
                return "high", "subject_variant"
            return "high", "object_variant"
        if scores["subject_exact"]:
            return "medium", "object_variant"
        if scores["object_exact"]:
            return "medium", "subject_variant"
        if scores["subject_similarity"] >= medium and scores["object_similarity"] >= medium:
            if scores["subject_similarity"] <= scores["object_similarity"]:
                return "medium", "subject_variant"
            return "medium", "object_variant"
        return None

    if scores["subject_similarity"] >= high and scores["object_similarity"] >= high:
        return "medium", "predicate_variant"
    if scores["subject_exact"] or scores["object_exact"]:
        return "low", "predicate_variant"
    if scores["subject_similarity"] >= medium and scores["object_similarity"] >= medium:
        return "low", "predicate_variant"
    return None


def generate_candidate_pairs(
    facts: list[dict[str, Any]],
    high: float = HIGH_CONFIDENCE,
    medium: float = MEDIUM_CONFIDENCE,
) -> list[dict[str, Any]]:
    """Pares candidatos ordenados de forma determinística.

    Ordenação: confiança desc → score desc → ``fact_hash`` esq. asc → ``fact_hash``
    dir. asc. ``left`` sempre tem o ``fact_hash`` menor. Cada par carrega
    ``promote_automatically: false``.
    """
    prepared = [_prepare(fact) for fact in facts]
    pairs: list[dict[str, Any]] = []
    for i in range(len(prepared)):
        for j in range(i + 1, len(prepared)):
            classified = classify_link_candidate(prepared[i], prepared[j], high, medium)
            if classified is None:
                continue
            confidence, mismatch = classified
            scores = score_pair(prepared[i], prepared[j])
            left, right = prepared[i], prepared[j]
            if left["fact_hash"] > right["fact_hash"]:
                left, right = right, left
            pairs.append({
                "confidence": confidence,
                "type": mismatch,
                "score": scores["score"],
                "left_index": i,
                "right_index": j,
                "left_fact_hash": left["fact_hash"],
                "right_fact_hash": right["fact_hash"],
                "left": dict(left),
                "right": dict(right),
                "promote_automatically": False,
            })
    pairs.sort(key=lambda pair: (
        -_RANK[pair["confidence"]],
        -pair["score"],
        pair["left_fact_hash"],
        pair["right_fact_hash"],
    ))
    return pairs


def _potential_verified(
    pairs: list[dict[str, Any]],
    prepared: list[dict[str, Any]],
    confidences: set[str],
    quorum: int,
) -> int:
    relevant = [p for p in pairs if p["confidence"] in confidences]
    if not relevant:
        return 0
    find, union = _union_find(len(prepared))
    for pair in relevant:
        union(pair["left_index"], pair["right_index"])
    clusters: dict[int, set[str]] = collections.defaultdict(set)
    members: dict[int, int] = collections.defaultdict(int)
    for idx, fact in enumerate(prepared):
        root = find(idx)
        clusters[root].update(fact["domains"])
        members[root] += 1
    return sum(
        1 for root, domains in clusters.items()
        if len(domains) >= quorum and members[root] > 1
    )


def _mismatch_types(
    pairs: list[dict[str, Any]],
    prepared: list[dict[str, Any]],
) -> dict[str, int]:
    best: dict[int, tuple[int, float, str]] = {}
    for pair in pairs:
        if pair["confidence"] == "low":
            continue
        rank = _RANK[pair["confidence"]]
        for idx in (pair["left_index"], pair["right_index"]):
            current = best.get(idx)
            if current is None or (rank, pair["score"]) > current[:2]:
                best[idx] = (rank, pair["score"], pair["type"])
    counts = {"subject_variant": 0, "object_variant": 0, "predicate_variant": 0, "true_unique": 0}
    for idx in range(len(prepared)):
        entry = best.get(idx)
        if entry is None:
            counts["true_unique"] += 1
        else:
            counts[entry[2]] += 1
    return counts


def _excerpt(pair_key: str, pair: dict[str, Any]) -> dict[str, Any]:
    fact = pair[pair_key]
    return {
        "fact_hash": fact["fact_hash"],
        "subject": fact["subject"],
        "predicate": fact["predicate"],
        "object": fact["object"],
        "domains": list(fact["domains"]),
    }


def build_report(
    facts: list[dict[str, Any]],
    quorum: int = 3,
    high: float = HIGH_CONFIDENCE,
    medium: float = MEDIUM_CONFIDENCE,
    max_examples: int = DEFAULT_MAX_EXAMPLES,
    audit_id: Optional[str] = None,
    generated_at: Optional[str] = None,
    build_space_commit: Optional[str] = None,
    worker_run_id: Optional[str] = None,
) -> dict[str, Any]:
    """Relatório read-only de candidatos cross-domain (nunca promove fato)."""
    prepared = [_prepare(fact) for fact in facts]
    pairs = generate_candidate_pairs(prepared, high, medium)

    counts = {"high": 0, "medium": 0, "low": 0}
    for pair in pairs:
        counts[pair["confidence"]] += 1

    coverage = domain_coverage(prepared)
    coverage["facts_by_domain"] = dict(sorted(
        coverage["facts_by_domain"].items(),
        key=lambda item: (-item[1], item[0]),
    ))

    now = datetime.now(timezone.utc)
    examples: list[dict[str, Any]] = []
    for pair in pairs[:max_examples]:
        examples.append({
            "confidence": pair["confidence"],
            "type": pair["type"],
            "score": pair["score"],
            "left": _excerpt("left", pair),
            "right": _excerpt("right", pair),
            "promote_automatically": False,
        })

    return {
        "audit_id": audit_id or f"entity_linking_audit_{now:%Y-%m-%d}",
        "generated_at": generated_at or now.isoformat(),
        "build_space_commit": build_space_commit or "unknown",
        "worker_run_id": worker_run_id or "unknown",
        "quorum": quorum,
        "facts_total": coverage["facts_total"],
        "domains_total": coverage["domains_total"],
        "domain_coverage": coverage,
        "candidate_pairs": counts,
        "potential_verified_if_high_aliasing": _potential_verified(pairs, prepared, {"high"}, quorum),
        "potential_verified_if_medium_aliasing": _potential_verified(pairs, prepared, {"high", "medium"}, quorum),
        "mismatch_types": _mismatch_types(pairs, prepared),
        "examples": examples,
        "promote_automatically": False,
        "parameters": {
            "quorum": quorum,
            "high": high,
            "medium": medium,
            "max_examples": max_examples,
            "domains_require_disjoint": True,
            "mismatch_types_scope": "fact_level_best_candidate_high_or_medium",
            "qdrant_used": False,
        },
        "truthfulness_note": {
            "read_only": True,
            "promote_automatically": False,
            "qdrant_ignored": True,
            "does_not_change_quorum_or_confirmacoes": True,
            "medium_is_upper_bound": True,
            "medium_does_not_imply_safe_aliasing": True,
            "only_high_is_recommended_for_curated_alias_review": True,
        },
    }
