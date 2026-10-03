"""Testes do ReasoningEngine."""
from __future__ import annotations

from src.cognition.reasoning_engine import ReasoningEngine


def test_busca_total_when_no_facts():
    engine = ReasoningEngine()
    plan = engine.evaluate_knowledge_gap("Computação Quântica", internal_facts=[])
    assert plan.decision == "BUSCA_TOTAL"
    assert len(plan.target_queries) >= 1
    assert len(plan.chain_of_thought) >= 3


def test_expansao_restrita_when_few_facts():
    engine = ReasoningEngine()
    plan = engine.evaluate_knowledge_gap("IA", internal_facts=["fato1", "fato2"])
    assert plan.decision == "EXPANSAO_RESTRITA"


def test_auto_reflexao_when_dense_memory():
    engine = ReasoningEngine()
    plan = engine.evaluate_knowledge_gap("IA", internal_facts=[f"fato{i}" for i in range(5)])
    assert plan.decision == "AUTO_REFLEXAO"
    assert plan.target_queries == []


def test_plan_to_dict_is_serializable():
    import json
    engine = ReasoningEngine()
    plan = engine.evaluate_knowledge_gap("IA", internal_facts=[])
    serialized = json.dumps(plan.to_dict(), ensure_ascii=False)
    assert "BUSCA_TOTAL" in serialized