"""Nexus-Alpha — Ciclo autônomo executado pelo GitHub Actions.

A cada 6h (ou manualmente):
1. ReasoningEngine decide o plano.
2. WebMiner coleta dados (com AntiBlockSystem).
3. EntityExtractor (spaCy pt com fallback regex) extrai tripletas.
4. Envia **um payload por fonte** ao Hugging Face Space (preserva o domínio de
   cada fonte para a corroboração/triangulação server-side).
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
    # Base enciclopédica PT (maximiza sobreposição exata de triplas)
    "https://pt.wikipedia.org/wiki/Intelig%C3%AAncia_artificial",
    "https://pt.wikipedia.org/wiki/Aprendizado_de_m%C3%A1quina",
    "https://pt.wikipedia.org/wiki/Rede_neural_artificial",
    "https://pt.wikipedia.org/wiki/Aprendizado_profundo",
    "https://pt.wikipedia.org/wiki/Processamento_de_linguagem_natural",
    "https://pt.wikipedia.org/wiki/Visi%C3%A3o_computacional",
    "https://pt.wikipedia.org/wiki/Aprendizado_por_refor%C3%A7o",
    "https://pt.wikipedia.org/wiki/Intelig%C3%AAncia_artificial_geral",
    # Base enciclopédica EN
    "https://en.wikipedia.org/wiki/Artificial_intelligence",
    "https://en.wikipedia.org/wiki/Machine_learning",
    # Documentação / pesquisa (allowlist tech)
    "https://pytorch.org/tutorials/beginner/basics/intro.html",
    "https://www.tensorflow.org/tutorials/quickstart/beginner",
    "https://scikit-learn.org/stable/modules/neural_networks_supervised.html",
    "https://huggingface.co/docs/transformers/index",
    "https://ollama.com/library",
    "https://research.google/blog/",
    "https://arxiv.org/abs/2303.08774",
    "https://paperswithcode.com/area/natural-language-processing",
    # Institucional / científico / guias
    "https://plato.stanford.edu/entries/artificial-intelligence/",
    "https://www.nist.gov/artificial-intelligence",
    "https://www.geeksforgeeks.org/what-is-artificial-intelligence/",
    "https://www.ibm.com/think/topics/artificial-intelligence",
    "https://developer.mozilla.org/en-US/docs/Glossary/Machine_learning",
    "https://news.mit.edu/topic/artificial-intelligence2",
    "https://spectrum.ieee.org/artificial-intelligence",
]


def _to_urls(queries: list[str]) -> list[str]:
    """Seeds diversas primeiro (corroboração) e depois as queries de busca."""
    urls: list[str] = list(SEED_QUERIES)
    for q in queries:
        if q.startswith("http://") or q.startswith("https://"):
            urls.append(q)
        else:
            urls.append(f"https://duckduckgo.com/html/?q={quote(q)}")
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
    rag = RAGEngine(miner=miner, security=security, extractor=extractor, top_k=40)

    target_urls = _to_urls(plan.target_queries)
    logger.info("Minerando %d URLs (com seeds Wikipédia).", len(target_urls))
    sources = await rag.fetch_and_verify(target_urls)

    payloads = [src.get("payload", {}) for src in sources]
    payloads = [p for p in payloads if p.get("extracted_entities")]
    if not payloads:
        logger.warning("Nenhuma tripla extraída neste ciclo.")
        return

    api_url = f"{api_base}/api/ingest"
    headers = {
        "Authorization": f"Bearer {hf_token}",
        "X-Nexus-Token": token,
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient() as client:
        # Wake-up: ping /health até o Space sair da hibernação (auth obrigatório em Space privado).
        warmup_headers = {"Authorization": f"Bearer {hf_token}"}
        for attempt in range(5):
            try:
                hp = await client.get(f"{api_base}/health", headers=warmup_headers, timeout=20.0)
                if hp.status_code == 200:
                    break
                logger.info("Warm-up: Space /health -> %d (tentativa %d/5)", hp.status_code, attempt + 1)
            except Exception as exc:
                logger.warning("Warm-up: ping falhou (%s) - tentativa %d/5", exc, attempt + 1)
            await asyncio.sleep(15)

        sent = 0
        for payload in payloads:
            payload.setdefault("timestamp", int(time.time()))
            response = await client.post(api_url, json=payload, headers=headers, timeout=30.0)
            logger.info(
                "Resposta [%s]: %s — %s",
                payload.get("source_url"), response.status_code, response.text,
            )
            sent += 1
        logger.info("Ingestão concluída: %d fonte(s) enviada(s).", sent)


if __name__ == "__main__":
    asyncio.run(run_cycle())
