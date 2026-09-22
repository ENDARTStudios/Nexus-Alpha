"""Nexus-Alpha — Cloud Core (FastAPI) para Hugging Face Spaces.

Recebe NexusPayloads já validados pelo worker do GitHub Actions e os persiste no
Neo4j AuraDB, além de expor o atendimento conversacional e a topologia do grafo.

Conexões de banco são compartilhadas (singleton) para reaproveitar o pool, em vez
de abrir/fechar um driver a cada requisição.
"""
from __future__ import annotations

import collections
import hashlib
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.database.graph_connector import GraphConnector
from src.database.vector_connector import VectorConnector
from src.miner.quarantine import QuarantineStore
from src.security.rate_limiter import InMemoryRateLimiter


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("nexus.core")


API_SECRET_TOKEN = os.environ.get("NEXUS_API_TOKEN", "ChaveSecretaPadraoParaDesenvolvimento")

rate_limiter = InMemoryRateLimiter(requests_limit=5, window_seconds=60)

EPISODE_RETENTION_MAX = 10000
_brain_reads = {"durable": 0, "volatile": 0}


class EntityItem(BaseModel):
    subject: str
    predicate: str
    object: str
    confidence: float = Field(ge=0.0, le=1.0)


class IngestionPayload(BaseModel):
    source_url: str
    timestamp: int
    domain_score: float = Field(default=0.5, ge=0.0, le=1.0)
    title: Optional[str] = None
    extracted_entities: List[EntityItem] = Field(default_factory=list)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: str = Field(default="default", max_length=128)


class SimulationRequest(BaseModel):
    topic: Optional[str] = Field(default=None, max_length=200)
    rounds: int = Field(default=12, ge=1, le=50)
    seed: Optional[int] = None
    injections: dict[str, float] = Field(default_factory=dict)
    use_llm: bool = False


class ExtractRequest(BaseModel):
    text: str = Field(min_length=20, max_length=20000)


class BrainEpisodeRequest(BaseModel):
    kind: str = Field(default="external", max_length=64)
    concepts: List[str] = Field(default_factory=list)


class BrainActivateRequest(BaseModel):
    concepts: List[str] = Field(default_factory=list)


_graph_connector: Optional[GraphConnector] = None
_vector_connector: Optional[VectorConnector] = None
_quarantine: Optional[QuarantineStore] = None
_chat_service = None


def get_graph_connector() -> GraphConnector:
    global _graph_connector
    if _graph_connector is None:
        _graph_connector = GraphConnector()
    return _graph_connector


def get_vector_connector() -> VectorConnector:
    global _vector_connector
    if _vector_connector is None:
        _vector_connector = VectorConnector()
    return _vector_connector


def get_quarantine() -> QuarantineStore:
    global _quarantine
    if _quarantine is None:
        _quarantine = QuarantineStore()
    return _quarantine


_canonicalizer = None


def get_canonicalizer():
    global _canonicalizer
    if _canonicalizer is None:
        from src.cognition.canonicalizer import SemanticCanonicalizer

        _canonicalizer = SemanticCanonicalizer()
    return _canonicalizer


_entity_resolver = None


def get_entity_resolver():
    global _entity_resolver
    if _entity_resolver is None:
        from src.cognition.entity_resolver import EntityResolver

        _entity_resolver = EntityResolver()
    return _entity_resolver


_extraction_stats = {
    "raw_triples": 0,
    "canonical_triples": 0,
    "rejected_noise": 0,
    "duplicate_canonical_triples": 0,
    "reasons": {
        "numeric_predicate": 0,
        "url_or_code_predicate": 0,
        "stopword_predicate": 0,
        "nonverbal_predicate": 0,
        "invalid_predicate": 0,
        "unmapped_predicate": 0,
        "missing_entity": 0,
        "self_loop": 0,
    },
}
_unmapped_predicates: "collections.Counter[str]" = collections.Counter()
_invalid_predicates: "collections.Counter[str]" = collections.Counter()

_INVALID_REASONS = {
    "numeric_predicate",
    "url_or_code_predicate",
    "stopword_predicate",
    "nonverbal_predicate",
    "invalid_predicate",
}

_rejection_quarantine = None


def get_rejection_quarantine():
    global _rejection_quarantine
    if _rejection_quarantine is None:
        from src.cognition.triple_refiner import RejectionQuarantine

        _rejection_quarantine = RejectionQuarantine()
    return _rejection_quarantine


_brain = None


def get_brain():
    global _brain
    if _brain is None:
        from src.brain import BrainMemorySystem

        _brain = BrainMemorySystem(graph=get_graph_connector())
    return _brain


def get_chat_service():
    global _chat_service
    if _chat_service is None:
        from src.cognition.chat_service import ChatService

        _chat_service = ChatService(
            graph=get_graph_connector(), vector=get_vector_connector()
        )
    return _chat_service


