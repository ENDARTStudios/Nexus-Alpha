"""#048.10H.4 — testes do retry seguro de ingest (mock, sem rede)."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scripts.worker_cycle as worker  # noqa: E402


class _Resp:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        self.text = ""


class _Client:
    def __init__(self, statuses) -> None:
        self._statuses = list(statuses)
        self.calls = 0

    async def post(self, url, json=None, headers=None, timeout=None):
        self.calls += 1
        return _Resp(self._statuses.pop(0) if self._statuses else 200)


def _run(client):
    return asyncio.run(worker._post_ingest_with_retry(client, "u", {"source_url": "x"}, {}))


def test_retry_on_502_then_success():
    client = _Client([502, 200])
    resp = _run(client)
    assert resp.status_code == 200
    assert client.calls == 2


def test_no_retry_on_403():
    client = _Client([403, 200])
    resp = _run(client)
    assert resp.status_code == 403
    assert client.calls == 1


def test_no_retry_on_422():
    client = _Client([422, 200])
    resp = _run(client)
    assert resp.status_code == 422
    assert client.calls == 1


def test_bounded_retries_exhausted():
    client = _Client([502, 502, 502])
    resp = _run(client)
    assert resp.status_code == 502
    assert client.calls == 3  # max_retries=2 -> 3 tentativas
