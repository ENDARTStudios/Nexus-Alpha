"""Testes do ProxyRotator."""
from __future__ import annotations

from pathlib import Path

from src.miner.web_miner import ProxyRotator


def test_proxy_rotator_round_robin(tmp_path: Path):
    proxy_file = tmp_path / "proxies.txt"
    proxy_file.write_text("http://1.1.1.1:8080\nhttp://2.2.2.2:8080\n# comment\n", encoding="utf-8")

    rotator = ProxyRotator(proxy_file=str(proxy_file), enabled=True)
    seen = [rotator.next() for _ in range(4)]
    assert seen[0] == "http://1.1.1.1:8080"
    assert seen[1] == "http://2.2.2.2:8080"
    assert seen[2] == "http://1.1.1.1:8080"


def test_proxy_rotator_report_failure_removes_proxy(tmp_path: Path):
    proxy_file = tmp_path / "proxies.txt"
    proxy_file.write_text("http://1.1.1.1:8080\nhttp://2.2.2.2:8080\n", encoding="utf-8")
    rotator = ProxyRotator(proxy_file=str(proxy_file), enabled=True)
    rotator.report_failure("http://1.1.1.1:8080")
    assert "http://1.1.1.1:8080" not in rotator.proxies
    assert rotator.next() == "http://2.2.2.2:8080"


def test_proxy_rotator_disabled_returns_none():
    rotator = ProxyRotator(enabled=False)
    assert rotator.next() is None