@asynccontextmanager
async def lifespan(_: FastAPI):
    if os.environ.get("NEXUS_BOOTSTRAP_SCHEMA", "true").lower() in ("1", "true", "yes"):
        await get_graph_connector().ensure_schema()
    try:
        yield
    finally:
        if _graph_connector is not None:
            await _graph_connector.close()


app = FastAPI(
    title="Nexus-Alpha Cloud Core",
    description="Cérebro da IA rodando no Hugging Face Spaces",
    version="1.4.0",
    lifespan=lifespan,
)


_cors_origins = os.environ.get("NEXUS_CORS_ORIGINS", "*")
_cors_regex = os.environ.get("NEXUS_CORS_ORIGIN_REGEX", r"https://.*\.vercel\.app")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins.split(",") if o.strip()] or ["*"],
    allow_origin_regex=_cors_regex or None,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/")
def home() -> dict:
    return {"status": "online", "message": "Nexus-Alpha Core operacional no Hugging Face Spaces."}


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}


@app.get("/api/metrics")
async def metrics() -> dict:
    """Métricas do pipeline + saúde cognitiva (grafo, vetores, quarentena, memória)."""
    graph = get_graph_connector()
    snapshot = await graph.graph_snapshot()
    vectors = get_vector_connector().count()
    try:
        quarantined = len(get_quarantine().list_all())
    except Exception as exc:
        logger.warning("Falha ao ler quarentena: %s", exc)
        quarantined = 0

    reads = _brain_reads["durable"] + _brain_reads["volatile"]
    persistence_rate = round(_brain_reads["durable"] / reads, 2) if reads else 1.0
    ratio = snapshot["episodes"] / EPISODE_RETENTION_MAX
    pressure = "low" if ratio < 0.5 else ("medium" if ratio < 0.8 else "high")

    return {
        "status": "online",
        "timestamp": int(time.time()),
        "facts": snapshot["concepts"],
        "verified_facts": snapshot["verified"],
        "vectors": vectors,
        "quarantine": quarantined,
        "episodes": snapshot["episodes"],
        "cognitive_health": {
            "episodic_persistence_rate": persistence_rate,
            "hebbian_consistency_check": bool(snapshot.get("ok")),
            "retention_pressure": pressure,
        },
        "extraction_quality": {
            "raw_triples": _extraction_stats["raw_triples"],
            "canonical_triples": _extraction_stats["canonical_triples"],
            "rejected_noise": _extraction_stats["rejected_noise"],
            "duplicate_canonical_triples": _extraction_stats["duplicate_canonical_triples"],
            "rejection_reasons": dict(_extraction_stats["reasons"]),
            "top_unmapped_predicates": [
                {"predicate": predicate, "count": count}
                for predicate, count in _unmapped_predicates.most_common(10)
            ],
            "top_invalid_predicates": [
                {"predicate": predicate, "count": count}
                for predicate, count in _invalid_predicates.most_common(10)
            ],
            "quarantine": get_rejection_quarantine().stats(),
            "cross_source_matches": snapshot.get("cross_source", 0),
            "potential_verified_before_quorum": snapshot.get("cross_source", 0),
            "verified_facts": snapshot["verified"],
        },
        "verification": {
            "quorum": graph.verify_quorum,
            "facts_with_multi_domain": snapshot.get("cross_source", 0),
            "max_domain_confirmations": snapshot.get("max_confirmacoes", 0),
            "verified_facts_domain_independent": snapshot["verified"],
        },
    }


