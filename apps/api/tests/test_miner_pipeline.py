"""Testes do validador de esteira (headers anti-bloqueio + delay dinâmico)."""
from __future__ import annotations

import asyncio
import time

import pytest

from src.miner.anti_block import AntiBlockSystem


def test_generate_headers_structure():
    ab = AntiBlockSystem()
    headers = ab.generate_headers("https://wikipedia.org")
    assert isinstance(headers, dict)
    assert "User-Agent" in headers
    assert "Referer" in headers
    assert len(headers["User-Agent"]) > 10


@pytest.mark.asyncio
async def test_dynamic_delay_timing():
    ab = AntiBlockSystem()
    start = time.time()
    await ab.dynamic_delay()
    elapsed = time.time() - start
    assert elapsed >= 1.4, "delay muito curto — risco de ban"
    assert elapsed <= 4.2, "delay muito longo — acima do aceitável"


def test_dynamic_delay_with_fast_settings():
    ab = AntiBlockSystem(min_delay=0.0, max_delay=0.05)
    start = time.time()
    asyncio.run(ab.dynamic_delay())
    assert time.time() - start < 0.5