"""Testes do limitador de taxa em memória (sliding window por identidade)."""
from __future__ import annotations

import logging
import time

from src.security import rate_limiter as rl_module
from src.security.rate_limiter import InMemoryRateLimiter, fingerprint_secret


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


def test_clear_stale_keys():
    limiter = InMemoryRateLimiter(requests_limit=5, window_seconds=0.05)
    limiter.is_allowed("9.9.9.9")
    time.sleep(0.1)
    assert limiter.clear_stale_keys() == 1
    assert limiter.is_allowed("9.9.9.9") is True


def test_check_returns_retry_after_on_block():
    limiter = InMemoryRateLimiter(requests_limit=1, window_seconds=10)
    key = "ip:10.0.0.9"
    first = limiter.check(key)
    assert first.allowed is True
    assert first.retry_after_seconds == 0

    second = limiter.check(key)
    assert second.allowed is False
    assert 1 <= second.retry_after_seconds <= 10


def test_check_retry_after_counts_down_within_window():
    limiter = InMemoryRateLimiter(requests_limit=1, window_seconds=1)
    key = "ip:10.0.0.8"
    limiter.check(key)
    blocked = limiter.check(key)
    assert blocked.allowed is False
    time.sleep(0.5)
    later = limiter.check(key)
    assert later.retry_after_seconds <= blocked.retry_after_seconds


def test_identity_keys_are_independent():
    """IP e token no mesmo limiter não dividem cota (chaves são opacas)."""
    limiter = InMemoryRateLimiter(requests_limit=1, window_seconds=60)
    assert limiter.check("ip:1.1.1.1").allowed is True
    assert limiter.check("token:abc123").allowed is True
    assert limiter.check("ip:1.1.1.1").allowed is False
    assert limiter.check("token:abc123").allowed is False


def test_fingerprint_secret_is_stable_and_masks_secret():
    fp = fingerprint_secret("segredo-super-secreto")
    assert len(fp) == 12
    assert fp == fingerprint_secret("segredo-super-secreto")
    assert "segredo" not in fp
    assert fingerprint_secret("outro") != fp


def test_max_keys_evicts_least_recently_active(monkeypatch):
    clock = iter([1000.0, 1001.0, 1002.0, 1003.0])
    monkeypatch.setattr(rl_module.time, "time", lambda: next(clock))
    limiter = InMemoryRateLimiter(requests_limit=10, window_seconds=60, max_keys=3)
    limiter.check("a")
    limiter.check("b")
    limiter.check("c")
    decision = limiter.check("d")  # no teto: despeja LRU ('a') antes de inserir
    assert decision.allowed is True
    assert set(limiter.history) == {"b", "c", "d"}


def test_max_keys_purges_expired_before_evicting(monkeypatch):
    times = iter([1000.0, 1000.5, 1061.0, 1061.5])
    monkeypatch.setattr(rl_module.time, "time", lambda: next(times))
    limiter = InMemoryRateLimiter(requests_limit=10, window_seconds=60, max_keys=3)
    limiter.check("old1")
    limiter.check("old2")
    limiter.check("n1")  # abaixo do teto: entra sem purgar (purge é lazy, no teto)
    assert set(limiter.history) == {"old1", "old2", "n1"}
    limiter.check("n2")  # no teto: old1/old2 (>60s) purgadas antes de despejar LRU
    assert set(limiter.history) == {"n1", "n2"}


def test_key_count_never_grows_unbounded():
    limiter = InMemoryRateLimiter(requests_limit=10, window_seconds=60, max_keys=10)
    for i in range(100):
        limiter.check(f"ip:10.0.0.{i}")
    assert len(limiter.history) <= 10


def test_clear_stale_keys_keeps_active_windows():
    limiter = InMemoryRateLimiter(requests_limit=5, window_seconds=60, max_keys=100)
    limiter.check("ativa")
    limiter.history["expirada"] = [time.time() - 120]
    removed = limiter.clear_stale_keys()
    assert removed == 1
    assert "ativa" in limiter.history
    assert "expirada" not in limiter.history


def test_block_log_never_contains_raw_token(caplog):
    limiter = InMemoryRateLimiter(requests_limit=1, window_seconds=60)
    raw_token = "hf_raw_token_valor_secreto_nunca_logado"
    key = f"token:{fingerprint_secret(raw_token)}"
    with caplog.at_level(logging.WARNING, logger="src.security.rate_limiter"):
        limiter.check(key)
        limiter.check(key)  # bloqueio → loga a chave (fingerprint), nunca o cru
    assert raw_token not in caplog.text
    assert fingerprint_secret(raw_token) in caplog.text