@app.post("/api/ingest")
async def ingest_data(
    payload: IngestionPayload,
    x_nexus_token: Optional[str] = Header(None),
) -> dict:
    if x_nexus_token != API_SECRET_TOKEN:
        raise HTTPException(status_code=401, detail="Token de autorização inválido.")

    payload_dict = payload.model_dump()
    from src.cognition.triple_refiner import refine_triple_ex

    canonicalizer = get_canonicalizer()
    raw_entities = payload_dict.get("extracted_entities", [])
    _extraction_stats["raw_triples"] += len(raw_entities)
    refined_entities = []
    seen_canonical = set()
    quarantine = get_rejection_quarantine()
    for entity in raw_entities:
        refined, reason = refine_triple_ex(entity, canonicalizer)
        if refined is None:
            _extraction_stats["rejected_noise"] += 1
            _extraction_stats["reasons"][reason] = _extraction_stats["reasons"].get(reason, 0) + 1
            if reason == "unmapped_predicate":
                raw_predicate = str(entity.get("predicate", "")).strip()
                if raw_predicate:
                    _unmapped_predicates[raw_predicate.upper()] += 1
            elif reason in _INVALID_REASONS:
                raw_predicate = str(entity.get("predicate", "")).strip()
                if raw_predicate:
                    _invalid_predicates[raw_predicate.upper()] += 1
            try:
                quarantine.record(entity, reason, payload.source_url)
            except Exception as exc:
                logger.warning("Falha na quarentena de rejeitados: %s", exc)
            continue
        key = (refined["subject"], refined["predicate"], refined["object"])
        if key in seen_canonical:
            _extraction_stats["duplicate_canonical_triples"] += 1
            continue
        seen_canonical.add(key)
        refined_entities.append(refined)
    _extraction_stats["canonical_triples"] += len(refined_entities)
    payload_dict["extracted_entities"] = refined_entities

    success = False
    try:
        success = bool(await get_graph_connector().ingest_payload(payload_dict))
    except Exception as exc:
        logger.warning("Neo4j indisponível (%s) — modo demo em memória.", exc)
        success = False

    vectors_indexed = 0
    try:
        from src.cognition.embeddings import hash_embedding

        text = " ".join(
            f"{e['subject']} {e['predicate']} {e['object']}"
            for e in refined_entities
        ) or (payload.title or payload.source_url)
        vector_db = get_vector_connector()
        vector = hash_embedding(text, vector_db.embedding_dim)
        point_id = int(
            hashlib.sha256(f"{payload.source_url}:{payload.timestamp}".encode()).hexdigest()[:8],
            16,
        ) % (10 ** 8)
        if vector_db.store_memory(
            point_id=point_id,
            vector=vector,
            payload={"text": text, "url": payload.source_url, "title": payload.title},
        ):
            vectors_indexed = 1
    except Exception as exc:
        logger.warning("Memória vetorial indisponível (%s) — ingestão apenas no grafo.", exc)

    db_status = "cluster-active" if success else "demo-memory"
    verified = await get_graph_connector().count_verified()
    try:
        brain = get_brain()
        brain.record_episode(
            "ingest",
            {
                "source_url": payload.source_url,
                "extracted_entities": payload_dict["extracted_entities"],
            },
        )
        episode_payloads = brain.episode_payloads(
            payload_dict["extracted_entities"], payload.source_url
        )
        if episode_payloads:
            await get_graph_connector().persist_episodes(episode_payloads)
    except Exception as exc:
        logger.warning("Falha ao registrar episódio no hipocampo: %s", exc)
    return {
        "status": "success" if success else "partial_success",
        "message": (
            "Dados processados e inseridos no Neo4j AuraDB real."
            if success
            else "Dados retidos em quarentena local devido a indisponibilidade temporária do Neo4j."
        ),
        "db_status": db_status,
        "entities_processed": len(refined_entities),
        "vectors_indexed": vectors_indexed,
        "verified_facts": verified,
    }


@app.get("/api/brain/stats")
async def brain_stats() -> dict:
    """Contrato normalizado do painel Cérebro (read-only; sem segredos)."""
    brain = get_brain()
    base = brain.stats()
    graph = get_graph_connector()
    snapshot = await graph.graph_snapshot()
    return {
        "working_memory": {
            "active_slots": len(base["working_active"]),
            "active_concepts": base["working_active"],
            "capacity": base["working_capacity"],
            "decay_policy": "temporal",
            "region": base["working_region"],
        },
        "episodic_memory": {
            "episodes": snapshot["episodes"] or base["episodes"],
            "last_episode_at": snapshot["last_episode"] or brain.episodic.last_timestamp(),
            "region": base["episodic_region"],
        },
        "consolidation": {
            "candidates": len(brain.consolidation_candidates()),
            "consolidated": snapshot["consolidated"],
            "min_replays": base["min_replays"],
            "region": base["semantic_region"],
        },
        "graph": {
            "concepts": snapshot["concepts"],
            "facts": snapshot["facts"],
            "verified_facts": snapshot["verified"],
            "hebbian_pairs": snapshot["hebbian"],
        },
        "vectors": {"count": get_vector_connector().count()},
    }


@app.get("/api/brain/episodes")
async def brain_episodes(limit: int = 20) -> dict:
    """Últimos episódios: lê o durável (Neo4j) e cai para o volátil se vazio."""
    limit = max(1, min(int(limit), 100))
    durable = await get_graph_connector().recent_episodes(limit=limit)
    if durable:
        _brain_reads["durable"] += 1
        return {"items": durable, "source": "neo4j"}
    _brain_reads["volatile"] += 1
    return {"items": get_brain().recent_episodes(limit=limit), "source": "volatile"}


@app.post("/api/brain/activate")
async def brain_activate(payload: BrainActivateRequest) -> dict:
    """Ativa conceitos na memória de trabalho (slots com decaimento)."""
    brain = get_brain()
    active = brain.attend(payload.concepts)
    return {"status": "ok", "active": active, "region": "Córtex Pré-Frontal"}


