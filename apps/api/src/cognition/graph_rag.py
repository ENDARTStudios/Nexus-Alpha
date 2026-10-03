"""Nexus-Alpha — Motor GraphRAG (subgrafo contextual para a LLM).

Extrai o subgrafo de 1–2 saltos ao redor de uma entidade usando o schema real
(``:RELACIONA`` com a propriedade ``predicate``) e formata como contexto textual
para enriquecer o prompt da LLM no ``/api/chat`` (via ``ChatService``).

Degrada graciosamente (retorna ``""``) quando o grafo está indisponível.
"""
from __future__ import annotations

import logging
from typing import Any


logger = logging.getLogger(__name__)


SUBGRAPH_QUERY = """
MATCH (s:Conceito)
WHERE toLower(s.nome) CONTAINS toLower($term)
MATCH path = (s)-[rels:RELACIONA*1..2]-(neighbor:Conceito)
RETURN s.nome AS origem,
       [r IN relationships(path) | r.predicate] AS relacoes,
       neighbor.nome AS destino,
       [r IN relationships(path) | coalesce(r.confidence, 0.5)] AS confiancas
LIMIT $limit
"""


class GraphRAGEngine:
    def __init__(self, graph: Any = None) -> None:
        self.graph_db = graph

    async def retrieve_subgraph_context(self, entity_name: str, limit: int = 15) -> str:
        term = (entity_name or "").strip()
        if not term or self.graph_db is None:
            return ""
        try:
            driver = getattr(self.graph_db, "driver", None)
            connect = getattr(self.graph_db, "connect", None)
            opened_here = driver is None
            if opened_here and callable(connect):
                await connect()
                driver = getattr(self.graph_db, "driver", None)
            if driver is None:
                return ""

            lines: list[str] = []
            async with driver.session() as session:
                result = await session.run(SUBGRAPH_QUERY, term=term, limit=limit)
                async for record in result:
                    rel_path = " -> ".join(record["relacoes"] or [])
                    line = (
                        f"• Fato Mapeado: {record['origem']} via [{rel_path}] "
                        f"conecta-se a {record['destino']}"
                    )
                    if line not in lines:
                        lines.append(line)

            if opened_here:
                close = getattr(self.graph_db, "close", None)
                if callable(close):
                    await close()
        except Exception as exc:
            logger.error("GraphRAG: falha ao extrair subgrafo: %s", exc)
            return ""
        return "\n".join(lines)
