"""Nexus-Alpha — Conector assíncrono para Neo4j com queries Cypher.

Prioriza credenciais injetadas por variáveis de ambiente (Hugging Face) e força o
protocolo criptografado de nuvem `neo4j+s://` exigido pelo Neo4j AuraDB.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
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

MERGE (fato:Fato {chave: toLower(item.subject) + '|' + toUpper(item.predicate) + '|' + toLower(item.object)})
  ON CREATE SET fato.sujeito = item.subject, fato.predicado = toUpper(item.predicate),
                fato.objeto = item.object, fato.criado_em = timestamp()

MERGE (f)-[:CONFIRMA]->(fato)
MERGE (s)-[:MINERADO_DE]->(f)
MERGE (o)-[:MINERADO_DE]->(f)

WITH DISTINCT fato
MATCH (ff:FonteWeb)-[:CONFIRMA]->(fato)
WITH fato, count(DISTINCT ff) AS confirmacoes
SET fato.confirmacoes = confirmacoes, fato.verificado = (confirmacoes >= $quorum)
RETURN count(fato) AS total_processado
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
OPTIONAL MATCH (fa:Fato {chave: toLower(s.nome) + '|' + r.predicate + '|' + toLower(o.nome)})
RETURN DISTINCT s.nome AS subject, r.predicate AS predicate, o.nome AS object,
       coalesce(fa.verificado, false) AS verificado
LIMIT $limit
"""

TOPOLOGY_QUERY = """
MATCH (s:Conceito)-[r:RELACIONA]->(o:Conceito)
OPTIONAL MATCH (fa:Fato {chave: toLower(s.nome) + '|' + r.predicate + '|' + toLower(o.nome)})
RETURN s.nome AS sujeito, r.predicate AS relacao, o.nome AS objeto,
       coalesce(fa.verificado, false) AS verificado
LIMIT $limit
"""

DEMO_TOPOLOGY = {
    "nodes": [{"id": "Nexus-Alpha Core", "group": 1, "val": 20, "verified": False}],
    "links": [],
}

COUNT_QUERY = "MATCH (c:Conceito) RETURN count(c) AS total"

VERIFIED_QUERY = (
    "MATCH (fa:Fato) WHERE fa.verificado = true RETURN count(fa) AS total"
)

COUNT_FACTS_QUERY = "MATCH (fa:Fato) RETURN count(fa) AS total"

CONSOLIDATED_QUERY = (
    "MATCH ()-[r:RELACIONA]->() WHERE r.consolidado = true RETURN count(r) AS total"
)

HEBBIAN_QUERY = (
    "MATCH ()-[r:RELACIONA]->() WHERE coalesce(r.replays, 0) >= 2 RETURN count(r) AS total"
)

SNAPSHOT_QUERY = """
CALL { MATCH (c:Conceito) RETURN count(c) AS concepts }
CALL { MATCH (fa:Fato)
       RETURN count(fa) AS facts,
              sum(CASE WHEN fa.verificado THEN 1 ELSE 0 END) AS verified }
CALL { MATCH ()-[r:RELACIONA]->()
       RETURN count(r) AS relations,
              sum(CASE WHEN r.consolidado THEN 1 ELSE 0 END) AS consolidated,
              sum(CASE WHEN coalesce(r.replays, 0) >= 2 THEN 1 ELSE 0 END) AS hebbian }
CALL { MATCH (e:Episodio)
       RETURN count(e) AS episodes, toString(max(e.created_at)) AS last_episode }
RETURN concepts, facts, verified, consolidated, hebbian, episodes, last_episode
"""

EPISODE_MERGE_QUERY = """
UNWIND $episodes AS item
MERGE (e:Episodio {fact_hash: item.fact_hash, day: item.day})
  ON CREATE SET e.id = item.id,
                e.created_at = datetime(item.created_at),
                e.last_seen_at = datetime(item.created_at),
                e.source_domain = item.source_domain,
                e.subject = item.subject,
                e.predicate = item.predicate,
                e.object = item.object,
                e.status = item.status,
                e.replays = 1,
                e.weight = 0.1
  ON MATCH SET  e.replays = e.replays + 1,
                e.last_seen_at = datetime(item.created_at),
                e.status = item.status,
                e.weight = (e.replays + 1) * 0.1
RETURN count(e) AS total_processado
"""

EPISODE_RECENT_QUERY = """
MATCH (e:Episodio)
RETURN e.id AS id,
       toString(e.created_at) AS created_at,
       e.source_domain AS source_domain,
       e.subject AS subject,
       e.predicate AS predicate,
       e.object AS object,
       e.status AS status,
       e.replays AS replays,
       e.weight AS weight
ORDER BY e.last_seen_at DESC
LIMIT $limit
"""

EPISODE_PRUNE_AGE_QUERY = """
MATCH (e:Episodio)
WHERE e.created_at < datetime() - duration({days: $days})
WITH collect(e) AS old
FOREACH (x IN old | DETACH DELETE x)
RETURN size(old) AS removed
"""

