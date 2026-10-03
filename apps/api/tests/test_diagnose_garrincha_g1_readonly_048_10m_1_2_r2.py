"""Testes offline do R2 Fase A — classificação do estado Garrincha (fixtures).

Nenhum teste escreve em Neo4j/Qdrant, nenhum chama /api/ingest, nenhum roda worker.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.diagnose_garrincha_g1_readonly_048_10m_1_2_r2 import (  # noqa: E402
    classify_garrincha_state,
    exact_query,
    subject_any_query,
    club_defendeu_query,
)

OBJECT_VARIANTS = ["BOTAFOGO DE FUTEBOL E REGATAS", "BOTAFOGO"]


def row(over: dict | None = None) -> dict:
    base = {
        "element_id": "4:x:3749",
        "sujeito": "MANUEL FRANCISCO DOS SANTOS",
        "predicado": "DEFENDEU",
        "objeto": "BOTAFOGO DE FUTEBOL E REGATAS",
        "verificado": False,
        "confirmacoes": 2,
        "domains": ["pt.wikipedia.org", "en.wikipedia.org"],
    }
    base.update(over or {})
    return base


def test_queries_sao_apenas_match_return() -> None:
    for q in (exact_query(), subject_any_query(), club_defendeu_query()):
        low = q.lower()
        assert low.startswith("match")
        for forbidden in ("create", "merge", "delete", "set ", "remove"):
            assert forbidden not in low, f"escrita em query: {forbidden}"


def test_estado_aceito_do_piloto_classifica_limpo() -> None:
    out = classify_garrincha_state([row()], [row()], [], OBJECT_VARIANTS)
    assert out["canonical_fact_found"] is True
    assert out["same_triple_confirmation"] is True
    assert out["distinct_domain_count"] == 2
    assert out["confirmed_domains"] == ["en.wikipedia.org", "pt.wikipedia.org"]
    assert out["non_wikimedia_domain_present"] is False
    assert out["span_broken"] is False
    assert out["junk_object"] is False
    assert out["forbidden_object"] is False
    assert out["invalid_predicate"] is False
    assert out["homonymy_risk"] == "low"
    assert out["blocking_reason"] is None


def test_fato_ausente_vira_nao_encontrado() -> None:
    out = classify_garrincha_state([], [], [], OBJECT_VARIANTS)
    assert out["canonical_fact_found"] is False
    assert out["distinct_domain_count"] == 0
    assert out["blocking_reason"] is None


def test_objeto_span_quebrado_marca_span_broken() -> None:
    broken = row({"objeto": "PELO SANTOS"})
    out = classify_garrincha_state([broken], [broken], [], OBJECT_VARIANTS)
    assert out["span_broken"] is True
    assert out["blocking_reason"] == "BLOCKED_048_10M_1_2_R2_SEMANTIC_RISK"


def test_objeto_nao_clube_marca_span_broken() -> None:
    # caso real do grafo: GARRINCHA --DEFENDEU--> PRIMEIRA PARTIDA DO TORNEIO
    broken = row({"objeto": "PRIMEIRA PARTIDA DO TORNEIO"})
    out = classify_garrincha_state([broken], [broken], [], OBJECT_VARIANTS)
    assert out["span_broken"] is True
    assert out["blocking_reason"] == "BLOCKED_048_10M_1_2_R2_SEMANTIC_RISK"


def test_objeto_vazio_marca_junk() -> None:
    junk = row({"objeto": ""})
    out = classify_garrincha_state([junk], [junk], [], OBJECT_VARIANTS)
    assert out["junk_object"] is True


def test_predicado_fora_do_vocabulario_marca_invalido() -> None:
    strange = row({"predicado": "ABACAXI"})
    out = classify_garrincha_state([row()], [strange], [], OBJECT_VARIANTS)
    assert out["invalid_predicate"] is True


def test_dois_fatos_ids_diferentes_nao_quebram_same_triple() -> None:
    a = row()
    b = row({"element_id": "4:x:9999", "domains": ["rsssfbrasil.com"], "confirmacoes": 1})
    out = classify_garrincha_state([a, b], [a], [], OBJECT_VARIANTS)
    assert out["distinct_domain_count"] == 3
    assert out["same_triple_confirmation"] is True
    assert out["non_wikimedia_domain_present"] is True
    assert out["confirmed_domains"] == ["en.wikipedia.org", "pt.wikipedia.org", "rsssfbrasil.com"]
