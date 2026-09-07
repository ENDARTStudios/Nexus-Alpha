"""Nexus-Alpha — Ciclo autônomo executado pelo GitHub Actions.

A cada 6h (ou manualmente):
1. ReasoningEngine decide o plano.
2. WebMiner coleta dados (com AntiBlockSystem).
3. NLPExtractor extrai tripletas.
4. Envia ao Hugging Face Spaces via API autenticada.
"""
from __future__ import annotations

import asyncio
import logging
import os

import httpx

from src.cognition.reasoning_engine import ReasoningEngine
from src.cognition.nlp_extractor import NLPExtractor
from src.cognition.rag_engine import RAGEngine
from src.miner.web_miner import WebMiner
from src.miner.security_protocol import SecurityProtocol


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("nexus.worker")


SEED_QUERIES = [
    "https://pt.wikipedia.org/wiki/Intelig%C3%AAncia_artificial",
    "https://pt.wikipedia.org/wiki/Aprendizado_de_m%C3%A1quina",
    "https://pt.wikipedia.org/wiki/Rede_neural_artificial",
]


async def run_cycle() -> None:
    token = os.environ.get("NEXUS_API_TOKEN", "")
    api_base = os.environ.get("HF_SPACE_URL", "").rstrip("/")
    if not token or not api_base:
        logger.error("Secrets ausentes — defina NEXUS_API_TOKEN e HF_SPACE_URL no GitHub.")
        return

    engine = ReasoningEngine()
    plan = engine.evaluate_knowledge_gap("Inteligência Artificial", internal_facts=[])
    logger.info("Plano de ação: %s — queries=%d", plan.decision, len(plan.target_queries))

    miner = WebMiner()
    security = SecurityProtocol()
    nlp = NLPExtractor()
    rag = RAGEngine(miner=miner, security=security, extractor=None)  # type: ignore[arg-type]

    sources = await rag.fetch_and_verify(plan.target_queries or SEED_QUERIES)
    payload_payload: dict = {
        "source_url": "https://github-actions.nexus",
        "timestamp": int(asyncio.get_event_loop().time()),
        "domain_score": 0.0,
        "extracted_entities": [],
    }
    for src in sources:
        for ent in src["payload"].get("extracted_entities", []):
            payload_payload["extracted_entities"].append(ent)
        if nlp is not None and src.get("content"):
            for tripla in nlp.extract_triplets(src["content"], src.get("title", "IA") or "IA"):
                payload_payload["extracted_entities"].append(tripla)

    if not payload_payload["extracted_entities"]:
        logger.warning("Nenhuma tripla extraída neste ciclo.")
        return

    api_url = f"{api_base}/api/ingest"
    headers = {"X-Nexus-Token": token, "Content-Type": "application/json"}
    async with httpx.AsyncClient() as client:
        logger.info("Enviando %d entidades para %s", len(payload_payload["extracted_entities"]), api_url)
        response = await client.post(api_url, json=payload_payload, headers=headers, timeout=30.0)
        logger.info("Resposta: %s — %s", response.status_code, response.text)


if __name__ == "__main__":
    asyncio.run(run_cycle())