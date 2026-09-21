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


@pytest.mark.asyncio
async def test_episode_methods_degrade_gracefully_when_offline(monkeypatch):
    connector = GraphConnector()
    connector.driver = None

    async def boom():
        raise RuntimeError("offline")

    monkeypatch.setattr(connector, "connect", boom)
    assert await connector.persist_episodes([{"fact_hash": "x", "day": "2026-09-21"}]) == 0
    assert await connector.recent_episodes() == []
    assert await connector.prune_episodes() == 0
    assert await connector.mark_episodes_status(["x"]) == 0
    assert await connector.persist_episodes([]) == 0
    assert await connector.mark_episodes_status([]) == 0


def test_verify_quorum_from_env(tmp_path, monkeypatch):
    cfg = tmp_path / "settings.yaml"
    cfg.write_text("database:\n  graph:\n    uri: 'bolt://localhost:7687'\n", encoding="utf-8")
    monkeypatch.setenv("NEXUS_VERIFY_QUORUM", "5")
    assert GraphConnector(config_path=str(cfg)).verify_quorum == 5


def test_verify_quorum_from_settings(tmp_path, monkeypatch):
    cfg = tmp_path / "settings.yaml"
    cfg.write_text(
        "database:\n  graph:\n    uri: 'bolt://localhost:7687'\n"
        "security_policy:\n  triangulation:\n    verify_quorum: 4\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("NEXUS_VERIFY_QUORUM", raising=False)
    assert GraphConnector(config_path=str(cfg)).verify_quorum == 4


def test_verify_quorum_invalid_falls_back_to_three(tmp_path, monkeypatch):
    cfg = tmp_path / "settings.yaml"
    cfg.write_text("database:\n  graph:\n    uri: 'bolt://localhost:7687'\n", encoding="utf-8")
    monkeypatch.setenv("NEXUS_VERIFY_QUORUM", "abc")
    assert GraphConnector(config_path=str(cfg)).verify_quorum == 3
