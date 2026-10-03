"""Nexus-Alpha — Filtro de triangulação de fontes (anti-fake-news).

Promove uma tripla semântica a "VERIFIED_FACT" somente quando:
- aparece em `min_sources` domínios independentes;
- a confiança média ≥ `auto_quarantine_threshold`.

Caso contrário, devolve "QUARANTINE" para armazenamento isolado.
"""
from __future__ import annotations

import logging
from urllib.parse import urlparse


logger = logging.getLogger(__name__)


class TriangulationFilter:
    def __init__(self, min_sources: int = 3, threshold: float = 0.5) -> None:
        self.min_sources = min_sources
        self.auto_quarantine_threshold = threshold

    @staticmethod
    def _extract_domain(url: str) -> str:
        try:
            netloc = urlparse(url).netloc
            return netloc.replace("www.", "") or "unknown_domain"
        except Exception:
            return "unknown_domain"

    def process_discovered_triplets(
        self,
        incoming_triplet: dict,
        historical_records: list[dict],
    ) -> dict:
        unique_domains: set[str] = set()
        total_confidence = float(incoming_triplet.get("confidence", 0.0))
        current_domain = self._extract_domain(incoming_triplet.get("source_url", ""))
        unique_domains.add(current_domain)

        for record in historical_records:
            domain = self._extract_domain(record.get("source_url", ""))
            unique_domains.add(domain)
            total_confidence += float(record.get("confidence", 0.0))

        total = len(historical_records) + 1
        avg_confidence = total_confidence / total if total else 0.0
        independent_source_count = len(unique_domains)

        logger.info(
            "Triangulação: %d domínios independentes, confiança média %.2f",
            independent_source_count, avg_confidence,
        )

        if independent_source_count >= self.min_sources and avg_confidence >= self.auto_quarantine_threshold:
            return {
                "status": "VERIFIED_FACT",
                "action": "INSERT_INTO_GRAPH",
                "final_confidence": round(avg_confidence, 2),
                "reason": f"Fato confirmado por {independent_source_count} fontes distintas na Web.",
            }
        return {
            "status": "QUARANTINE",
            "action": "STORE_IN_ISOLATION",
            "final_confidence": round(avg_confidence, 2),
            "reason": "Fontes independentes insuficientes ou nível de confiança médio abaixo do limiar de segurança.",
        }


if __name__ == "__main__":
    f = TriangulationFilter(min_sources=3, threshold=0.6)
    fact = {
        "subject": "Grafeno", "predicate": "CONDUZ", "object": "Eletricidade",
        "confidence": 0.9, "source_url": "https://site-cientifico-a.com",
    }
    history = [
        {"source_url": "https://universidade-b.edu", "confidence": 0.85},
        {"source_url": "https://portal-tecnologico-c.org", "confidence": 0.70},
    ]
    print(f.process_discovered_triplets(fact, history))