"""Testes da quarentena persistente."""
from __future__ import annotations

import json
from pathlib import Path

from src.miner.quarantine import QuarantineStore


def test_quarantine_put_and_list(tmp_path: Path):
    store = QuarantineStore(base_dir=tmp_path)
    store.put({"source_url": "https://x", "title": "A"}, reason="score baixo", score=0.2)
    store.put({"source_url": "https://y", "title": "B"}, reason="triangulação falhou", score=0.45)

    records = store.list_all()
    assert len(records) == 2
    assert records[0]["payload"]["source_url"] == "https://x"
    assert records[1]["score"] == 0.45


def test_quarantine_reprocess_filters_by_score(tmp_path: Path):
    store = QuarantineStore(base_dir=tmp_path)
    store.put({"source_url": "https://x"}, reason="ok", score=0.7)
    store.put({"source_url": "https://y"}, reason="fraco", score=0.2)

    candidates = list(store.reprocess_candidates(min_score=0.5))
    assert len(candidates) == 1
    assert candidates[0]["payload"]["source_url"] == "https://x"


def test_quarantine_clear(tmp_path: Path):
    store = QuarantineStore(base_dir=tmp_path)
    store.put({"source_url": "https://x"}, reason="ok", score=0.2)
    store.clear()
    assert store.list_all() == []
    assert not store.file_path.exists()


def test_quarantine_approve_and_discard(tmp_path: Path):
    store = QuarantineStore(base_dir=tmp_path)
    store.put({"source_url": "https://x"}, reason="fraco", score=0.1)
    first = store.list_all()[0]
    removed = store.approve_at(0)
    assert removed is not None
    assert store.list_all() == []
    # After removal, discard on empty should return None
    assert store.discard_at(0) is None