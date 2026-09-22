"""Nexus-Alpha — Auditoria de near-match cross-source (#046, metric-only).

Responde: "dos fatos com 1 domínio, quantos têm near-match com fatos de outros
domínios?" para separar duas hipóteses:

- **H1** divergência de entidade/objeto (fontes falam o mesmo fato com superfícies
  diferentes) → muitos near-matches → canonicalização/aliasing (#047);
- **H2** cobertura insuficiente de domínios → poucos near-matches → ampliar seeds
  independentes (#048).

Regra de ouro: similaridade **diagnostica**, nunca valida. Este módulo é puro e
**read-only**: não escreve `:Fato`, não altera `confirmacoes`, não promove nada.
A similaridade é **lexical/estrutural** (sem Qdrant/vetores stale e sem embedding
de validação). Limitação conhecida: sinônimos não lexicalmente parecidos
(ex.: ``Vila Belmiro`` ↔ ``Estádio Urbano Caldeira``) NÃO são capturados.
"""
from __future__ import annotations

import collections
import difflib
import re
import unicodedata
from typing import Any, Optional

HIGH_CONFIDENCE = 0.85
MEDIUM_CONFIDENCE = 0.60

_STOP = frozenset({
    "o", "a", "os", "as", "um", "uma", "uns", "umas",
    "the", "an", "of", "de", "do", "da", "dos", "das",
})


def _norm(text: Any) -> str:
    """minúsculas, sem acentos/pontuação, sem artigos iniciais, espaços colapsados."""
    folded = unicodedata.normalize("NFKD", str(text or "").strip().lower())
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    folded = re.sub(r"[^a-z0-9\s]+", " ", folded)
    tokens = [t for t in folded.split() if t and t not in _STOP]
    return " ".join(tokens)


def _tokens(text: str) -> set[str]:
    return set(_norm(text).split())


