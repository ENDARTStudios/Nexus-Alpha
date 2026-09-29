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
import json
import logging
import os
import time
from pathlib import Path
from urllib.parse import quote

import httpx

from src.cognition.reasoning_engine import ReasoningEngine
from src.cognition.extractor import EntityExtractor
from src.cognition.rag_engine import RAGEngine
from src.cognition.geo_extractor import (
    default_geo_allowlist,
    fetch_and_extract_geo,
    is_geo_nominatim_url,
)
from src.cognition.geo_wiki_parser import extract_geo_localizado_from_wiki, is_geo_wiki_url
from src.ops.space_telemetry import check_space_telemetry
from src.miner.seed_loader import cluster_to_seeds, load_seed_clusters, manifest_health, validate_seed_clusters
from src.miner.source_productivity import payload_telemetry
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


# #048.6 batch 3 / #048.10G.1: teto de mineração do RAG. O top_k trunca a cauda de
# target_urls SILENCIOSAMENTE (foi assim que as RSSSF caíram no run 36333813255).
# Guard seed-aware: cobre SEED_QUERIES + URLs curadas do manifest + margem de 10.
_SEED_MANIFEST = Path(__file__).resolve().parent.parent / "config" / "seed_clusters.yaml"
try:
    _ACTIVE_SEED_URLS = len(cluster_to_seeds(load_seed_clusters(_SEED_MANIFEST)))
except Exception:  # manifest ausente/inválido não pode quebrar o import
    _ACTIVE_SEED_URLS = 0
WORKER_TOP_K = max(64, len(SEED_QUERIES) + _ACTIVE_SEED_URLS + 10)


def _merge_urls(base_urls: list[str], cluster_urls: list[str]) -> list[str]:
    """Clusters curados primeiro; o top_k do RAG trunca a cauda.

    Seeds curadas (ex.: RSSSF) jamais podem cair por truncamento — a cauda
    (queries de busca/DDG) é descartável. Sem duplicatas, ordem estável.
    """
    merged = [u for u in cluster_urls if u not in base_urls]
    merged.extend(u for u in base_urls if u not in merged)
    return merged


def _load_cluster_urls() -> list[str]:
    """URLs dos clusters curados (#048), validadas estruturalmente."""
    path = Path(__file__).resolve().parent.parent / "config" / "seed_clusters.yaml"
    try:
        data = load_seed_clusters(path)
        errors = validate_seed_clusters(data)
        if errors:
            logger.warning("seed_clusters.yaml inválido (%d erros): %s", len(errors), errors[:5])
            return []
        logger.info("Clusters curados: %s", manifest_health(data))
        return cluster_to_seeds(data)
    except Exception as exc:
        logger.warning("Falha ao carregar clusters: %s", exc)
        return []


def _split_geo_urls(urls: list[str]) -> tuple[list[str], list[str], list[str]]:
    """Separa URLs: Nominatim (JSON), wiki GEO (parser dedicado) e HTML (pipeline atual)."""
    nominatim = [u for u in urls if is_geo_nominatim_url(u)]
    geo_wiki = [u for u in urls if not is_geo_nominatim_url(u) and is_geo_wiki_url(u)]
    html = [u for u in urls if not is_geo_nominatim_url(u) and not is_geo_wiki_url(u)]
    return nominatim, geo_wiki, html


def _build_geo_payloads(
    geo_urls: list[str],
    allowlist=None,
    expected_city: str | None = None,
    fetcher=fetch_and_extract_geo,
) -> tuple[list[dict], dict]:
    """Caminho GEO isolado: fetch JSON -> triplas -> payloads no MESMO refine/ingest.

    Nao passa pelo WebMiner (HTML) e nao cria bypass de validacao: as triplas
    seguem para o ingest canonico como qualquer outra fonte.
    """
    allowlist = allowlist or default_geo_allowlist()
    telemetry = {
        "osm_urls_seen": len(geo_urls),
        "osm_urls_fetched": 0,
        "osm_json_parsed": 0,
        "geo_triples_raw": 0,
        "geo_triples_canonical": 0,
        "rejection_reasons": {},
    }
    payloads: list[dict] = []
    for url in geo_urls:
        triples, tel = fetcher(url, allowlist, expected_city)
        telemetry["osm_urls_fetched"] += 1
        telemetry["osm_json_parsed"] += int(tel.get("osm_json_parsed", 0))
        telemetry["geo_triples_raw"] += int(tel.get("geo_triples_raw", 0))
        for reason, count in (tel.get("rejection_reasons") or {}).items():
            telemetry["rejection_reasons"][reason] = telemetry["rejection_reasons"].get(reason, 0) + count
        if triples:
            telemetry["geo_triples_canonical"] += len(triples)
            # EntityItem do Space exige `confidence` (0..1); o extrator GEO nao o define.
            entities = [{**t, "confidence": float(t.get("confidence", 0.9))} for t in triples]
            payloads.append(
                {
                    "source_url": url,
                    "timestamp": int(time.time()),
                    "domain_score": 0.85,
                    "metadata": {
                        "source_type": "geo_osm",
                        "publisher": "OpenStreetMap",
                        "publisher_family": "OpenStreetMap",
                        "license": "ODbL",
                        "attribution": "(c) OpenStreetMap contributors",
                    },
                    "title": "GEO/OSM",
                    "content": "",
                    "extracted_entities": entities,
                }
            )
    return payloads, telemetry


