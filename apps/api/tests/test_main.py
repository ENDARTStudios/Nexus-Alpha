"""Testes do orquestrador NexusAlphaCore (sem rede real)."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.main import NexusAlphaCore


def _fake_core(monkeypatch) -> NexusAlphaCore:
    core = NexusAlphaCore(
        security=MagicMock(),
        vector=MagicMock(),
        miner=MagicMock(),
    )
    core.security.process_discovered_triplets = MagicMock(return_value={
        "status": "VERIFIED_FACT",
        "action": "INSERT_INTO_GRAPH",
        "final_confidence": 0.9,
        "reason": "mock",
    })
    core.graph_db.connect = AsyncMock()
    core.graph_db.close = AsyncMock()
    core.graph_db.ingest_payload = AsyncMock(return_value=1)
    core.vector_db.store_memory = MagicMock(return_value=True)
    return core


@pytest.mark.asyncio
async def test_cycle_persists_verified_facts():
    core = _fake_core(None)
    history = [{"source_url": "https://edu.org", "confidence": 0.8}]
    result = await core.execute_autonomous_cycle(
        "Inteligência Artificial",
        historical_records=history,
        simulated_mined_text="Inteligência Artificial utiliza Redes Neurais profundas e processa grandes volumes de dados.",
    )
    assert result["status"] == "done"
    assert result["verified"] >= 1
    assert core.graph_db.ingest_payload.await_count >= 1


@pytest.mark.asyncio
async def test_cycle_quarantines_unverified_facts():
    core = _fake_core(None)
    core.security.process_discovered_triplets = MagicMock(return_value={
        "status": "QUARANTINE",
        "action": "STORE_IN_ISOLATION",
        "final_confidence": 0.2,
        "reason": "fake",
    })
    result = await core.execute_autonomous_cycle(
        "IA",
        historical_records=[],
        simulated_mined_text="IA utiliza Redes Neurais para processar informações.",
    )
    assert result["status"] == "done"
    assert result["quarantined"] >= 0
    assert core.graph_db.ingest_payload.await_count == 0