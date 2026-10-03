"""Testes do adaptador AgentReach (sem rede real)."""
from __future__ import annotations

import pytest

from src.miner.agent_reach import AgentReach


class FakeResponse:
    def __init__(self, status: int, text: str) -> None:
        self.status_code = status
        self.text = text


class FakeClient:
    def __init__(self, response: FakeResponse) -> None:
        self._response = response

    async def get(self, url, headers=None, follow_redirects=None):
        return self._response


def test_available_tools_reports_expected_keys():
    tools = AgentReach.available_tools()
    for key in ("agent-reach", "yt-dlp", "gh", "feedparser", "jina-reader"):
        assert key in tools
    assert tools["jina-reader"] is True


@pytest.mark.asyncio
async def test_read_web_returns_payload():
    long_text = "conteudo limpo " * 40
    reach = AgentReach()
    client = FakeClient(FakeResponse(200, long_text))
    payload = await reach.read_web("https://example.com", client=client)  # type: ignore[arg-type]
    assert payload is not None
    assert payload["metadata"]["provider"] == "jina-reader"
    assert payload["source_url"] == "https://example.com"
    assert len(payload["content"]) > 200


@pytest.mark.asyncio
async def test_read_web_short_content_returns_none():
    reach = AgentReach()
    client = FakeClient(FakeResponse(200, "curto"))
    assert await reach.read_web("https://example.com", client=client) is None  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_read_web_http_error_returns_none():
    reach = AgentReach()
    client = FakeClient(FakeResponse(503, "erro " * 100))
    assert await reach.read_web("https://example.com", client=client) is None  # type: ignore[arg-type]


def test_clean_vtt_strips_timestamps_and_tags():
    vtt = (
        "WEBVTT\n\n"
        "00:00:00.000 --> 00:00:02.000\n"
        "<c>Olá mundo</c>\n\n"
        "00:00:02.000 --> 00:00:04.000\n"
        "<c>Olá mundo</c>\n"
    )
    cleaned = AgentReach._clean_vtt(vtt)
    assert "WEBVTT" not in cleaned
    assert "-->" not in cleaned
    assert "<c>" not in cleaned
    assert cleaned == "Olá mundo"


@pytest.mark.asyncio
async def test_read_youtube_without_ytdlp_returns_none(monkeypatch):
    monkeypatch.setattr("src.miner.agent_reach.shutil.which", lambda name: None)
    reach = AgentReach()
    assert await reach.read_youtube("https://youtube.com/watch?v=x") is None


@pytest.mark.asyncio
async def test_read_rss_without_feedparser_returns_none(monkeypatch):
    monkeypatch.setattr(AgentReach, "_has_module", staticmethod(lambda name: False))
    reach = AgentReach()
    assert await reach.read_rss("https://example.com/feed.xml") is None


@pytest.mark.asyncio
async def test_fetch_dispatches_youtube(monkeypatch):
    reach = AgentReach()
    sentinel = {"source_url": "https://youtu.be/x", "content": "transcricao", "title": "", "metadata": {}, "payload": None}

    async def fake_youtube(url):
        return sentinel

    monkeypatch.setattr(reach, "read_youtube", fake_youtube)
    assert await reach.fetch("https://youtu.be/x") is sentinel


@pytest.mark.asyncio
async def test_fetch_falls_back_to_web(monkeypatch):
    reach = AgentReach()
    sentinel = {"source_url": "https://example.com", "content": "web", "title": "", "metadata": {}, "payload": None}

    async def fake_web(url, client=None):
        return sentinel

    monkeypatch.setattr(reach, "read_web", fake_web)
    assert await reach.fetch("https://example.com") is sentinel
