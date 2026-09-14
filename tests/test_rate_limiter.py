"""Testes do limitador de taxa em memória (sliding window por IP)."""
from __future__ import annotations

import time

from src.security.rate_limiter import InMemoryRateLimiter


def test_rate_limiter_allowance():
    limiter = InMemoryRateLimiter(requests_limit=2, window_seconds=10)
    ip = "192.168.1.1"
    assert limiter.is_allowed(ip) is True
    assert limiter.is_allowed(ip) is True
    assert limiter.is_allowed(ip) is False


def test_rate_limiter_window_expiry():
    limiter = InMemoryRateLimiter(requests_limit=1, window_seconds=0.1)
    ip = "10.0.0.1"
    assert limiter.is_allowed(ip) is True
    assert limiter.is_allowed(ip) is False
    time.sleep(0.15)
    assert limiter.is_allowed(ip) is True


def test_rate_limiter_tracks_ips_independently():
    limiter = InMemoryRateLimiter(requests_limit=1, window_seconds=60)
    assert limiter.is_allowed("1.1.1.1") is True
    assert limiter.is_allowed("2.2.2.2") is True
    assert limiter.is_allowed("1.1.1.1") is False


def test_clear_stale_ips():
    limiter = InMemoryRateLimiter(requests_limit=5, window_seconds=0.05)
    limiter.is_allowed("9.9.9.9")
    time.sleep(0.1)
    assert limiter.clear_stale_ips() == 1
    assert limiter.is_allowed("9.9.9.9") is True