def _load_expected_geo_city() -> str | None:
    """Cidade esperada do lote atual (registry). Unica -> usa como fallback OSM source-scoped."""
    path = Path(__file__).resolve().parent.parent / "reports" / "geo_expected_facts_048_10H.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    cities = {str(f.get("object")) for f in (data.get("expected_facts") or []) if f.get("object")}
    return next(iter(cities)) if len(cities) == 1 else None


def _build_geo_wiki_payloads(
    geo_wiki_urls: list[str],
    parser=extract_geo_localizado_from_wiki,
    fetcher=None,
) -> tuple[list[dict], dict]:
    """URLs wiki GEO: parser dedicado (subject pinado), SEM extracao narrativa generica."""
    import urllib.error
    import urllib.request

    def _default_fetch(url: str) -> str:
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "Nexus-Alpha/1.0 (geo wiki parser)"})
            with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310 (allowlist)
                return response.read().decode("utf-8", errors="replace")
        except Exception:
            return ""

    fetch = fetcher or _default_fetch
    telemetry = {"geo_wiki_urls_seen": len(geo_wiki_urls), "geo_wiki_urls_fetched": 0,
                 "geo_wiki_triples_canonical": 0, "generic_wiki_noise_suppressed": True}
    payloads: list[dict] = []
    for url in geo_wiki_urls:
        html = fetch(url)
        telemetry["geo_wiki_urls_fetched"] += 1
        triples = parser(url, "", html) if html else []
        if not triples:
            continue
        telemetry["geo_wiki_triples_canonical"] += len(triples)
        entities = [{**t, "confidence": float(t.get("confidence", 0.9))} for t in triples]
        payloads.append(
            {
                "source_url": url,
                "timestamp": int(time.time()),
                "domain_score": 0.9,
                "metadata": {"source_type": "wiki_narrative", "publisher": "Wikimedia",
                             "publisher_family": "Wikimedia", "geo_wiki_dedicated_parser": True},
                "title": "GEO/Wiki",
                "content": "",
                "extracted_entities": entities,
            }
        )
    return payloads, telemetry


async def _post_ingest_with_retry(client, api_url: str, payload: dict, headers: dict, max_retries: int = 2):
    """POST no endpoint de ingest com retry limitado para 5xx.

    Idempotente: o grafo persiste por MERGE na chave canonica (`app.py` -> graph_connector),
    entao reenviar o mesmo payload nao cria duplicata. Retry apenas para 502/503/504.
    """
    response = None
    for attempt in range(max_retries + 1):
        response = await client.post(api_url, json=payload, headers=headers, timeout=30.0)
        if response.status_code not in (502, 503, 504):
            return response
        if attempt < max_retries:
            logger.warning(
                "ingest 5xx (%s) em %s — retry %d/%d",
                response.status_code, payload.get("source_url"), attempt + 1, max_retries,
            )
            await asyncio.sleep(5 * (attempt + 1))
    return response


class TelemetryBlocked(RuntimeError):
    """Gate duro: o worker recusa a abrir a porta quando a telemetria está stale."""


def _telemetry_gate(allow_unverified_local: bool = False):
    return check_space_telemetry(allow_unverified_local=allow_unverified_local)


def _enforce_telemetry_gate(result) -> None:
    if result.ok:
        return
    reason = result.reason or "BLOCKED_SPACE_STALE_TELEMETRY"
    message = (
        f"{reason}\n"
        f"missing_fields: {result.missing_fields}\n"
        f"reason: {result.reason}\n"
        f"No writes were attempted."
    )
    logger.error(message)
    raise TelemetryBlocked(message)


