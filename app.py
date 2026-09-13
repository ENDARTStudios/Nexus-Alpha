"""Nexus-Alpha — Cloud Core (FastAPI) para Hugging Face Spaces.

Recebe NexusPayloads já validados pelo worker do GitHub Actions e os persiste no
Neo4j AuraDB, além de expor o atendimento conversacional e a topologia do grafo.

Conexões de banco são compartilhadas (singleton) para reaproveitar o pool, em vez
de abrir/fechar um driver a cada requisição.
"""
from __future__ import annotations

import hashlib
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.database.graph_connector import GraphConnector
from src.database.vector_connector import VectorConnector
from src.miner.quarantine import QuarantineStore


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("nexus.core")


API_SECRET_TOKEN = os.environ.get("NEXUS_API_TOKEN", "ChaveSecretaPadraoParaDesenvolvimento")


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
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins.split(",") if o.strip()] or ["*"],
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
    """Métricas para o dashboard/frontend (grafo, vetores e quarentena)."""
    facts = await get_graph_connector().count_concepts()
    verified = await get_graph_connector().count_verified()
    vectors = get_vector_connector().count()
    try:
        quarantined = len(get_quarantine().list_all())
    except Exception as exc:
        logger.warning("Falha ao ler quarentena: %s", exc)
        quarantined = 0
    return {
        "status": "online",
        "timestamp": int(time.time()),
        "facts": facts,
        "verified_facts": verified,
        "vectors": vectors,
        "quarantine": quarantined,
    }


@app.post("/api/ingest")
async def ingest_data(
    payload: IngestionPayload,
    x_nexus_token: Optional[str] = Header(None),
) -> dict:
    if x_nexus_token != API_SECRET_TOKEN:
        raise HTTPException(status_code=401, detail="Token de autorização inválido.")

    success = False
    try:
        success = bool(await get_graph_connector().ingest_payload(payload.model_dump()))
    except Exception as exc:
        logger.warning("Neo4j indisponível (%s) — modo demo em memória.", exc)
        success = False

    vectors_indexed = 0
    try:
        from src.cognition.embeddings import hash_embedding

        text = " ".join(
            f"{e.subject} {e.predicate} {e.object}"
            for e in payload.extracted_entities
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
    return {
        "status": "success" if success else "partial_success",
        "message": (
            "Dados processados e inseridos no Neo4j AuraDB real."
            if success
            else "Dados retidos em quarentena local devido a indisponibilidade temporária do Neo4j."
        ),
        "db_status": db_status,
        "entities_processed": len(payload.extracted_entities),
        "vectors_indexed": vectors_indexed,
        "verified_facts": verified,
    }


@app.post("/api/chat")
async def chat_endpoint(payload: ChatRequest) -> dict:
    """Atendimento conversacional: recupera contexto híbrido e responde ao cliente."""
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
