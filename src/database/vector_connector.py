"""Nexus-Alpha — Conector de Vector DB (Qdrant Cloud / Milvus / in-memory).

Esta versão prioriza Qdrant Cloud (camada gratuita) carregando credenciais de
`config/settings.yaml` e variáveis de ambiente. Expõe a API simplificada
`store_memory` / `query_similarity` e mantém `upsert` / `search` legados.
"""
from __future__ import annotations

import hashlib
import logging
import os
from typing import Any, Optional

import yaml


logger = logging.getLogger(__name__)


class _InMemoryStore:
    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = sum(x * x for x in a) ** 0.5
        nb = sum(y * y for y in b) ** 0.5
        return dot / (na * nb) if na and nb else 0.0

    def upsert(self, point_id: str, vector: list[float], payload: dict[str, Any]) -> None:
        self._store[point_id] = {"vector": vector, "payload": payload}

    def search(self, vector: list[float], top_k: int) -> list[dict[str, Any]]:
        scored = []
        for pid, item in self._store.items():
            scored.append({
                "id": pid,
                "score": self._cosine(vector, item["vector"]),
                "payload": item["payload"],
            })
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def count(self) -> int:
        return len(self._store)


class VectorConnector:
    """Interface Qdrant/Milvus/in-memory."""

    def __init__(
        self,
        config_path: str = "config/settings.yaml",
        backend: Optional[str] = None,
    ) -> None:
        self.config_path = config_path
        self.client: Any = None
        self.backend = backend or "memory"
        self.collection_name: str = "nexus_semantic_memory"
        self.embedding_dim: int = 384
        self.qdrant_url: Optional[str] = None
        self.qdrant_api_key: Optional[str] = None
        self._mem = _InMemoryStore()
        self._load_config()
        self._init_backend()

    def _load_config(self) -> None:
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            vec = cfg.get("database", {}).get("vector", {})
            self.collection_name = vec.get("collection_name", self.collection_name)
            self.embedding_dim = int(vec.get("embedding_dim", self.embedding_dim))
            self.qdrant_url = os.environ.get("QDRANT_HOST") or vec.get("uri")
            self.qdrant_api_key = os.environ.get("QDRANT_API_KEY")
            if not self.backend:
                uri = (self.qdrant_url or "").lower()
                if "qdrant" in uri or uri.startswith("http"):
                    self.backend = "qdrant"
                elif "milvus" in uri:
                    self.backend = "milvus"
                else:
                    self.backend = "memory"
        except Exception as exc:
            logger.error("Falha ao carregar configurações vetoriais: %s", exc)
            self.backend = "memory"

    def _init_backend(self) -> None:
        if self.backend == "qdrant":
            try:
                from qdrant_client import QdrantClient
                from qdrant_client.models import Distance, VectorParams

                self.client = QdrantClient(
                    url=self.qdrant_url,
                    api_key=self.qdrant_api_key,
                    timeout=15.0,
                )
                if not self.client.collection_exists(collection_name=self.collection_name):
                    self.client.create_collection(
                        collection_name=self.collection_name,
                        vectors_config=VectorParams(size=self.embedding_dim, distance=Distance.COSINE),
                    )
                logger.info("Qdrant Cloud conectado: %s/%s", self.qdrant_url, self.collection_name)
            except Exception as exc:
                logger.warning("Qdrant indisponível (%s) — usando in-memory.", exc)
                self.backend = "memory"
        elif self.backend == "milvus":
            try:
                from pymilvus import MilvusClient
                self.client = MilvusClient(uri=self.qdrant_url or "")
                if not self.client.has_collection(self.collection_name):
                    self.client.create_collection(
                        collection_name=self.collection_name,
                        dimension=self.embedding_dim,
                    )
                logger.info("Milvus conectado: %s/%s", self.qdrant_url, self.collection_name)
            except Exception as exc:
                logger.warning("Milvus indisponível (%s) — usando in-memory.", exc)
                self.backend = "memory"
        else:
            logger.info("VectorConnector em modo in-memory.")

    def _ensure_collection(self) -> None:
        if self.backend == "qdrant" and self.client is not None:
            from qdrant_client.models import Distance, VectorParams
            if not self.client.collection_exists(collection_name=self.collection_name):
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=self.embedding_dim, distance=Distance.COSINE),
                )

    @staticmethod
    def _vector_id(payload: dict[str, Any]) -> str:
        raw = f"{payload.get('source_url','')}::{payload.get('timestamp','')}::{payload.get('title','')}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def store_memory(self, point_id: int, vector: list[float], payload: dict[str, Any]) -> bool:
        """API simplificada usada pelo pipeline HF Spaces."""
        if self.backend == "qdrant" and self.client is not None:
            try:
                from qdrant_client.models import PointStruct
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=[PointStruct(id=point_id, vector=vector, payload=payload)],
                )
                logger.info("Fragmento semântico %s salvo na memória vetorial.", point_id)
                return True
            except Exception as exc:
                logger.error("Erro ao salvar na memória vetorial: %s", exc)
                return False
        self._mem.upsert(str(point_id), vector, payload)
        return True

    def query_similarity(self, query_vector: list[float], limit: int = 3) -> list[dict[str, Any]]:
        if self.backend == "qdrant" and self.client is not None:
            try:
                hits = self.client.search(
                    collection_name=self.collection_name,
                    query_vector=query_vector,
                    limit=limit,
                )
                return [{"id": hit.id, "score": hit.score, "payload": hit.payload} for hit in hits]
            except Exception as exc:
                logger.error("Erro ao buscar similaridade vetorial: %s", exc)
                return []
        return self._mem.search(query_vector, limit)

    def upsert(self, payload: dict[str, Any], embedding: Optional[list[float]] = None) -> str:
        vec_id = self._vector_id(payload)
        point_id = int(hashlib.sha256(vec_id.encode()).hexdigest()[:8], 16) % (10 ** 8)
        self.store_memory(
            point_id=point_id,
            vector=embedding or [0.0] * self.embedding_dim,
            payload=payload,
        )
        return vec_id

    def search(self, query_embedding: list[float], top_k: int = 5) -> list[dict[str, Any]]:
        return self.query_similarity(query_embedding, limit=top_k)

    def count(self) -> int:
        if self.backend == "qdrant" and self.client is not None:
            return self.client.count(self.collection_name).count
        return self._mem.count()

    def backend_name(self) -> str:
        return self.backend


if __name__ == "__main__":
    connector = VectorConnector()
    if connector.backend == "memory":
        # Demonstração local sem Qdrant
        from qdrant_client import QdrantClient
        connector.client = QdrantClient(":memory:")
        connector.collection_name = "test_memory"
        connector._ensure_collection()
        mock_vector = [0.1] * 384
        mock_data = {"url": "https://exemplo.com", "text": "A computação assíncrona otimiza a IA."}
        connector.store_memory(point_id=1, vector=mock_vector, payload=mock_data)
        results = connector.query_similarity(query_vector=mock_vector, limit=1)
        print("Resultado da busca semântica simulada:", results)