async def run_cycle(allow_unverified_local: bool = False) -> None:
    _enforce_telemetry_gate(_telemetry_gate(allow_unverified_local=allow_unverified_local))
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
    rag = RAGEngine(miner=miner, security=security, extractor=extractor, top_k=WORKER_TOP_K)

    target_urls = _to_urls(plan.target_queries)
    cluster_urls = _load_cluster_urls()
    if cluster_urls:
        target_urls = _merge_urls(target_urls, cluster_urls)
        logger.info("Clusters curados: +%d URLs -> %d no total.", len(cluster_urls), len(target_urls))

    geo_urls, geo_wiki_urls, html_urls = _split_geo_urls(target_urls)
    if geo_urls:
        logger.info("GEO/OSM: %d URL(s) Nominatim roteadas para o geo path isolado.", len(geo_urls))
    if geo_wiki_urls:
        logger.info("GEO/Wiki: %d URL(s) roteadas para o parser dedicado (sem narrativa generica).", len(geo_wiki_urls))
    logger.info("Minerando %d URL(s) HTML (com seeds Wikipédia).", len(html_urls))
    sources = await rag.fetch_and_verify(html_urls)

    payloads = [src.get("payload", {}) for src in sources]
    payloads = [p for p in payloads if p.get("extracted_entities")]
    geo_payloads, geo_telemetry = _build_geo_payloads(geo_urls, expected_city=_load_expected_geo_city())
    if geo_urls:
        logger.info("telemetria GEO/OSM: %s", json.dumps(geo_telemetry, ensure_ascii=False))
    geo_wiki_payloads, geo_wiki_telemetry = _build_geo_wiki_payloads(geo_wiki_urls)
    if geo_wiki_urls:
        logger.info("telemetria GEO/Wiki: %s", json.dumps(geo_wiki_telemetry, ensure_ascii=False))
    payloads.extend(geo_payloads)
    payloads.extend(geo_wiki_payloads)
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

        # Extração canônica via LLM no Space (opt-in). Se vazio, mantém o heurístico.
        canonicalized = 0
        extract_url = f"{api_base}/api/extract"
        for payload in payloads:
            try:
                ex = await client.post(
                    extract_url,
                    json={"text": (payload.get("content") or "")[:20000]},
                    headers=headers,
                    timeout=90.0,
                )
                if ex.status_code == 200 and ex.json().get("triplets"):
                    payload["extracted_entities"] = ex.json()["triplets"]
                    canonicalized += 1
            except Exception as exc:
                logger.warning("Extração LLM falhou (%s): %s", payload.get("source_url"), exc)
        logger.info("Extração canônica LLM aplicada em %d/%d fonte(s).", canonicalized, len(payloads))

        sent = 0
        for payload in payloads:
            payload.setdefault("timestamp", int(time.time()))
            tel = payload_telemetry(payload)
            logger.info(
                "telemetria %s",
                json.dumps(
                    {
                        "url": payload.get("source_url"),
                        "quality": tel.get("extractive_quality"),
                        "canonical_triples": tel.get("canonical_triples"),
                        "raw_triples": tel.get("raw_triples"),
                        "football_related_hits": tel.get("football_related_hits"),
                        "football_verb_hits": tel.get("football_verb_hits"),
                        "notes": tel.get("notes"),
                    },
                    ensure_ascii=False,
                ),
            )
            response = await _post_ingest_with_retry(client, api_url, payload, headers)
            logger.info(
                "Resposta [%s]: %s — %s",
                payload.get("source_url"), response.status_code, response.text,
            )
            try:
                body = response.json()
                if isinstance(body, dict) and body.get("status") in {"degraded", "failed"}:
                    logger.warning(
                        "Ingest degradado [%s]: status=%s entities=%s masked=%s",
                        payload.get("source_url"),
                        body.get("status"),
                        body.get("entities_processed"),
                        body.get("masked_extraction_failure"),
                    )
            except Exception:
                pass
            sent += 1
        logger.info("Ingestão concluída: %d fonte(s) enviada(s).", sent)

        # Ciclo de "sono": consolidação semântica (Hebbian) no córtex do Space
        try:
            cons = await client.post(
                f"{api_base}/api/brain/consolidate", headers=headers, timeout=120.0
            )
            logger.info("Consolidação cerebral: %s — %s", cons.status_code, cons.text[:200])
        except Exception as exc:
            logger.warning("Consolidação cerebral falhou: %s", exc)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Worker autônomo Nexus-Alpha (gate de telemetria obrigatório).")
    parser.add_argument(
        "--allow-unverified-local",
        action="store_true",
        help="NÃO usar em produção: pula o gate de telemetria (apenas offline/local).",
    )
    _args = parser.parse_args()
    if _args.allow_unverified_local:
        logger.warning("Gate de telemetria PULADO (--allow-unverified-local). NÃO usar em produção.")
    try:
        asyncio.run(run_cycle(allow_unverified_local=_args.allow_unverified_local))
    except TelemetryBlocked as exc:
        logger.error("%s", exc)
        raise SystemExit(1)
