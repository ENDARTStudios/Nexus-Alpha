"""Nexus-Alpha — Ciclo autônomo executado pelo GitHub Actions.

A cada 6h (ou manualmente):
1. ReasoningEngine decide o plano.
2. WebMiner coleta dados (com AntiBlockSystem).
3. EntityExtractor (fallback regex, custo zero) extrai tripletas.
4. Envia ao Hugging Face Spaces via API autenticada.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from urllib.parse import quote

import httpx

from src.cognition.reasoning_engine import ReasoningEngine
from src.cognition.extractor import EntityExtractor
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


def _to_urls(queries: list[str]) -> list[str]:
    """Converte queries de busca em URLs reais (Wikipedia para termos, DuckDuckGo para busca)."""
    urls: list[str] = []
    for q in queries:
        if q.startswith("http://") or q.startswith("https://"):
            urls.append(q)
        else:
            # Termo direto -> busca DuckDuckGo; se falhar, termo vira URL Wikipedia
            urls.append(f"https://duckduckgo.com/html/?q={quote(q)}")
    # Adiciona seeds de Wikipédia para garantir conteúdo real extraível
    urls.extend(SEED_QUERIES)
    return urls


async def run_cycle() -> None:
    token = os.environ.get("NEXUS_API_TOKEN", "")
    api_base = os.environ.get("HF_SPACE_URL", "").rstrip("/")
    hf_token = os.environ.get("HF_TOKEN", "")
    if not token or not api_base:
        logger.error("Secrets ausentes — defina NEXUS_API_TOKEN e HF_SPACE_URL no GitHub.")
        return

    engine = ReasoningEngine()
    plan = engine.evaluate_knowledge_gap("Inteligência Artificial", internal_facts=[])
    logger.info("Plano de ação: %s — queries=%d", plan.decision, len(plan.target_queries))

    miner = WebMiner()
    security = SecurityProtocol()
    extractor = EntityExtractor(enable_fallback=True)
    rag = RAGEngine(miner=miner, security=security, extractor=extractor)

    target_urls = _to_urls(plan.target_queries)
    logger.info("Minerando %d URLs (com seeds Wikipédia).", len(target_urls))
    sources = await rag.fetch_and_verify(target_urls)

    payload: dict = {
        "source_url": "https://github-actions.nexus",
        "timestamp": int(time.time()),
        "domain_score": max(
            (float(src.get("payload", {}).get("domain_score", 0.0)) for src in sources),
            default=0.0,
        ),
        "extracted_entities": [],
    }
    for src in sources:
        for ent in src["payload"].get("extracted_entities", []):
            payload["extracted_entities"].append(ent)

    if not payload["extracted_entities"]:
        logger.warning("Nenhuma tripla extraída neste ciclo.")
        return

    api_url = f"{api_base}/api/ingest"
    # Header Authorization (token HF) é exigido pelo proxy de Spaces PRIVADOS
    headers = {
        "Authorization": f"Bearer {hf_token}",
        "X-Nexus-Token": token,
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient() as client:
        # Wake-up: ping /health até o Space sair da hibernação antes do POST
        for attempt in range(5):
            try:
                hp = await client.get(f"{api_base}/health", timeout=20.0)
                if hp.status_code == 200:
                    break
                logger.info("Warm-up: Space /health -> %d (tentativa %d/5)", hp.status_code, attempt + 1)
            except Exception as exc:
                logger.warning("Warm-up: ping falhou (%s) - tentativa %d/5", exc, attempt + 1)
            await asyncio.sleep(15)

        logger.info("Enviando %d entidades para %s", len(payload["extracted_entities"]), api_url)
        response = await client.post(api_url, json=payload, headers=headers, timeout=30.0)
        logger.info("Resposta: %s — %s", response.status_code, response.text)


if __name__ == "__main__":
    asyncio.run(run_cycle())