@app.post("/api/brain/episode")
async def brain_episode(payload: BrainEpisodeRequest) -> dict:
    """Registra um episódio (hipocampo virtual) para consolidação posterior."""
    brain = get_brain()
    episode = brain.record_episode(
        payload.kind, {"extracted_entities": [{"subject": c, "predicate": "CONECTA_A", "object": "MEMÓRIA"} for c in payload.concepts]}
    )
    return {"status": "ok", "episode": {"timestamp": episode.timestamp, "kind": episode.kind}}


@app.post("/api/brain/consolidate")
async def brain_consolidate() -> dict:
    """Ciclo de 'sono': consolida a partir do tally DURÁVEL (idempotente) e retém."""
    from src.brain.memory import INVERSE_PREDICATES, fact_hash

    brain = get_brain()
    graph = get_graph_connector()
    candidates = await graph.episode_tally(min_replays=brain.min_replays)

    inverses: list[dict] = []
    for fact in candidates:
        inverse = INVERSE_PREDICATES.get(str(fact.get("predicate", "")).upper())
        if inverse:
            inverses.append({
                "subject": fact["object"],
                "predicate": inverse,
                "object": fact["subject"],
                "replays": fact["replays"],
            })

    consolidated = await graph.consolidate_facts(candidates + inverses)
    hashes = [fact_hash(c["subject"], c["predicate"], c["object"]) for c in candidates]
    return {
        "status": "ok",
        "source": "neo4j_tally",
        "candidates": len(candidates),
        "inverses": len(inverses),
        "consolidated": consolidated,
        "min_replays": brain.min_replays,
        "episodes_marked": await graph.mark_episodes_status(hashes, "consolidado"),
        "pruned_episodes": await graph.prune_episodes(),
    }


@app.post("/api/extract")
def extract_endpoint(payload: ExtractRequest) -> dict:
    """Extração canônica de triplas via LLM (opt-in; vazio se o LLM não estiver configurado)."""
    from src.cognition.llm_extractor import LLMCanonicalExtractor

    triplets = LLMCanonicalExtractor().extract_canonical_triplets(payload.text)
    return {"status": "ok", "triplets": triplets, "count": len(triplets)}


@app.post("/api/chat")
async def chat_endpoint(payload: ChatRequest, request: Request) -> dict:
    """Atendimento conversacional: recupera contexto híbrido e responde ao cliente."""
    client_ip = request.client.host if request.client else "unknown"
    if not rate_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Muitas requisições. O Córtex está se consolidando, tente novamente em um minuto.",
        )
    service = get_chat_service()
    result = await service.answer(payload.message, payload.session_id)
    sources = result["sources"]
    if "neo4j" in sources:
        context_source = "neo4j_cluster_active"
    elif sources:
        context_source = "vector_memory"
    else:
        context_source = "fallback_empty_graph"
    return {
        "status": "success",
        "reply": result["reply"],
        "session_id": result["session_id"],
        "reasoning_steps": result["reasoning_steps"],
        "sources": sources,
        "provider": result["provider"],
        "context_source": context_source,
        "verified": result.get("verified", False),
    }


@app.get("/api/graph/topology")
async def get_graph_topology() -> dict:
    """Exporta a topologia do córtex relacional no formato D3/ForceGraph."""
    try:
        return await get_graph_connector().topology()
    except Exception as exc:
        logger.warning("Topologia indisponível (%s) — fallback demo.", exc)
        return {"nodes": [{"id": "Nexus-Alpha Core", "group": 1, "val": 20}], "links": []}


@app.post("/api/simulate")
async def simulate(payload: SimulationRequest) -> dict:
    """Roda uma simulação de enxame sobre o grafo e devolve o relatório de cenário."""
    from src.cognition.chat_service import extract_keywords
    from src.simulation import SwarmSimulator

    connector = get_graph_connector()
    if payload.topic:
        rows = await connector.search_context(extract_keywords(payload.topic))
        simulator = SwarmSimulator.from_relations(rows, seed=payload.seed)
    else:
        topology = await connector.topology()
        simulator = SwarmSimulator.from_topology(topology, seed=payload.seed)

    applied = simulator.inject(payload.injections)
    report = simulator.report(simulator.run(rounds=payload.rounds))
    report["injections_applied"] = applied

    provider = None
    if payload.use_llm and report.get("status") == "ok":
        from src.cognition.llm_provider import get_llm_provider

        llm = get_llm_provider()
        provider = llm.name
        narrative = await llm.generate(
            f"Resuma a previsão para: {payload.topic or 'o grafo atual'}",
            [{"fact": report["summary"]}],
        )
        if narrative:
            report["narrative"] = narrative
    report["provider"] = provider
    return report
