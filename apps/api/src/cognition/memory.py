"""Nexus-Alpha — Memória local híbrida (vetorial + grafo leve).

Implementação in-process que evita dependência de serviços externos durante
desenvolvimento/testes. O pipeline é o mesmo consumido pelo
GraphConnector/VectorConnector: armazena conceitos, relações e embeddings.
"""
from __future__ import annotations

import logging
import math
from collections import defaultdict
from typing import Any, Optional

logger = logging.getLogger(__name__)


class LocalMemory:
    """Memória leve: conceitos + relacionamentos + embeddings hash-based."""

    def __init__(self) -> None:
        self.concepts: dict[str, dict[str, Any]] = {}
        self.relations: list[dict[str, Any]] = []
        self.embeddings: dict[str, list[float]] = defaultdict(lambda: [])

    def upsert_concept(self, name: str, attrs: Optional[dict] = None) -> None:
        attrs = attrs or {}
        if name not in self.concepts:
            self.concepts[name] = {"name": name, "count": 0, **attrs}
        self.concepts[name]["count"] += 1

    def add_relation(self, subject: str, predicate: str, obj: str, confidence: float, source: str) -> None:
        self.relations.append({
            "subject": subject,
            "predicate": predicate,
            "object": obj,
            "confidence": confidence,
            "source": source,
        })
        self.upsert_concept(subject)
        self.upsert_concept(obj)

    def related(self, concept: str, max_hops: int = 2) -> list[dict[str, Any]]:
        out = []
        for r in self.relations:
            if r["subject"] == concept or r["object"] == concept:
                out.append(r)
        return out

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        q_tokens = set(query.lower().split())
        scored = []
        for r in self.relations:
            score = sum(1 for t in q_tokens if t in r["subject"].lower() or t in r["object"].lower())
            if score:
                scored.append({**r, "score": score})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def stats(self) -> dict[str, int]:
        return {"concepts": len(self.concepts), "relations": len(self.relations)}