def similarity(left: Any, right: Any) -> float:
    """Similaridade lexical 0..1 = máx(jaccard de tokens, razão de sequência)."""
    a, b = _norm(left), _norm(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    ta, tb = _tokens(a), _tokens(b)
    jaccard = len(ta & tb) / len(ta | tb) if (ta | tb) else 0.0
    ratio = difflib.SequenceMatcher(None, a, b).ratio()
    return round(max(jaccard, ratio), 4)


def classify_near_match(
    left: dict[str, Any],
    right: dict[str, Any],
    high: float = HIGH_CONFIDENCE,
    medium: float = MEDIUM_CONFIDENCE,
) -> tuple[Optional[str], Optional[str]]:
    """Classifica um par como ``(confiança, tipo)`` ou ``(None, None)``.

    Tipos: ``subject_variant``, ``object_variant``, ``predicate_variant``.
    Exige domínios diferentes (corroboração cross-source).
    """
    if set(left.get("domains") or []) == set(right.get("domains") or []):
        return None, None

    subject_sim = similarity(left.get("subject"), right.get("subject"))
    object_sim = similarity(left.get("object"), right.get("object"))
    same_predicate = (left.get("predicate") or "") == (right.get("predicate") or "")

    if same_predicate:
        s_exact = _norm(left.get("subject")) == _norm(right.get("subject"))
        o_exact = _norm(left.get("object")) == _norm(right.get("object"))
        if s_exact and o_exact:
            return None, None
        if s_exact and object_sim >= high:
            return "high", "object_variant"
        if o_exact and subject_sim >= high:
            return "high", "subject_variant"
        if subject_sim >= high and object_sim >= high:
            variant = "object_variant" if object_sim <= subject_sim else "subject_variant"
            return "high", variant
        if subject_sim >= medium and object_sim >= medium:
            variant = "subject_variant" if subject_sim <= object_sim else "object_variant"
            return "medium", variant
        return None, None

    # predicados diferentes: só relevante se sujeito E objeto casam muito bem.
    if subject_sim >= high and object_sim >= high:
        return "medium", "predicate_variant"
    return None, None


def _union_find(n: int):
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    return find, union


def audit(
    facts: list[dict[str, Any]],
    quorum: int = 3,
    high: float = HIGH_CONFIDENCE,
    medium: float = MEDIUM_CONFIDENCE,
    max_examples: int = 20,
) -> dict[str, Any]:
    """Relatório read-only de near-match cross-source (sem promover fato)."""
    prepared: list[dict[str, Any]] = []
    for fact in facts:
        domains = sorted({str(d).strip().lower() for d in (fact.get("domains") or []) if d})
        prepared.append({
            "subject": fact.get("subject"),
            "predicate": fact.get("predicate"),
            "object": fact.get("object"),
            "domains": domains,
        })

    total = len(prepared)
    one_domain = [f for f in prepared if len(f["domains"]) == 1]
    multi_domain = [f for f in prepared if len(f["domains"]) >= 2]

    best: dict[int, dict[str, Any]] = {}
    high_pairs: list[tuple[int, int, str]] = []
    for i in range(total):
        for j in range(i + 1, total):
            confidence, mismatch = classify_near_match(prepared[i], prepared[j], high, medium)
            if confidence is None:
                continue
            if confidence == "high":
                high_pairs.append((i, j, mismatch or "unknown"))
            for idx, other in ((i, j), (j, i)):
                if len(prepared[idx]["domains"]) != 1:
                    continue
                current = best.get(idx)
                score = max(similarity(prepared[idx]["subject"], prepared[other]["subject"]),
                            similarity(prepared[idx]["object"], prepared[other]["object"]))
                rank = {"high": 2, "medium": 1}.get(confidence, 0)
                current_rank = {"high": 2, "medium": 1}.get(current["confidence"], 0) if current else 0
                if current is None or rank > current_rank or (rank == current_rank and score > current["score"]):
                    best[idx] = {"confidence": confidence, "mismatch": mismatch,
                                 "score": score, "other": prepared[other]}

    find, union = _union_find(total)
    for i, j, _ in high_pairs:
        union(i, j)

    clusters: dict[int, set[str]] = collections.defaultdict(set)
    members: dict[int, int] = collections.defaultdict(int)
    for idx, fact in enumerate(prepared):
        root = find(idx)
        clusters[root].update(fact["domains"])
        members[root] += 1
    potential_verified_if_linking = sum(
        1 for root, domains in clusters.items()
        if len(domains) >= quorum and members[root] > 1
    )

    near = {"high": 0, "medium": 0, "low": 0}
    mismatch_types = {"subject_variant": 0, "object_variant": 0, "predicate_variant": 0, "true_unique": 0}
    examples: list[dict[str, Any]] = []
    for idx in [i for i, f in enumerate(prepared) if len(f["domains"]) == 1]:
        entry = best.get(idx)
        if entry is None:
            mismatch_types["true_unique"] += 1
            continue
        if entry["confidence"] == "high":
            near["high"] += 1
            mismatch_types[entry["mismatch"]] = mismatch_types.get(entry["mismatch"], 0) + 1
            if len(examples) < max_examples:
                examples.append({
                    "type": entry["mismatch"],
                    "left": {**{k: prepared[idx][k] for k in ("subject", "predicate", "object")},
                             "domain": prepared[idx]["domains"][0]},
                    "right": {**{k: entry["other"][k] for k in ("subject", "predicate", "object")},
                              "domain": (entry["other"]["domains"] or ["?"])[0]},
                    "score": entry["score"],
                })
        elif entry["confidence"] == "medium":
            near["medium"] += 1
            if entry["mismatch"] == "predicate_variant":
                mismatch_types["predicate_variant"] += 1
            else:
                mismatch_types["true_unique"] += 1
        else:
            near["low"] += 1

    one_domain_count = len(one_domain)
    return {
        "facts_total": total,
        "facts_with_one_domain": one_domain_count,
        "facts_with_two_or_more_domains": len(multi_domain),
        "exact_cross_source_matches": len(multi_domain),
        "near_matches": near,
        "near_match_rate_high": round(near["high"] / one_domain_count, 4) if one_domain_count else 0.0,
        "potential_verified_if_linking": potential_verified_if_linking,
        "mismatch_types": mismatch_types,
        "top_examples": examples,
        "parameters": {"quorum": quorum, "high": high, "medium": medium},
    }
