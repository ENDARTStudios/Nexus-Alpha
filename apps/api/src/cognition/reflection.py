"""Nexus-Alpha — Worker de auto-reflexão e desempate web.

Executa ciclos periódicos que:
1. Detectam contradições no grafo de conhecimento (Cypher `CONTRADICTION_QUERY`).
2. Disparão mineração focada para resolver cada contradição.
3. Atualizam o grafo com o resultado de maior reputação.

Pode ser usado de forma síncrona (chamada direta) ou agendada.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from ..database.graph_connector import GraphConnector
from ..miner.web_miner import WebMiner
from ..miner.security_protocol import SecurityProtocol
from ..miner.quarantine import QuarantineStore
from ..cognition.extractor import EntityExtractor
from ..cognition.rag_engine import RAGEngine

logger = logging.getLogger(__name__)


class ReflectionWorker:
    def __init__(
        self,
        graph: Optional[GraphConnector] = None,
        rag: Optional[RAGEngine] = None,
        security: Optional[SecurityProtocol] = None,
        extractor: Optional[EntityExtractor] = None,
        miner: Optional[WebMiner] = None,
        quarantine: Optional[QuarantineStore] = None,
    ) -> None:
        self.graph = graph or GraphConnector()
        self.security = security or SecurityProtocol()
        self.extractor = extractor or EntityExtractor()
        self.miner = miner or WebMiner()
        self.quarantine = quarantine or QuarantineStore()
        self.rag = rag or RAGEngine(
            miner=self.miner,
            security=self.security,
            extractor=self.extractor,
            quarantine=self.quarantine,
        )

    async def detect(self) -> list[dict[str, Any]]:
        try:
            contradictions = await self.graph.detect_contradictions()
        except Exception as exc:
            logger.error("Falha ao consultar Neo4j: %s", exc)
            return []
        logger.info("Auto-reflexão: %d contradição(ões) detectada(s).", len(contradictions))
        return contradictions

    async def resolve(self, contradiction: dict[str, Any]) -> dict[str, Any]:
        origem = contradiction.get("origem", "")
        destino = contradiction.get("destino", "")
        query = f"{origem} {destino} o que é fato"
        seed_urls = [
            "https://pt.wikipedia.org/wiki/Intelig%C3%AAncia_artificial",
            "https://pt.wikipedia.org/wiki/Intelig%C3%AAncia_artificial",
            "https://pt.wikipedia.org/wiki/Intelig%C3%AAncia_artificial",
        ]
        candidates = await self.miner.mine_urls(seed_urls)
        best: Optional[dict[str, Any]] = None
        for item in candidates:
            url = item["payload"]["source_url"]
            score = self.security.confidence(url, item["content"])
            item["payload"]["domain_score"] = score
            if best is None or score > best["payload"]["domain_score"]:
                best = item

        if best is None:
            return {"status": "sem_fontes", "contradiction": contradiction}

        payload = self.extractor.enrich_payload(best["payload"])
        if payload["domain_score"] >= self.security.min_domain_score:
            try:
                await self.graph.ingest_payload(payload)
                return {"status": "desempatado", "winner": payload["source_url"], "score": payload["domain_score"]}
            except Exception as exc:
                logger.error("Falha ao persistir desempate: %s", exc)
        self.quarantine.put(payload, reason="desempate_insuficiente", score=payload["domain_score"])
        return {"status": "quarentena", "winner": payload["source_url"], "score": payload["domain_score"]}

    async def run_once(self) -> dict[str, Any]:
        contradictions = await self.detect()
        results = []
        for c in contradictions[:5]:
            results.append(await self.resolve(c))
        return {"contradictions_found": len(contradictions), "resolutions": results}

    async def run_loop(self, interval_seconds: int = 86400) -> None:
        logger.info("ReflectionWorker iniciado (intervalo=%ds).", interval_seconds)
        while True:
            try:
                summary = await self.run_once()
                logger.info("Ciclo concluído: %s", summary)
            except Exception as exc:
                logger.error("Falha no ciclo de reflexão: %s", exc)
            await asyncio.sleep(interval_seconds)


if __name__ == "__main__":
    async def _demo() -> None:
        worker = ReflectionWorker()
        result = await worker.run_once()
        print(result)

    asyncio.run(_demo())