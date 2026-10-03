"""#052.3.1 — testes do helper puro de contabilidade de fatos (offline)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.ops.fact_accounting import (  # noqa: E402
    FactAccountingCounts,
    compute_fact_accounting,
)


def test_all_unique_hashes_ok():
    r = compute_fact_accounting(FactAccountingCounts(404, 404, 0, 404, 0))
    assert r.graph_scoped_gap == 0
    assert r.fact_accounting_status == "ok"
    assert r.warnings == []


def test_missing_hashes_partial():
    r = compute_fact_accounting(FactAccountingCounts(10, 7, 3, 10, 0))
    assert r.graph_scoped_gap == 0
    assert r.fact_accounting_status == "missing_fact_hashes"
    assert "FACT_HASH_MISSING_PRESENT" in r.warnings


def test_duplicate_hashes_blocked():
    r = compute_fact_accounting(FactAccountingCounts(10, 9, 0, 9, 1))
    assert r.graph_scoped_gap == -1
    assert r.fact_accounting_status == "duplicate_fact_hashes"
    assert "DUPLICATE_FACT_HASH_GROUPS_PRESENT" in r.warnings


def test_persisted_zero_ok():
    r = compute_fact_accounting(FactAccountingCounts(0, 0, 0, 0, 0))
    assert r.graph_scoped_gap == 0
    assert r.fact_accounting_status == "ok"


def test_positive_gap_query_error():
    r = compute_fact_accounting(FactAccountingCounts(10, 10, 0, 12, 0))
    assert r.fact_accounting_status == "query_error"
    assert r.graph_scoped_gap is None
    assert "GRAPH_SCOPED_GAP_POSITIVE_UNEXPECTED" in r.warnings


def test_none_counts_query_error():
    r = compute_fact_accounting(None)
    assert r.fact_accounting_status == "query_error"
    assert r.graph_scoped_gap is None
    assert "FACT_ACCOUNTING_QUERY_ERROR" in r.warnings
