"""Testes do VectorConnector em modo in-memory (sem dependência de Qdrant)."""
from __future__ import annotations

from src.database.vector_connector import VectorConnector


def test_vector_connector_memory_roundtrip(tmp_path):
    cfg = tmp_path / "settings.yaml"
    cfg.write_text(
        "database:\n  vector:\n    collection_name: test\n    embedding_dim: 4\n    uri: ''\n",
        encoding="utf-8",
    )
    vc = VectorConnector(config_path=str(cfg), backend="memory")
    assert vc.backend_name() == "memory"

    payload_a = {"source_url": "https://a", "timestamp": 1, "title": "A"}
    payload_b = {"source_url": "https://b", "timestamp": 2, "title": "B"}

    vc.store_memory(point_id=1, vector=[1.0, 0.0, 0.0, 0.0], payload=payload_a)
    vc.store_memory(point_id=2, vector=[0.0, 1.0, 0.0, 0.0], payload=payload_b)

    hits = vc.query_similarity([1.0, 0.0, 0.0, 0.0], limit=2)
    assert hits[0]["payload"]["source_url"] == "https://a"
    assert hits[1]["payload"]["source_url"] == "https://b"
    assert vc.count() == 2


def test_upsert_persists_and_returns_id(tmp_path):
    cfg = tmp_path / "settings.yaml"
    cfg.write_text(
        "database:\n  vector:\n    collection_name: test\n    embedding_dim: 4\n    uri: ''\n",
        encoding="utf-8",
    )
    vc = VectorConnector(config_path=str(cfg), backend="memory")
    vector_id = vc.upsert({"source_url": "https://x", "timestamp": 1, "title": "T"})
    assert isinstance(vector_id, str)
    assert vc.count() == 1