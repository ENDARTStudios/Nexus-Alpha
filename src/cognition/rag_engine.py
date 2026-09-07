"""Nexus-Alpha — RAG ativo: detecta lacunas na memória local e dispara scraping em tempo real."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from ..miner.web_miner import WebMiner
from ..miner.security_protocol import SecurityProtocol, VerificationResult
from ..miner.quarantine import QuarantineStore
from .reasoning import ChainOfThought, ReasoningTrace
from .extractor import EntityExtractor
from .memory import LocalMemory


logger = logging.getLogger(__name__)


class RAGEngine:
    """
    Pipeline completo:
    1. Consulta a memória local (`LocalMemory`) e o Vector DB.
    2. Se a similaridade for insuficiente (knowledge gap), minera a web.
    3. Triangula com `SecurityProtocol` (domain score + sensacionalismo).
    4. Quarentena fatos abaixo do limiar.
    5. Enriquece o payload via `EntityExtractor`.
    """

    def __init__(
        self,
        miner: Optional[WebMiner] = None,
        security: Optional[SecurityProtocol] = None,
        cot: Optional[ChainOfThought] = None,
        extractor: Optional[EntityExtractor] = None,
        memory: Optional[LocalMemory] = None,
        quarantine: Optional[QuarantineStore] = None,
        vector_db: Optional[Any] = None,
        min_relevance_score: float = 0.75,
        top_k: int = 5,
    ) -> None:
        self.miner = miner or WebMiner()
        self.security = security or SecurityProtocol()
        self.cot = cot or ChainOfThought()
        self.extractor = extractor or EntityExtractor()
        self.memory = memory or LocalMemory()
        self.quarantine = quarantine or QuarantineStore()
        self.vector_db = vector_db
        self.min_relevance_score = min_relevance_score
        self.top_k = top_k

    async def retrieve_or_search(self, query_text: str, query_vector: Optional[list] = None) -> dict:
        """
        Recuperação semântica ativa: consulta o Vector DB; se o score for
        menor que `min_relevance_score`, dispara mineração web e devolve o
        melhor bloco encontrado.
        """
        logger.info("RAG: analisando memória interna para '%s'", query_text)

        internal_hits: list[dict] = []
        if self.vector_db is not None and query_vector is not None:
            try:
                internal_hits = self.vector_db.query_similarity(query_vector, limit=2)
            except Exception as exc:
                logger.warning("Vector DB indisponível (%s) — seguindo com memória local.", exc)

        if internal_hits and internal_hits[0].get("score", 0.0) >= self.min_relevance_score:
            logger.info("RAG: conhecimento interno suficiente localizado.")
            payload = internal_hits[0].get("payload", {})
            return {
                "source": "internal_memory",
                "score": internal_hits[0]["score"],
                "content": payload.get("text") or payload.get("content", ""),
            }

        logger.warning("RAG: lacuna detectada — disparando busca externa ativa.")
        if self.miner is not None:
            search_url = f"https://duckduckgo.com/?q={query_text.replace(' ', '+')}"
            try:
                web_data = await self.miner.mine_urls([search_url])
            except Exception as exc:
                logger.error("RAG: falha no miner (%s)", exc)
                web_data = []
            if web_data and web_data[0].get("content"):
                return {
                    "source": "active_web_scraping",
                    "score": 1.0,
                    "content": web_data[0]["content"][:1000],
                }

        return {
            "source": "none",
            "score": 0.0,
            "content": "Nenhum conhecimento interno ou externo pôde ser recuperado.",
        }

    def _memory_hits(self, question: str) -> list[dict]:
        hits = self.memory.search(question, top_k=5)
        return hits if hits else []

    async def fetch_and_verify(self, queries: list[str]) -> list[dict]:
        candidates = await self.miner.mine_urls(queries[: self.top_k])
        approved: list[dict] = []
        for item in candidates:
            url = item.get("payload", {}).get("source_url", "")
            text = item.get("content", "")
            score = self.security.confidence(url, text)
            payload = item["payload"]
            payload["domain_score"] = score

            if score < self.security.min_domain_score:
                self.quarantine.put(payload, reason="domain_score abaixo do limiar", score=score)
                continue

            payload = self.extractor.enrich_payload(payload)

            # Triangulação: fatos isolados vão para quarentena
            fact_key = payload.get("title") or url
            result = self.security.triangulate(
                fact=fact_key,
                sources=[{"url": url, "text": text}],
            )
            if result.status.startswith("Hipótese"):
                self.quarantine.put(payload, reason=result.status, score=score)

            approved.append(item)
        return approved

    async def answer(
        self,
        question: str,
        seed_urls: list[str],
        local_knowledge: Optional[list[str]] = None,
    ) -> ReasoningTrace:
        local_knowledge = local_knowledge or []
        hits = self._memory_hits(question)
        trace = await self.cot.reason(
            goal=question,
            subproblems=[
                f"Verificar se a memória local cobre: {question}",
                "Minerar fontes web complementares",
                "Triangular e sintetizar resposta final",
            ],
        )

        if hits:
            trace.steps.append(
                await self.cot._run_subproblem(
                    f"Memória local retornou {len(hits)} relações relevantes"
                )
            )
        elif not local_knowledge:
            trace.steps.append(
                await self.cot._run_subproblem("Base local insuficiente — acionando RAG ativo")
            )
            sources = await self.fetch_and_verify(seed_urls)
            for src in sources:
                score = src["payload"]["domain_score"]
                trace.steps.append(
                    await self.cot._run_subproblem(
                        f"Fonte {src['payload']['source_url']} (score={score})"
                    )
                )
                for ent in src["payload"].get("extracted_entities", []):
                    self.memory.add_relation(
                        subject=ent["subject"],
                        predicate=ent["predicate"],
                        obj=ent["object"],
                        confidence=ent["confidence"],
                        source=src["payload"]["source_url"],
                    )
        return trace


if __name__ == "__main__":
    async def _demo() -> None:
        engine = RAGEngine()
        trace = await engine.answer(
            question="O que é inteligência artificial?",
            seed_urls=[],
            local_knowledge=["conceito local"],
        )
        print(engine.cot.synthesize(trace))

    asyncio.run(_demo())