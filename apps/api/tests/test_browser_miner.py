"""Testes do adaptador BrowserMiner (sem browser-use instalado)."""
from __future__ import annotations

import pytest

from src.miner.browser_miner import BrowserMiner


def test_disabled_when_module_missing(monkeypatch):
    monkeypatch.setattr(BrowserMiner, "_has_module", staticmethod(lambda: False))
    miner = BrowserMiner()
    assert miner.available() is False


def test_disabled_when_api_key_absent(monkeypatch):
    monkeypatch.setattr(BrowserMiner, "_has_module", staticmethod(lambda: True))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    miner = BrowserMiner()
    assert miner.available() is False


def test_enabled_when_module_and_key_present(monkeypatch):
    monkeypatch.setattr(BrowserMiner, "_has_module", staticmethod(lambda: True))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    miner = BrowserMiner()
    assert miner.available() is True


@pytest.mark.asyncio
async def test_fetch_rendered_returns_none_when_disabled():
    miner = BrowserMiner(enabled=False)
    assert await miner.fetch_rendered("https://example.com") is None


@pytest.mark.asyncio
async def test_fetch_rendered_handles_import_error():
    # enabled=True força a tentativa de import; browser_use ausente -> None gracioso.
    miner = BrowserMiner(enabled=True)
    assert await miner.fetch_rendered("https://example.com") is None
