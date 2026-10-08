"""Testes offline do R3 Fase A — queries do diagnóstico apenas MATCH/RETURN
e reuso da lógica pura do R2 (build_corrected_dry_run) com fixtures.

Nenhum teste escreve em Neo4j/Qdrant, nenhum chama /api/ingest, nenhum roda worker.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.diagnose_garrincha_g1_readonly_048_10m_1_2_r2 import (  # noqa: E402
    exact_query,
    subject_any_query,
    club_defendeu_query,
    classify_garrincha_state,
)

OBJECT_VARIANTS = ["BOTAFOGO DE FUTEBOL E REGATAS", "BOTAFOGO"]


def test_queries_r3_reuso_r2_sao_match_return() -> None:
    for q in (exact_query(), subject_any_query(), club_defendeu_query()):
        low = q.lower()
        assert low.startswith("match")
        for forbidden in ("create", "merge", "delete", "set ", "remove"):
            assert forbidden not in low


def test_r3_importa_build_corrected_dry_run_do_r2() -> None:
    from scripts.prepare_garrincha_g1_corrected_dry_run_048_10m_1_2_r2 import (
        build_corrected_dry_run as build_r2,
    )
    assert build_r2 is not None


def test_classificacao_estado_aceito_r2_permanece() -> None:
    row = {
        "element_id": "4:x:3749",
        "sujeito": "MANUEL FRANCISCO DOS SANTOS",
        "predicado": "DEFENDEU",
        "objeto": "BOTAFOGO DE FUTEBOL E REGATAS",
        "verificado": False,
        "confirmacoes": 2,
        "domains": ["pt.wikipedia.org", "en.wikipedia.org"],
    }
    out = classify_garrincha_state([row], [row], [], OBJECT_VARIANTS)
    assert out["canonical_fact_found"] is True
    assert out["same_triple_confirmation"] is True
    assert out["distinct_domain_count"] == 2
    assert out["blocking_reason"] is None
