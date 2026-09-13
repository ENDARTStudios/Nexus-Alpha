"""Testes de integração do fallback AgentReach/BrowserMiner no WebMiner."""
from __future__ import annotations

import pytest

from src.miner.anti_block import AntiBlockSystem
from src.miner.web_miner import WebMiner


SHORT_HTML = "<html><head><title>curto</title></head><body><p>oi</p></body></html>"


class FakeClient:
    async def get(self, url, **kwargs):
        class Resp:
            status_code = 200
            text = SHORT_HTML

        return Resp()


class FakeReach:
    def __init__(self, payload):
        self.payload = payload

    def available(self) -> bool:
        return True

    async def fetch(self, url):
        return self.payload


class FakeRenderer:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def available(self) -> bool:
        return True

    async def fetch_rendered(self, url):
        self.calls += 1
        return self.payload


def _payload(content: str, provider: str) -> dict:
    return {
        "source_url": "https://example.com",
        "timestamp": 1,
        "domain_score": 0.0,
        "metadata": {"provider": provider},
        "title": "example",
        "content": content,
        "extracted_entities": [],
    }


@pytest.mark.asyncio
async def test_miner_uses_reach_fallback_when_static_content_short():
    miner = WebMiner(
        anti_block=AntiBlockSystem(min_delay=0, max_delay=0),
        reach=FakeReach(_payload("conteudo via reach " * 30, "jina-reader")),
    )
    results = await miner.mine_urls(["https://example.com"], client=FakeClient())
    assert len(results) == 1
    assert "via reach" in results[0]["content"]
    assert results[0]["payload"]["metadata"]["provider"] == "jina-reader"


@pytest.mark.asyncio
async def test_miner_prefers_renderer_over_reach():
    renderer = FakeRenderer(_payload("conteudo renderizado " * 30, "browser-use"))
    reach = FakeReach(_payload("conteudo via reach " * 30, "jina-reader"))
    miner = WebMiner(
        anti_block=AntiBlockSystem(min_delay=0, max_delay=0),
        renderer=renderer,
        reach=reach,
    )
    results = await miner.mine_urls(["https://example.com"], client=FakeClient())
    assert results[0]["payload"]["metadata"]["provider"] == "browser-use"
    assert renderer.calls == 1


@pytest.mark.asyncio
async def test_miner_without_adapters_keeps_static_content():
    miner = WebMiner(anti_block=AntiBlockSystem(min_delay=0, max_delay=0))
    results = await miner.mine_urls(["https://example.com"], client=FakeClient())
    assert len(results) == 1
    assert "oi" in results[0]["content"]
