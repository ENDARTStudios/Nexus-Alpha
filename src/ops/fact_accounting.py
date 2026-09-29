"""#052.3.1 — Contabilidade pura de fatos para graph_scoped_gap (read-only, sem escrita).

Nao acessa rede/Neo4j/Qdrant, nao importa cognicao, nao escreve. Apenas calcula a
contabilidade a partir de contagens ja obtidas e classifica o status.
"""
from __future__ import annotations

from dataclasses import dataclass, field

WARN_HASH_MISSING = "FACT_HASH_MISSING_PRESENT"
WARN_DUPLICATE = "DUPLICATE_FACT_HASH_GROUPS_PRESENT"
WARN_QUERY_ERROR = "FACT_ACCOUNTING_QUERY_ERROR"
WARN_GAP_POSITIVE = "GRAPH_SCOPED_GAP_POSITIVE_UNEXPECTED"

STATUS_OK = "ok"
STATUS_MISSING = "missing_fact_hashes"
STATUS_DUPLICATE = "duplicate_fact_hashes"
STATUS_QUERY_ERROR = "query_error"


@dataclass
class FactAccountingCounts:
    persisted_facts: int
    distinct_non_null_fact_hashes: int
    missing_fact_hash_count: int
    distinct_fact_node_keys: int
    duplicate_fact_hash_group_count: int


@dataclass
class FactAccountingResult:
    persisted_facts: int | None
    distinct_non_null_fact_hashes: int | None
    missing_fact_hash_count: int | None
    distinct_fact_node_keys: int | None
    duplicate_fact_hash_group_count: int | None
    graph_scoped_gap: int | None
    fact_accounting_status: str
    warnings: list[str] = field(default_factory=list)


def compute_fact_accounting(counts: FactAccountingCounts | None) -> FactAccountingResult:
    """Deriva status/warnings/gap. ``graph_scoped_gap = distinct_fact_node_keys - persisted_facts``."""
    if counts is None:
        return FactAccountingResult(None, None, None, None, None, None, STATUS_QUERY_ERROR, [WARN_QUERY_ERROR])

    p = int(counts.persisted_facts)
    dn = int(counts.distinct_non_null_fact_hashes)
    miss = int(counts.missing_fact_hash_count)
    dk = int(counts.distinct_fact_node_keys)
    dup = int(counts.duplicate_fact_hash_group_count)

    warnings: list[str] = []
    if p == 0:
        status, gap = STATUS_OK, 0
    elif dk > p:
        status, gap = STATUS_QUERY_ERROR, None
        warnings.append(WARN_GAP_POSITIVE)
    elif dup > 0:
        status, gap = STATUS_DUPLICATE, dk - p
        warnings.append(WARN_DUPLICATE)
    elif miss > 0:
        status, gap = STATUS_MISSING, dk - p
        warnings.append(WARN_HASH_MISSING)
    else:
        status, gap = STATUS_OK, dk - p

    return FactAccountingResult(p, dn, miss, dk, dup, gap, status, warnings)
