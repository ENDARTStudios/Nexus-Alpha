"""Nexus-Alpha — Conector assíncrono para Neo4j com queries Cypher.

Prioriza credenciais injetadas por variáveis de ambiente (Hugging Face) e força o
protocolo criptografado de nuvem `neo4j+s://` exigido pelo Neo4j AuraDB.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Optional

import yaml
from neo4j import AsyncGraphDatabase, AsyncDriver

from ..miner.security_protocol import SecurityProtocol


logger = logging.getLogger(__name__)


INGEST_QUERY = """
MERGE (f:FonteWeb {url: $source_url})
  ON CREATE SET f.primeira_verificacao = $timestamp
  ON MATCH   SET f.ultima_verificacao  = $timestamp
SET f.domain_score = $domain_score

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
    """Interface assíncrona para persistência semântica no Neo4j AuraDB."""

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
        """Carrega credenciais (env-first) e garante o protocolo TLS `neo4j+s://`."""
        try:
            self.uri = os.environ.get("NEO4J_URI")
            self.password = os.environ.get("NEO4J_PASSWORD")
            self.user = os.environ.get("NEO4J_USER", "neo4j")
            self.pool_size = 50

            if not self.uri or not self.password:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f) or {}
                graph = cfg.get("database", {}).get("graph", {})
                self.uri = graph.get("uri", "bolt://localhost:7687")
                self.user = graph.get("user", "neo4j")
                self.pool_size = graph.get("pool_size", 50)
                password_env = graph.get("password_env", "NEXUS_NEO4J_PASSWORD")
                self.password = os.getenv(password_env) or "NexusSecurePass2026"

            # [CORREÇÃO - ISSUE #017]: força o protocolo seguro exigido pelo AuraDB
            if self.uri.startswith("bolt://"):
                self.uri = self.uri.replace("bolt://", "neo4j+s://", 1)
            elif self.uri.startswith("neo4j://"):
                self.uri = self.uri.replace("neo4j://", "neo4j+s://", 1)

            logger.info("Configuração carregada. Alvo de persistência: %s", self.uri.split("@")[-1] or self.uri)
        except Exception as exc:
            logger.error("Falha ao carregar configurações de grafos: %s", exc)
            raise

    async def connect(self) -> None:
        """Inicializa a conexão assíncrona e criptografada com o cluster AuraDB."""
        if self.driver is None:
            try:
                self.driver = AsyncGraphDatabase.driver(
                    self.uri,
                    auth=(self.user, self.password),
                    max_connection_pool_size=self.pool_size,
                )
                logger.info("Conexão assíncrona e criptografada com o Neo4j estabelecida com sucesso.")
            except Exception as exc:
                logger.error("Erro ao inicializar o driver Neo4j: %s", exc)
                raise

    async def close(self) -> None:
        """Fecha o pool de conexões de forma limpa."""
        if self.driver is not None:
            await self.driver.close()
            self.driver = None
            logger.info("Conexão com o Neo4j encerrada de forma limpa.")

    async def __aenter__(self) -> "GraphConnector":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def ingest_payload(self, payload: dict[str, Any]) -> int:
        """Persiste um NexusPayload (JSON-LD) de forma atômica via UNWIND.

        Retorna o total de conexões processadas (0 em caso de falha), permitindo
        que o chamador distinga sucesso (truthy) de indisponibilidade.
        """
        if self.driver is None:
            await self.connect()

        source_url = payload.get("source_url", "")
        domain_score = float(payload.get("domain_score", 0.5))
        entities = payload.get("extracted_entities", []) or []

        if not entities:
            logger.warning("Payload sem entidades extraídas — nada a ingerir (%s).", source_url)
            return 0

        try:
            async with self.driver.session() as session:
                result = await session.run(
                    INGEST_QUERY,
                    source_url=source_url,
                    timestamp=payload.get("timestamp"),
                    domain_score=domain_score,
                    entities=entities,
                )
                summary = await result.single()
                total = summary["total_processado"] if summary else 0
                logger.info(
                    "Ingestão concluída no cluster real (%s): %s conexões mapeadas (score=%.2f).",
                    source_url, total, domain_score,
                )
                return total
        except Exception as exc:
            logger.error("Erro durante a ingestão no cluster Neo4j: %s", exc)
            return 0

    async def detect_contradictions(self) -> list[dict[str, Any]]:
        if self.driver is None:
            await self.connect()
        async with self.driver.session() as session:
            result = await session.run(CONTRADICTION_QUERY)
            return [dict(record) async for record in result]

    async def evolution_report(self) -> list[dict[str, Any]]:
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
            "domain_score": 0.9,
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
