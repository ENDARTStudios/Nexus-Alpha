"""Nexus-Alpha — Resolução vetorial de entidades (colisão semântica dinâmica).

Complementa o ``SemanticCanonicalizer`` (dicionário léxico) resolvendo variações
textuais que o dicionário não cobre: entidades com alta proximidade vetorial
(``>= similarity_threshold``) colapsam sob o mesmo termo canônico, forçando o
acúmulo de confirmações no Neo4j para a promoção de ``verified_facts``.

Usa o embedding local determinístico (``src/cognition/embeddings.py``), sem
dependências externas. O cache de clusters é volátil (por instância/rodada).
"""
from __future__ import annotations

import logging
from typing import Dict, List

from .embeddings import cosine_similarity, get_embedding


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EntityResolver:
    def __init__(self, similarity_threshold: float = 0.80, max_clusters: int = 5000) -> None:
        self.similarity_threshold = similarity_threshold
        self.max_clusters = max_clusters
        # {termo_canonico: vetor_embedding}
        self.canonical_clusters: Dict[str, List[float]] = {}

    def resolve_entity(self, raw_entity: str) -> str:
        """Funde a entidade em um cluster existente (se similar) ou cria um novo."""
        entity_clean = (raw_entity or "").strip()
        if not entity_clean:
            return ""

        try:
            entity_vector = get_embedding(entity_clean)

            best_match = None
            best_score = -1.0
            for canonical_term, cluster_vector in self.canonical_clusters.items():
                score = cosine_similarity(entity_vector, cluster_vector)
                if score > best_score:
                    best_score = score
                    best_match = canonical_term

            if best_match is not None and best_score >= self.similarity_threshold:
                logger.info(
                    "RESOLVER: '%s' fundida em '%s' (sim=%.2f)",
                    entity_clean, best_match, best_score,
                )
                return best_match

            if len(self.canonical_clusters) < self.max_clusters:
                self.canonical_clusters[entity_clean] = entity_vector
            return entity_clean
        except Exception as exc:
            logger.error("Erro ao resolver entidade via embedding: %s", exc)
            return entity_clean

    def resolve_triplet(self, triplet: dict) -> dict:
        """Aplica a resolução em ``subject`` e ``object`` de uma tripla."""
        triplet["subject"] = self.resolve_entity(triplet.get("subject", ""))
        triplet["object"] = self.resolve_entity(triplet.get("object", ""))
        return triplet

    def clear_session_cache(self) -> None:
        """Limpa o cache entre rodadas para evitar desvios semânticos acumulados."""
        self.canonical_clusters.clear()
