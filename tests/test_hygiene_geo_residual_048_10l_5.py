"""#048.10L.5 — testes do gate de higiene residual (função pura, sem Neo4j)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.hygiene_geo_residual_048_10l_5 import build_dry_run  # noqa: E402


def _row(**over) -> dict:
    base = {"subject": "MINEIRAO", "object": "RIO DE JANEIRO", "chave": "mineirao|LOCALIZADO_EM|rio de janeiro",
            "verified": False, "confirmacoes": 1, "domains": ["pt.wikipedia.org"], "eid": "x"}
    base.update(over)
    return base


def test_dry_run_flags_wrong_city_target_as_safe():
    d = build_dry_run([_row()], set())
    assert len(d["candidates"]) == 1
    assert d["candidates"][0]["safe_to_remove"] is True
    assert d["abort_reasons"] == []
    assert d["would_delete_fact_count"] == 1
    assert d["would_change_verified_count"] == 0
    assert d["would_touch_qdrant"] is False


def test_dry_run_aborts_on_verified_target():
    d = build_dry_run([_row(verified=True, confirmacoes=3, domains=["a", "b", "c"])], set())
    assert d["abort_reasons"]
    assert d["candidates"][0]["safe_to_remove"] is False


def test_dry_run_aborts_on_expected_registry_membership():
    expected = {("MINEIRAO", "LOCALIZADO_EM", "RIODEJANEIRO")}
    d = build_dry_run([_row()], expected)
    assert d["abort_reasons"]
    assert d["candidates"][0]["safe_to_remove"] is False


def test_dry_run_ignores_non_target_rows():
    d = build_dry_run([_row(subject="BEIRA RIO", object="PORTO ALEGRE")], set())
    assert d["candidates"] == []
    assert d["would_delete_fact_count"] == 0
