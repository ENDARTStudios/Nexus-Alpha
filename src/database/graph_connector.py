"""Nexus-Alpha — Conector assíncrono para Neo4j com queries Cypher."""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Optional
from urllib.parse import urlparse

import yaml
from neo4j import AsyncGraphDatabase, AsyncDriver

from ..miner.security_protocol import SecurityProtocol


logger = logging.getLogger(__name__)


INGEST_QUERY = """
MERGE (f:FonteWeb {url: $source_url})
  ON CREATE SET f.primeira_verificacao = $timestamp
  ON MATCH   SET f.ultima_verificacao  = $timestamp
SET f.domain_score = $domain_score,
    f.em_quarentena = CASE WHEN $domain_score < $quarantine_threshold THEN true ELSE f.em_quarentena END

WITH f
UNWIND $entities AS item

MERGE (s:Conceito {nome: item.subject})
  ON CREATE SET s.criado_em = timestamp()
MERGE (o:Conceito {nome: item.object})
  ON CREATE SET o.criado_em = timestamp()

WITH f, s, o, item
CALL apoc.create.relationship(s, toUpper(item.predicate), {confidence: item.confidence, timestamp: $timestamp}, o) YIELD rel

MERGE (s)-[:MINERADO_DE]->(f)
MERGE (o)-[:MINERADO_DE]->(f)

RETURN count(item) AS total_processado
"""

CONTRADICTION_QUERY = """
MATCH (c1:Conceito)-[r1]->(c2:Conceito)
WHERE type(r1) IN ['AFIRMA', 'NEGA']
WITH c1, c2, collect({tipo: type(r1), peso: r1.peso}) AS relacoes
WHERE size(relacoes) > 1
  AND any(r IN relacoes WHERE r.tipo = 'AFIRMA')
  AND any(r IN relacoes WHERE r.tipo = 'NEGA')
RETURN c1.nome AS origem,
       c2.nome AS destino,
       relacoes,
       'Alerta: contradição detectada — acionar mecanismo de desempate web' AS status
"""

EVOLUTION_QUERY = """
MATCH (c:Conceito)
OPTIONAL MATCH (c)-[r]->()
WITH c, count(r) AS grau
RETURN c.nome AS conceito, grau AS conexoes
ORDER BY grau DESC
LIMIT 25
"""


class GraphConnector:
    """Interface assíncrona para persistência semântica no Neo4j."""

    def __init__(
        self,
        config_path: str = "config/settings.yaml",
        security: Optional[SecurityProtocol] = None,
    ) -> None:
        self.config_path = config_path
        self.security = security or SecurityProtocol()
        self.driver: Optional[AsyncDriver] = None
        self._load_config()

    def _load_config(self) -> None:
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            graph = cfg.get("database", {}).get("graph", {})
            self.uri = graph.get("uri", "bolt://localhost:7687")
            self.user = graph.get("user", "neo4j")
            password_env = graph.get("password_env", "NEXUS_NEO4J_PASSWORD")
            self.password = os.getenv(password_env) or os.getenv("NEO4J_PASSWORD", "neo4j")
            self.pool_size = graph.get("pool_size", 50)
            self.quarantine_threshold = (
                cfg.get("security_policy", {})
                .get("triangulation", {})
                .get("auto_quarantine_threshold", 0.5)
            )
        except Exception as exc:
            logger.error("Falha ao carregar configurações de grafos: %s", exc)
            raise

    async def connect(self) -> None:
        if self.driver is None:
            self.driver = AsyncGraphDatabase.driver(
                self.uri, auth=(self.user, self.password), max_connection_pool_size=self.pool_size
            )
            logger.info("Conexão assíncrona com o Neo4j estabelecida (%s).", self.uri)

    async def close(self) -> None:
        if self.driver is not None:
            await self.driver.close()
            self.driver = None
            logger.info("Conexão com o Neo4j encerrada.")

    async def __aenter__(self) -> "GraphConnector":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    @staticmethod
    def _domain_of(url: str) -> str:
        return urlparse(url).netloc.lower()

    async def ingest_payload(self, payload: dict[str, Any]) -> int:
        """Persiste um NexusPayload respeitando o SecurityProtocol e a quarentena."""
        if self.driver is None:
            await self.connect()

        source_url = payload.get("source_url", "")
        context_text = "{} {}".format(
            payload.get("title") or "",
            payload.get("metadata") or "",
        )
        domain_score = self.security.confidence(source_url, context_text)
        entities = payload.get("extracted_entities", []) or []

        if not entities:
            logger.warning("Payload sem entidades extraídas — nada a ingerir (%s).", source_url)
            return 0

        async with self.driver.session() as session:
            result = await session.run(
                INGEST_QUERY,
                source_url=source_url,
                timestamp=payload.get("timestamp"),
                domain_score=domain_score,
                quarantine_threshold=self.quarantine_threshold,
                entities=entities,
            )
            summary = await result.single()
            total = summary["total_processado"] if summary else 0
            logger.info(
                "Ingestão concluída em %s: %s conexões semânticas (score=%.2f).",
                source_url, total, domain_score,
            )
            return total

    async def detect_contradictions(self) -> list[dict]:
        if self.driver is None:
            await self.connect()
        async with self.driver.session() as session:
            result = await session.run(CONTRADICTION_QUERY)
            return [dict(record) async for record in result]

    async def evolution_report(self) -> list[dict]:
        if self.driver is None:
            await self.connect()
        async with self.driver.session() as session:
            result = await session.run(EVOLUTION_QUERY)
            return [dict(record) async for record in result]


if __name__ == "__main__":
    async def _demo() -> None:
        mock_payload = {
            "source_url": "https://wikipedia.org",
            "timestamp": 1710000000,
            "extracted_entities": [
                {"subject": "Inteligência Artificial", "predicate": "UTILIZA", "object": "Redes Neurais", "confidence": 0.95},
                {"subject": "Redes Neurais", "predicate": "PROCESSA", "object": "Grandes Volumes de Dados", "confidence": 0.88},
            ],
        }
        connector = GraphConnector()
        try:
            await connector.connect()
            await connector.ingest_payload(mock_payload)
        except Exception as exc:
            logger.warning("Demo ignorada (Neo4j indisponível): %s", exc)
        finally:
            await connector.close()

    asyncio.run(_demo())