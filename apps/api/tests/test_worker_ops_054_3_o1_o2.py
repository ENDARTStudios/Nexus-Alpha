"""Testes das tasks operacionais #054.3 (retry 429), O1 (lock do worker) e O2 (env loader).

Offline: cliente HTTP falso, nenhum acesso de rede; asyncio via asyncio.run().
"""
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from scripts.worker_cycle import _bounded_retry_after, worker_lock
from src.ops.space_env import nexus_api_token, space_base_url


class _FakeResponse:
    def __init__(self, status_code: int, headers: dict | None = None):
        self.status_code = status_code
        self.headers = headers or {}


class _FakeClient:
    """Cliente httpx falso: devolve as respostas na ordem; registra sleeps."""

    def __init__(self, responses: list[_FakeResponse]):
        self._responses = list(responses)
        self.calls = 0
        self.sleeps: list[float] = []

    async def post(self, *args, **kwargs):
        self.calls += 1
        return self._responses.pop(0)


def _sleep_monkeypatched(monkeypatch) -> list[float]:
    recorded: list[float] = []

    async def _no_sleep(seconds: float):
        recorded.append(seconds)

    monkeypatch.setattr("scripts.worker_cycle.asyncio.sleep", _no_sleep)
    return recorded


# --- #054.3: _bounded_retry_after ------------------------------------------------

@pytest.mark.parametrize(
    "raw,expected",
    [
        (None, 5.0),          # sem header -> default
        ("12", 12.0),         # header numérico respeitado
        ("99", 30.0),         # teto de 30s
        ("garbage", 5.0),     # header inválido -> default
        ("-5", 0.0),          # negativo -> 0
    ],
)
def test_bounded_retry_after(raw, expected):
    assert _bounded_retry_after(raw) == expected


# --- #054.3: 429 respeita Retry-After e reenvia; 4xx reais não são retentáveis ----

def test_post_ingest_retries_429_with_retry_after(monkeypatch):
    from scripts.worker_cycle import _post_ingest_with_retry

    recorded = _sleep_monkeypatched(monkeypatch)
    client = _FakeClient([
        _FakeResponse(429, {"Retry-After": "7"}),
        _FakeResponse(200),
    ])

    async def run():
        return await _post_ingest_with_retry(client, "https://space/api/ingest", {"source_url": "u"}, {})

    response = asyncio.run(run())
    assert response.status_code == 200
    assert client.calls == 2
    assert recorded == [7.0]


def test_post_ingest_gives_up_after_persistent_429(monkeypatch):
    from scripts.worker_cycle import _post_ingest_with_retry

    recorded = _sleep_monkeypatched(monkeypatch)
    client = _FakeClient([_FakeResponse(429, {"Retry-After": "1"}) for _ in range(5)])

    async def run():
        return await _post_ingest_with_retry(client, "https://space/api/ingest", {"source_url": "u"}, {})

    response = asyncio.run(run())
    assert response.status_code == 429
    assert client.calls == 3  # tentativa inicial + 2 retries (max_retries=2)
    assert len(recorded) == 2


def test_post_ingest_does_not_retry_401(monkeypatch):
    from scripts.worker_cycle import _post_ingest_with_retry

    recorded = _sleep_monkeypatched(monkeypatch)
    client = _FakeClient([_FakeResponse(401)])

    async def run():
        return await _post_ingest_with_retry(client, "https://space/api/ingest", {"source_url": "u"}, {})

    response = asyncio.run(run())
    assert response.status_code == 401
    assert client.calls == 1
    assert recorded == []


# --- O1: lock exclusivo com timeout por mtime -------------------------------------

def test_worker_lock_acquire_and_release(tmp_path: Path):
    lock = tmp_path / "worker.lock"
    with worker_lock(lock):
        assert lock.exists()
        assert lock.read_text(encoding="utf-8").strip().isdigit()
    assert not lock.exists()


def test_worker_lock_refuses_concurrent(tmp_path: Path):
    lock = tmp_path / "worker.lock"
    with worker_lock(lock):
        with pytest.raises(SystemExit, match="O1"):
            with worker_lock(lock):
                pass


def test_worker_lock_replaces_stale_orphan(tmp_path: Path):
    lock = tmp_path / "worker.lock"
    lock.write_text("999999", encoding="utf-8")
    very_old = time.time() - 4 * 60 * 60  # 4h atrás — além do stale de 3h
    import os

    os.utime(lock, (very_old, very_old))
    with worker_lock(lock):
        assert lock.read_text(encoding="utf-8").strip() != "999999"


# --- O2: loader canônico de ambiente ----------------------------------------------

def test_space_base_url_prefers_hf_and_strips_slash():
    assert space_base_url({"HF_SPACE_URL": "https://space.hf.space/", "NEXUS_SPACE_URL": "https://other"}) == "https://space.hf.space"


def test_space_base_url_falls_back_to_nexus():
    assert space_base_url({"NEXUS_SPACE_URL": "https://via-nexus.hf.space"}) == "https://via-nexus.hf.space"


def test_space_base_url_empty_when_absent():
    assert space_base_url({}) == ""
    assert nexus_api_token({}) == ""
