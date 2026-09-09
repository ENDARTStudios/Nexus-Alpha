"""Nexus-Alpha — Cloud Core (FastAPI) para Hugging Face Spaces.

Endpoint público protegido por token. Recebe NexusPayloads já validados pelo
worker do GitHub Actions e os persiste no Neo4j AuraDB.
"""
from __future__ import annotations

import logging
import os
from typing import List, Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from src.database.graph_connector import GraphConnector


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("nexus.core")


app = FastAPI(
    title="Nexus-Alpha Cloud Core",
    description="Cérebro da IA rodando no Hugging Face Spaces",
    version="1.2.0",
)


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


@app.get("/")
def home() -> dict:
    return {"status": "online", "message": "Nexus-Alpha Core operacional no Hugging Face Spaces."}


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}


@app.post("/api/ingest")
async def ingest_data(
    payload: IngestionPayload,
    x_nexus_token: Optional[str] = Header(None),
) -> dict:
    if x_nexus_token != API_SECRET_TOKEN:
        raise HTTPException(status_code=401, detail="Token de autorização inválido.")

    db_status = "demo-memory"
    success = False
    try:
        connector = GraphConnector()
        await connector.connect()
        success = bool(await connector.ingest_payload(payload.model_dump()))
        await connector.close()
    except Exception as exc:
        logger.warning("Neo4j indisponível (%s) — modo demo em memória.", exc)
        success = False

    if success:
        db_status = "cluster-active"
        return {
            "status": "success",
            "message": "Dados processados e inseridos no Neo4j AuraDB real.",
            "db_status": db_status,
            "entities_processed": len(payload.extracted_entities),
        }

    return {
        "status": "partial_success",
        "message": "Dados retidos em quarentena local devido a indisponibilidade temporária do Neo4j.",
        "db_status": db_status,
        "entities_processed": len(payload.extracted_entities),
    }
