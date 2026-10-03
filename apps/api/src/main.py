"""Nexus-Alpha — Orquestrador central (NexusAlphaCore).

Une minerador, raciocínio, NLP, triangulação e memórias híbridas em um único
ciclo autônomo. Pode ser executado standalone (`python -m src.main`) ou
embutido em workers / cron.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional

from src.cognition.nlp_extractor import NLPExtractor
from src.cognition.reasoning_engine import ReasoningEngine
from src.cognition.embeddings import hash_embedding
from src.cognition.canonicalizer import SemanticCanonicalizer
from src.cognition.entity_resolver import EntityResolver
from src.cognition.llm_extractor import LLMCanonicalExtractor
from src.database.graph_connector import GraphConnector
from src.database.vector_connector import VectorConnector
from src.miner.anti_block import AntiBlockSystem
from src.miner.quarantine import QuarantineStore
from src.miner.web_miner import WebMiner
from src.miner.security_protocol import SecurityProtocol
from src.security.triangulation import TriangulationFilter


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("nexus.core")


class NexusAlphaCore:
    def __init__(
        self,
        graph: Optional[GraphConnector] = None,
        vector: Optional[VectorConnector] = None,
        security: Optional[TriangulationFilter] = None,
        reasoning: Optional[ReasoningEngine] = None,
        nlp: Optional[NLPExtractor] = None,
        miner: Optional[WebMiner] = None,
        quarantine: Optional[QuarantineStore] = None,
    ) -> None:
        logger.info("Iniciando o ecossistema central Nexus-Alpha...")
        self.anti_block = AntiBlockSystem()
        self.reasoning = reasoning or ReasoningEngine()
        self.nlp = nlp or NLPExtractor()
        self.canonicalizer = SemanticCanonicalizer()
        self.entity_resolver = EntityResolver()
        self.llm_extractor = LLMCanonicalExtractor()
        self.security = security or TriangulationFilter(min_sources=2, threshold=0.5)
        self.miner = miner or WebMiner()
        self.protocol = SecurityProtocol()
        self.quarantine = quarantine or QuarantineStore()
        self.graph_db = graph or GraphConnector()
        self.vector_db = vector or VectorConnector()

    async def execute_autonomous_cycle(
        self,
        target_concept: str,
        historical_records: Optional[list[dict]] = None,
        simulated_mined_text: Optional[str] = None,
        source_url: str = "https://wikipedia.org",
    ) -> dict:
        historical_records = historical_records or []
        logger.info("=== CICLO DE EVOLUÇÃO PARA: %s ===", target_concept)

        # 1. Chain-of-Thought + knowledge-gap
        plan = self.reasoning.evaluate_knowledge_gap(target_concept, [])
        if plan.decision == "AUTO_REFLEXAO":
            logger.info("Conhecimento local consolidado. Pulando etapa de busca externa.")
            return {"status": "skipped", "reason": "knowledge_dense"}

        # 2. Mineração disfarçada
        logger.info("Gerando cabeçalhos furtivos para a query: %s", plan.target_queries)
        self.anti_block.generate_headers(source_url)
        await self.anti_block.dynamic_delay()

        mined_text = simulated_mined_text or (
            "As Redes Neurais artificiais mimetizam o cérebro humano e formam a "
            "base da Inteligência Artificial moderna."
        )

        # 3. Extração semântica: LLM canônico (opt-in) com fallback heurístico
        logger.info("Extraindo triplas (LLM canônico se configurado; senão heurístico)...")
        triplets = self.llm_extractor.extract_canonical_triplets(mined_text)
        if not triplets:
            triplets = self.nlp.extract_triplets(mined_text, target_concept)
        if not triplets:
            logger.warning("Nenhuma tripla pôde ser extraída.")
            return {"status": "no_triplets"}
        triplets = [self.canonicalizer.canonicalize_triplet(t) for t in triplets]
        triplets = [self.entity_resolver.resolve_triplet(t) for t in triplets]

        # 4. Triangulação e persistência
        verified = 0
        quarantined = 0
        for triplet in triplets:
            triplet["source_url"] = source_url
            decision = self.security.process_discovered_triplets(triplet, historical_records)

            if decision["status"] == "VERIFIED_FACT":
                verified += 1
                logger.info("Fato verificado! %s -> %s", triplet["subject"], triplet["object"])
                payload: dict[str, Any] = {
                    "source_url": source_url,
                    "timestamp": int(time.time()),
                    "domain_score": self.protocol.confidence(source_url, mined_text),
                    "extracted_entities": [triplet],
                }
                try:
                    await self.graph_db.connect()
                    await self.graph_db.ingest_payload(payload)
                    await self.graph_db.close()
                except Exception as exc:
                    logger.error("Erro no Neo4j: %s", exc)
                try:
                    self.vector_db.store_memory(
                        point_id=int(time.time()) % (10 ** 8),
                        vector=hash_embedding(
                            mined_text, getattr(self.vector_db, "embedding_dim", 384)
                        ),
                        payload={"text": mined_text, "url": source_url},
                    )
                except Exception as exc:
                    logger.error("Erro no Vector DB: %s", exc)
            else:
                quarantined += 1
                logger.warning("Quarentena: %s", decision["reason"])
                self.quarantine.put({"triplet": triplet, "url": source_url}, reason=decision["status"], score=decision["final_confidence"])

        logger.info("=== CICLO FINALIZADO: %d verificados, %d quarentenados ===", verified, quarantined)
        return {"status": "done", "verified": verified, "quarantined": quarantined}


if __name__ == "__main__":
    core = NexusAlphaCore()
    asyncio.run(core.execute_autonomous_cycle("Inteligência Artificial"))