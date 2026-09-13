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

MERGE (s)-[r:RELACIONA {predicate: toUpper(item.predicate)}]->(o)
  SET r.confidence = item.confidence, r.timestamp = $timestamp

MERGE (f)-[:CONFIRMA]->(r)
MERGE (s)-[:MINERADO_DE]->(f)
MERGE (o)-[:MINERADO_DE]->(f)

WITH DISTINCT r
MATCH (ff:FonteWeb)-[:CONFIRMA]->(r)
WITH r, count(DISTINCT ff) AS confirmacoes
SET r.confirmacoes = confirmacoes, r.verificado = (confirmacoes >= $quorum)
RETURN count(r) AS total_processado
"""

CONTRADICTION_QUERY = """
MATCH (c1:Conceito)-[r:RELACIONA]->(c2:Conceito)
WITH c1, c2, collect(DISTINCT r.predicate) AS predicados
WHERE any(p IN predicados WHERE p = 'AFIRMA')
  AND any(p IN predicados WHERE p = 'NEGA')
RETURN c1.nome AS origem,
       c2.nome AS destino,
       predicados AS relacoes,
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

CONTEXT_QUERY = """
UNWIND $keywords AS kw
MATCH (s:Conceito)-[r:RELACIONA]->(o:Conceito)
WHERE toLower(s.nome) CONTAINS kw OR toLower(o.nome) CONTAINS kw
RETURN DISTINCT s.nome AS subject, r.predicate AS predicate, o.nome AS object
LIMIT $limit
"""

TOPOLOGY_QUERY = """
MATCH (s:Conceito)-[r:RELACIONA]->(o:Conceito)
RETURN s.nome AS sujeito, r.predicate AS relacao, o.nome AS objeto
LIMIT $limit
"""

DEMO_TOPOLOGY = {"nodes": [{"id": "Nexus-Alpha Core", "group": 1, "val": 20}], "links": []}

COUNT_QUERY = "MATCH (c:Conceito) RETURN count(c) AS total"

VERIFIED_QUERY = (
    "MATCH ()-[r:RELACIONA]->() WHERE r.verificado = true RETURN count(r) AS total"
)

SCHEMA_STATEMENTS = [
    "CREATE CONSTRAINT conceito_nome IF NOT EXISTS FOR (c:Conceito) REQUIRE c.nome IS UNIQUE",
    "CREATE CONSTRAINT fonte_url IF NOT EXISTS FOR (f:FonteWeb) REQUIRE f.url IS UNIQUE",
    "CREATE INDEX conceito_busca IF NOT EXISTS FOR (c:Conceito) ON (c.nome)",
]


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
        """Carrega credenciais (env-first) e garante o protocolo TLS `neo4j+s://`.

        Aceita aliases de ambiente para evitar divergência de nomenclatura:
        ``NEO4J_URI``/``NEO4J_URL`` e ``NEO4J_PASSWORD``/``NEXUS_NEO4J_PASSWORD``.
        """
        try:
            self.uri = os.environ.get("NEO4J_URI") or os.environ.get("NEO4J_URL")
            self.password = (
                os.environ.get("NEO4J_PASSWORD")
                or os.environ.get("NEXUS_NEO4J_PASSWORD")
            )
            self.user = os.environ.get("NEO4J_USER", "neo4j")
            self.pool_size = 50
            self.verify_quorum = int(os.environ.get("NEXUS_VERIFY_QUORUM", "3"))

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
                    connection_timeout=10.0,
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

    async def ensure_schema(self) -> bool:
        """Aplica constraints/índices idempotentes (performance de leitura)."""
        try:
            if self.driver is None:
                await self.connect()
            async with self.driver.session() as session:
                for statement in SCHEMA_STATEMENTS:
                    await session.run(statement)
            logger.info("Schema do Neo4j verificado (constraints/índices).")
            return True
        except Exception as exc:
            logger.warning("Falha ao aplicar schema do Neo4j: %s", exc)
            return False

    async def count_concepts(self) -> int:
        """Total de nós :Conceito no grafo (0 se indisponível)."""
        try:
            if self.driver is None:
                await self.connect()
            async with self.driver.session() as session:
                result = await session.run(COUNT_QUERY)
                record = await result.single()
                return int(record["total"]) if record else 0
        except Exception as exc:
            logger.warning("Falha ao contar conceitos no Neo4j: %s", exc)
            return 0

    async def count_verified(self) -> int:
        """Total de relações corroboradas por >= quórum de fontes (fatos verificados)."""
        try:
            if self.driver is None:
                await self.connect()
            async with self.driver.session() as session:
                result = await session.run(VERIFIED_QUERY)
                record = await result.single()
                return int(record["total"]) if record else 0
        except Exception as exc:
            logger.warning("Falha ao contar fatos verificados: %s", exc)
            return 0

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
                    quorum=self.verify_quorum,
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

    async def search_context(self, keywords: list[str], limit: int = 8) -> list[dict[str, Any]]:
        """Busca relações cujos conceitos casam com as palavras-chave (chat/RAG)."""
        keywords = [k.lower() for k in keywords if k]
        if not keywords:
            return []
        try:
            if self.driver is None:
                await self.connect()
            async with self.driver.session() as session:
                result = await session.run(CONTEXT_QUERY, keywords=keywords, limit=limit)
                return [dict(record) async for record in result]
        except Exception as exc:
            logger.warning("Falha na busca de contexto no Neo4j: %s", exc)
            return []

    async def topology(self, limit: int = 100) -> dict[str, list[dict[str, Any]]]:
        """Exporta nós e arestas no formato D3/ForceGraph para a UI.

        Degrada para uma malha de demonstração quando o cluster está vazio ou
        indisponível, mantendo o comportamento resiliente do endpoint.
        """
        nodes: dict[str, dict[str, Any]] = {}
        links: list[dict[str, Any]] = []
        try:
            if self.driver is None:
                await self.connect()
            async with self.driver.session() as session:
                result = await session.run(TOPOLOGY_QUERY, limit=limit)
                async for record in result:
                    sujeito = record["sujeito"]
                    objeto = record["objeto"]
                    nodes.setdefault(sujeito, {"id": sujeito, "group": 1, "val": 15})
                    nodes.setdefault(objeto, {"id": objeto, "group": 1, "val": 15})
                    links.append({
                        "source": sujeito,
                        "target": objeto,
                        "label": record["relacao"],
                    })
        except Exception as exc:
            logger.warning("Falha ao extrair topologia do Neo4j: %s", exc)

        if not nodes:
            return {"nodes": list(DEMO_TOPOLOGY["nodes"]), "links": []}
        return {"nodes": list(nodes.values()), "links": links}


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