EPISODE_PRUNE_COUNT_QUERY = """
MATCH (e:Episodio)
WITH e ORDER BY e.last_seen_at DESC
SKIP $max_count
WITH collect(e) AS extra
FOREACH (x IN extra | DETACH DELETE x)
RETURN size(extra) AS removed
"""

EPISODE_MARK_QUERY = """
UNWIND $hashes AS h
MATCH (e:Episodio {fact_hash: h})
SET e.status = $status
RETURN count(e) AS total
"""

CONSOLIDATION_QUERY = """
UNWIND $facts AS item
MERGE (s:Conceito {nome: item.subject})
  ON CREATE SET s.criado_em = timestamp()
MERGE (o:Conceito {nome: item.object})
  ON CREATE SET o.criado_em = timestamp()
MERGE (s)-[r:RELACIONA {predicate: item.predicate}]->(o)
  SET r.replays = coalesce(r.replays, 0) + item.replays,
      r.peso = coalesce(r.peso, 0.0) + item.replays * 0.1,
      r.consolidado = true,
      r.consolidated_at = $timestamp
RETURN count(item) AS total_processado
"""

SCHEMA_STATEMENTS = [
    "CREATE CONSTRAINT conceito_nome IF NOT EXISTS FOR (c:Conceito) REQUIRE c.nome IS UNIQUE",
    "CREATE CONSTRAINT fonte_url IF NOT EXISTS FOR (f:FonteWeb) REQUIRE f.url IS UNIQUE",
    "CREATE INDEX conceito_busca IF NOT EXISTS FOR (c:Conceito) ON (c.nome)",
    "CREATE INDEX episodio_created_at IF NOT EXISTS FOR (e:Episodio) ON (e.created_at)",
    "CREATE INDEX episodio_last_seen IF NOT EXISTS FOR (e:Episodio) ON (e.last_seen_at)",
    "CREATE INDEX episodio_status IF NOT EXISTS FOR (e:Episodio) ON (e.status)",
    "CREATE INDEX episodio_fact_hash IF NOT EXISTS FOR (e:Episodio) ON (e.fact_hash)",
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

        Aceita aliases de ambiente (``NEO4J_URI``/``NEO4J_URL``,
        ``NEO4J_PASSWORD``/``NEXUS_NEO4J_PASSWORD``) e resolve o quórum de
        verificação via ``NEXUS_VERIFY_QUORUM`` ou
        ``security_policy.triangulation.verify_quorum`` (default 3).
        """
        try:
            cfg: dict[str, Any] = {}
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f) or {}
            except FileNotFoundError:
                logger.warning("settings.yaml não encontrado (%s) — usando defaults.", self.config_path)

            graph = cfg.get("database", {}).get("graph", {})
            triangulation = cfg.get("security_policy", {}).get("triangulation", {})

            self.uri = (
                os.environ.get("NEO4J_URI")
                or os.environ.get("NEO4J_URL")
                or graph.get("uri", "bolt://localhost:7687")
            )
            self.password = (
                os.environ.get("NEO4J_PASSWORD")
                or os.environ.get("NEXUS_NEO4J_PASSWORD")
            )
            if not self.password:
                password_env = graph.get("password_env", "NEXUS_NEO4J_PASSWORD")
                self.password = os.getenv(password_env) or "NexusSecurePass2026"
            self.user = os.environ.get("NEO4J_USER") or graph.get("user", "neo4j")
            self.pool_size = graph.get("pool_size", 50)

            raw_quorum = (
                os.environ.get("NEXUS_VERIFY_QUORUM")
                or triangulation.get("verify_quorum")
                or 3
            )
            try:
                self.verify_quorum = max(1, int(raw_quorum))
            except (TypeError, ValueError):
                logger.warning("NEXUS_VERIFY_QUORUM inválido (%r) — usando 3.", raw_quorum)
                self.verify_quorum = 3

            # [CORREÇÃO - ISSUE #017]: força o protocolo seguro exigido pelo AuraDB
            if self.uri.startswith("bolt://"):
                self.uri = self.uri.replace("bolt://", "neo4j+s://", 1)
            elif self.uri.startswith("neo4j://"):
                self.uri = self.uri.replace("neo4j://", "neo4j+s://", 1)

            logger.info(
                "Configuração carregada. Alvo: %s | quórum de verificação=%d",
                self.uri.split("@")[-1] or self.uri,
                self.verify_quorum,
            )
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

    async def _count(self, query: str, label: str) -> int:
        try:
            if self.driver is None:
                await self.connect()
            async with self.driver.session() as session:
                result = await session.run(query)
                record = await result.single()
                return int(record["total"]) if record else 0
        except Exception as exc:
            logger.warning("Falha ao contar %s: %s", label, exc)
            return 0

    async def count_facts(self) -> int:
        """Total de nós :Fato (triplas registradas)."""
        return await self._count(COUNT_FACTS_QUERY, "fatos")

    async def count_consolidated(self) -> int:
        """Total de arestas consolidadas (Hebbian: repetição >= limiar)."""
        return await self._count(CONSOLIDATED_QUERY, "consolidados")

    async def count_hebbian(self) -> int:
        """Arestas reforçadas por repetição (replays >= 2) — derivado do grafo."""
        return await self._count(HEBBIAN_QUERY, "pares hebbianos")

    async def graph_snapshot(self) -> dict[str, int]:
        """Todos os contadores em UMA consulta (evita corrida/cold-start no Space)."""
        empty = {
            "concepts": 0,
            "facts": 0,
            "verified": 0,
            "consolidated": 0,
            "hebbian": 0,
            "episodes": 0,
            "last_episode": None,
            "ok": False,
        }
        try:
            if self.driver is None:
                await self.connect()
            async with self.driver.session() as session:
                result = await session.run(SNAPSHOT_QUERY)
                record = await result.single()
                if record is None:
                    return empty
                return {
                    "concepts": int(record["concepts"] or 0),
                    "facts": int(record["facts"] or 0),
                    "verified": int(record["verified"] or 0),
                    "consolidated": int(record["consolidated"] or 0),
                    "hebbian": int(record["hebbian"] or 0),
                    "episodes": int(record["episodes"] or 0),
                    "last_episode": record["last_episode"],
                    "ok": True,
                }
        except Exception as exc:
            logger.warning("Falha no snapshot do grafo: %s", exc)
            return empty

    async def persist_episodes(self, episodes: list[dict[str, Any]]) -> int:
        """Episódios duráveis com MERGE idempotente (agregado por fact_hash+day)."""
        if not episodes:
            return 0
        try:
            if self.driver is None:
                await self.connect()
            async with self.driver.session() as session:
                result = await session.run(EPISODE_MERGE_QUERY, episodes=episodes)
                record = await result.single()
                total = int(record["total_processado"]) if record else 0
                logger.info("Episódios persistentes: %d registrado(s)/agregado(s).", total)
                return total
        except Exception as exc:
            logger.warning("Falha ao persistir episódios: %s", exc)
            return 0

    async def recent_episodes(self, limit: int = 20) -> list[dict[str, Any]]:
        """Lê os episódios duráveis mais recentes (lista vazia se indisponível)."""
        try:
            if self.driver is None:
                await self.connect()
            async with self.driver.session() as session:
                result = await session.run(EPISODE_RECENT_QUERY, limit=limit)
                return [dict(record) async for record in result]
        except Exception as exc:
            logger.warning("Falha ao ler episódios duráveis: %s", exc)
            return []

    async def prune_episodes(self, days: int = 30, max_count: int = 10000) -> int:
        """Retenção: remove por idade e depois por volume. Retorna o total removido."""
        removed = 0
        try:
            if self.driver is None:
                await self.connect()
            async with self.driver.session() as session:
                for query, params in (
                    (EPISODE_PRUNE_AGE_QUERY, {"days": days}),
                    (EPISODE_PRUNE_COUNT_QUERY, {"max_count": max_count}),
                ):
                    result = await session.run(query, **params)
                    record = await result.single()
                    removed += int(record["removed"]) if record else 0
            if removed:
                logger.info("Retenção de episódios: %d removido(s).", removed)
        except Exception as exc:
            logger.warning("Falha na retenção de episódios: %s", exc)
        return removed

    async def mark_episodes_status(self, fact_hashes: list[str], status: str = "consolidado") -> int:
        """Atualiza o status de episódios duráveis (ex.: após consolidação)."""
        if not fact_hashes:
            return 0
        try:
            if self.driver is None:
                await self.connect()
            async with self.driver.session() as session:
                result = await session.run(
                    EPISODE_MARK_QUERY, hashes=fact_hashes, status=status
                )
                record = await result.single()
                return int(record["total"]) if record else 0
        except Exception as exc:
            logger.warning("Falha ao marcar episódios: %s", exc)
            return 0

    async def consolidate_facts(self, facts: list[dict[str, Any]]) -> int:
        """Consolidação semântica (Hebbian): fortalece arestas repetidas.

        Cada item: ``{subject, predicate, object, replays}``. Incrementa ``replays``
        e ``peso`` da aresta ``:RELACIONA`` correspondente. Retorna o total processado.
        """
        if not facts:
            return 0
        try:
            if self.driver is None:
                await self.connect()
            async with self.driver.session() as session:
                result = await session.run(
                    CONSOLIDATION_QUERY, facts=facts, timestamp=int(time.time())
                )
                record = await result.single()
                total = int(record["total_processado"]) if record else 0
                logger.info("Consolidação Hebbiana: %d fato(s) fortalecido(s).", total)
                return total
        except Exception as exc:
            logger.warning("Falha na consolidação semântica: %s", exc)
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
                    verificado = bool(record["verificado"])
                    for name in (sujeito, objeto):
                        node = nodes.setdefault(
                            name, {"id": name, "group": 1, "val": 15, "verified": False}
                        )
                        if verificado:
                            node["verified"] = True
                            node["group"] = 2
                            node["val"] = 22
                    links.append({
                        "source": sujeito,
                        "target": objeto,
                        "label": record["relacao"],
                        "verified": verificado,
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
