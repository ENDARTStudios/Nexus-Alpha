"""Testes do motor GraphRAG (subgrafo contextual), sem rede real."""
from __future__ import annotations

import pytest

from src.cognition.graph_rag import GraphRAGEngine, SUBGRAPH_QUERY


class FakeResult:
    def __init__(self, records):
        self._records = list(records)
        self._index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._index >= len(self._records):
            raise StopAsyncIteration
        record = self._records[self._index]
        self._index += 1
        return record


class FakeSession:
    def __init__(self, records):
        self.records = records

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def run(self, query, **kwargs):
        return FakeResult(self.records)


class FakeDriver:
    def __init__(self, records):
        self.records = records

    def session(self):
        return FakeSession(self.records)


class FakeGraph:
    def __init__(self, records):
        self.driver = FakeDriver(records)


class ExplodingSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def run(self, query, **kwargs):
        raise RuntimeError("neo4j down")


class ExplodingDriver:
    def session(self):
        return ExplodingSession()


@pytest.mark.asyncio
async def test_graph_rag_context_building():
    records = [
        {"origem": "MACHINE LEARNING", "relacoes": ["PERTENCE_A"], "destino": "INTELIGÊNCIA ARTIFICIAL"},
        {"origem": "IA GENERATIVA", "relacoes": ["DISTRIBUIR", "PERTENCE_A"], "destino": "INTELIGÊNCIA ARTIFICIAL"},
    ]
    context = await GraphRAGEngine(FakeGraph(records)).retrieve_subgraph_context("machine learning")
    assert "MACHINE LEARNING" in context
    assert "INTELIGÊNCIA ARTIFICIAL" in context
    assert "PERTENCE_A" in context
    assert "Fato Mapeado" in context
    assert "DISTRIBUIR -> PERTENCE_A" in context


@pytest.mark.asyncio
async def test_graph_rag_empty_entity_returns_empty():
    engine = GraphRAGEngine(FakeGraph([]))
    assert await engine.retrieve_subgraph_context("") == ""
    assert await engine.retrieve_subgraph_context("   ") == ""


@pytest.mark.asyncio
async def test_graph_rag_no_driver_returns_empty():
    class NoDriver:
        pass

    assert await GraphRAGEngine(NoDriver()).retrieve_subgraph_context("IA") == ""
    assert await GraphRAGEngine(None).retrieve_subgraph_context("IA") == ""


@pytest.mark.asyncio
async def test_graph_rag_dedupes_lines():
    record = {"origem": "A", "relacoes": ["X"], "destino": "B"}
    context = await GraphRAGEngine(FakeGraph([record, record])).retrieve_subgraph_context("a")
    assert context.count("Fato Mapeado") == 1


@pytest.mark.asyncio
async def test_graph_rag_handles_driver_error():
    class BoomGraph:
        driver = ExplodingDriver()

    assert await GraphRAGEngine(BoomGraph()).retrieve_subgraph_context("IA") == ""


def test_subgraph_query_uses_real_schema():
    assert "RELACIONA" in SUBGRAPH_QUERY
    assert "r.predicate" in SUBGRAPH_QUERY
    assert "UTILIZA|" not in SUBGRAPH_QUERY


class FakeSearchGraph:
    def __init__(self, records):
        self.records = records

    async def search_context(self, keywords, limit: int = 8):
        return []

    @property
    def driver(self):
        return FakeDriver(self.records)


class FakeVector:
    embedding_dim = 384

    def query_similarity(self, vector, limit: int = 3):
        return []


class FakeLLM:
    name = "fake"

    async def generate(self, question, context):
        return "ok"


@pytest.mark.asyncio
async def test_chat_service_includes_graphrag_source():
    from src.cognition.chat_service import ChatService

    records = [{"origem": "IA", "relacoes": ["USA"], "destino": "DADOS"}]
    service = ChatService(
        graph=FakeSearchGraph(records), vector=FakeVector(), llm=FakeLLM()
    )
    result = await service.answer("inteligência artificial", "sessao-grafo")
    assert "graphrag" in result["sources"]
    assert any("Subgrafo GraphRAG" in step for step in result["reasoning_steps"])
