"""Testes do AntiBlockSystem."""
from __future__ import annotations

import asyncio

from src.miner.anti_block import AntiBlockSystem


def test_generate_headers_has_required_fields():
    ab = AntiBlockSystem(min_delay=0.0, max_delay=0.0)
    headers = ab.generate_headers("https://example.com")
    for key in ["User-Agent", "Accept", "Accept-Language", "Referer"]:
        assert key in headers
    assert "Mozilla" in headers["User-Agent"]


def test_user_agent_rotation_changes():
    ab = AntiBlockSystem()
    agents = {ab.generate_headers()["User-Agent"] for _ in range(20)}
    assert len(agents) > 1


def test_dynamic_delay_runs():
    async def _run():
        ab = AntiBlockSystem(min_delay=0.0, max_delay=0.01)
        await ab.dynamic_delay()
    asyncio.run(_run())