"""Testes do GraphConnector (queries, schema e contagem), sem rede real."""
from __future__ import annotations

import pytest

from src.database.graph_connector import GraphConnector, INGEST_QUERY


def test_ingest_query_is_apoc_free():
    assert "apoc." not in INGEST_QUERY
    assert "RELACIONA" in INGEST_QUERY


@pytest.mark.asyncio
async def test_ensure_schema_returns_false_when_offline(monkeypatch):
    connector = GraphConnector()
    connector.driver = None

    async def boom():
        raise RuntimeError("offline")

    monkeypatch.setattr(connector, "connect", boom)
    assert await connector.ensure_schema() is False


@pytest.mark.asyncio
async def test_count_concepts_returns_zero_when_offline(monkeypatch):
    connector = GraphConnector()
    connector.driver = None

    async def boom():
        raise RuntimeError("offline")

    monkeypatch.setattr(connector, "connect", boom)
    assert await connector.count_concepts() == 0
