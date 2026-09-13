"""Testes do ChatService (recuperação híbrida + sessões), sem rede real."""
from __future__ import annotations

import pytest

from src.cognition.chat_service import ChatService, extract_keywords


class FakeGraph:
    def __init__(self, rows):
        self.rows = rows
        self.calls: list[list[str]] = []

    async def search_context(self, keywords, limit: int = 8):
        self.calls.append(list(keywords))
        return self.rows


class BoomGraph:
    async def search_context(self, keywords, limit: int = 8):
        raise RuntimeError("neo4j down")


class FakeVector:
    embedding_dim = 384

    def __init__(self, hits):
        self.hits = hits

    def query_similarity(self, vector, limit: int = 3):
        return self.hits


class FakeLLM:
    name = "fake"

    async def generate(self, question, context):
        return f"resp:{question}:{len(context)}"


def test_extract_keywords_filters_stopwords():
    keywords = extract_keywords("O que é a inteligência artificial?")
    assert "inteligência" in keywords
    assert "artificial" in keywords
    assert "que" not in keywords


@pytest.mark.asyncio
async def test_answer_combines_graph_and_vector_context():
    graph = FakeGraph([{"subject": "IA", "predicate": "UTILIZA", "object": "Redes Neurais"}])
    vector = FakeVector([{"score": 0.9, "payload": {"text": "fragmento vetorial", "url": "http://fonte"}}])
    service = ChatService(graph=graph, vector=vector, llm=FakeLLM())

    result = await service.answer("O que é IA?", "sess-1")

    assert result["reply"] == "resp:O que é IA?:2"
    assert result["provider"] == "fake"
    assert result["context_size"] == 2
    assert "neo4j" in result["sources"]
    assert "http://fonte" in result["sources"]
    assert graph.calls and "ia" in graph.calls[0]


@pytest.mark.asyncio
async def test_answer_degrades_when_graph_unavailable():
    service = ChatService(graph=BoomGraph(), vector=FakeVector([]), llm=FakeLLM())
    result = await service.answer("tema qualquer", "sess-2")
    assert result["reply"].startswith("resp:")
    assert result["context_size"] == 0


@pytest.mark.asyncio
async def test_answer_handles_empty_message():
    service = ChatService(graph=FakeGraph([]), vector=FakeVector([]), llm=FakeLLM())
    result = await service.answer("   ", "sess-3")
    assert "envie uma mensagem" in result["reply"].lower()
    assert result["context_size"] == 0


@pytest.mark.asyncio
async def test_session_history_is_remembered_and_bounded():
    service = ChatService(
        graph=FakeGraph([]), vector=FakeVector([]), llm=FakeLLM(), history_turns=1
    )
    await service.answer("primeira", "sess-x")
    await service.answer("segunda", "sess-x")
    history = service._sessions["sess-x"]
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[-1]["role"] == "assistant"
