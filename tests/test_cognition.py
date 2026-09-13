"""Testes do módulo de cognição (sem dependências externas)."""
from __future__ import annotations

import pytest

from src.cognition.reasoning import ChainOfThought, ReasoningStep
from src.cognition.rag_engine import RAGEngine
from src.miner.security_protocol import SecurityProtocol, VerificationResult


@pytest.mark.asyncio
async def test_chain_of_thought_decomposes():
    async def solver(prompt: str) -> str:
        return f"resp::{prompt}"

    cot = ChainOfThought(solver=solver)
    trace = await cot.reason("Meta", ["sub-1", "sub-2"])
    assert len(trace.steps) == 2
    assert trace.steps[0].result == "resp::sub-1"
    out = cot.synthesize(trace)
    assert "[META] Meta" in out


@pytest.mark.asyncio
async def test_rag_engine_pipeline():
    engine = RAGEngine()
    trace = await engine.answer(
        question="O que é IA?",
        seed_urls=[],
        local_knowledge=["conceito local"],
    )
    assert trace.goal == "O que é IA?"


@pytest.mark.asyncio
async def test_rag_engine_uses_memory_hits():
    engine = RAGEngine()
    engine.memory.add_relation("Inteligência Artificial", "UTILIZA", "Redes Neurais", 0.9, "local")
    trace = await engine.answer(question="redes neurais", seed_urls=[], local_knowledge=[])
    assert any("memória local" in s.description.lower() for s in trace.steps)


def test_security_triangulation_quorum():
    proto = SecurityProtocol(quorum=3, min_domain_score=0.7)
    sources = [
        {"url": "https://www.gov.br/a", "text": "Estudo confirma dado X."},
        {"url": "https://www.edu/b", "text": "Paper confirma dado X."},
        {"url": "https://blogspam.wordpress.com/c", "text": "URGENTE! dado X inacreditável!!!"},
    ]
    result: VerificationResult = proto.triangulate("dado X confirmado", sources)
    assert result.status.startswith("Hipótese")
    assert result.confidence < 0.9


def test_trusted_tech_domains_pass_the_trust_gate():
    proto = SecurityProtocol()
    assert proto.domain_score("https://huggingface.co/docs") == 0.8
    assert proto.domain_score("https://openai.com/research") == 0.8
    assert proto.domain_score("https://pytorch.org") == 0.9
    assert proto.domain_score("https://example.com") == 0.6
    assert proto.domain_score("https://reddit.com/x") == 0.4