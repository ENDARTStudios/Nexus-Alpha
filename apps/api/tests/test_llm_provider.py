"""Testes da camada de geração de linguagem (llm_provider)."""
from __future__ import annotations

import pytest

from src.cognition.llm_provider import (
    ExtractiveResponder,
    OpenAICompatibleLLM,
    get_llm_provider,
)


@pytest.mark.asyncio
async def test_extractive_without_context():
    reply = await ExtractiveResponder().generate("pergunta", [])
    assert "não tenho fatos" in reply.lower() or "nao tenho fatos" in reply.lower()


@pytest.mark.asyncio
async def test_extractive_with_context_lists_facts():
    reply = await ExtractiveResponder().generate(
        "O que é IA?", [{"fact": "IA UTILIZA Redes Neurais", "source": "neo4j"}]
    )
    assert "IA UTILIZA Redes Neurais" in reply


def test_openai_compatible_unavailable_without_env(monkeypatch):
    monkeypatch.delenv("NEXUS_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("NEXUS_LLM_MODEL", raising=False)
    assert OpenAICompatibleLLM().available() is False


def test_openai_compatible_available_with_env(monkeypatch):
    monkeypatch.setenv("NEXUS_LLM_BASE_URL", "http://localhost:11434/v1")
    assert OpenAICompatibleLLM().available() is True


@pytest.mark.asyncio
async def test_openai_compatible_generate_returns_empty_when_unavailable(monkeypatch):
    monkeypatch.delenv("NEXUS_LLM_BASE_URL", raising=False)
    assert await OpenAICompatibleLLM().generate("q", []) == ""


def test_get_llm_provider_defaults_to_extractive(monkeypatch):
    monkeypatch.delenv("NEXUS_LLM_BASE_URL", raising=False)
    assert get_llm_provider().name == "extractive"


def test_get_llm_provider_prefers_remote(monkeypatch):
    monkeypatch.setenv("NEXUS_LLM_BASE_URL", "http://localhost:11434/v1")
    assert get_llm_provider().name == "openai-compatible"
