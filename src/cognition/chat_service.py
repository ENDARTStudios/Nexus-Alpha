"""Nexus-Alpha — Serviço de conversação (chat) sobre a memória híbrida.

Orquestra o fluxo da rota ``/api/chat``:

1. Extrai palavras-chave da pergunta do cliente.
2. Recupera fatos no **grafo** (Neo4j) e fragmentos na **memória vetorial** (Qdrant).
3. Sintetiza a resposta com o ``llm_provider`` (extrativo por padrão).
4. Mantém um histórico curto por ``session_id`` (em memória, LRU limitado).

Todas as etapas externas degradam graciosamente: sem Neo4j/Qdrant o chat continua
respondendo a partir do que houver (ou informa honestamente que não há fatos).
"""
from __future__ import annotations

import logging
import re
from collections import OrderedDict
from typing import Any, Optional

from ..database.graph_connector import GraphConnector
from ..database.vector_connector import VectorConnector
from .embeddings import hash_embedding
from .llm_provider import ExtractiveResponder, get_llm_provider


logger = logging.getLogger(__name__)


_WORD_RE = re.compile(r"[0-9A-Za-zÀ-ÿ]{2,}")

STOPWORDS = {
    "que", "qual", "quais", "como", "onde", "quando", "porque", "por", "para",
    "sobre", "the", "and", "for", "with", "what", "when", "where", "why", "how",
    "uma", "das", "dos", "com", "sem", "seu", "sua", "meu", "minha", "voce",
    "você", "isso", "isto", "aquilo", "tem", "sao", "são", "está", "esta",
    "ser", "mais", "menos", "muito", "pode", "fazer", "gostaria", "queria",
    "de", "da", "do", "em", "no", "na", "os", "as", "um", "ou", "ao", "se",
    "me", "te", "nos", "eu", "tu", "ele", "ela", "vou", "quero", "saber",
}


def extract_keywords(text: str, max_keywords: int = 6) -> list[str]:
    """Extrai termos úteis (sem stopwords) para consulta ao grafo/vetor."""
    seen: list[str] = []
    for token in _WORD_RE.findall(text or ""):
        lowered = token.lower()
        if lowered in STOPWORDS or lowered in seen:
            continue
        seen.append(lowered)
    return seen[:max_keywords]


class ChatService:
    def __init__(
        self,
        graph: Optional[GraphConnector] = None,
        vector: Optional[VectorConnector] = None,
        llm: Optional[Any] = None,
        max_sessions: int = 200,
        history_turns: int = 6,
        embedding_dim: Optional[int] = None,
    ) -> None:
        self.graph = graph or GraphConnector()
        self.vector = vector or VectorConnector()
        self.llm = llm or get_llm_provider()
        self.max_sessions = max_sessions
        self.history_turns = history_turns
        self.embedding_dim = embedding_dim or getattr(self.vector, "embedding_dim", 384)
        self._sessions: "OrderedDict[str, list[dict[str, str]]]" = OrderedDict()

    def reset(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def _remember(self, session_id: str, role: str, content: str) -> None:
        history = self._sessions.setdefault(session_id, [])
        history.append({"role": role, "content": content})
        del history[: -self.history_turns * 2]
        self._sessions.move_to_end(session_id)
        while len(self._sessions) > self.max_sessions:
            self._sessions.popitem(last=False)

    async def retrieve_context(self, message: str) -> tuple[list[dict[str, Any]], list[str]]:
        """Recuperação híbrida: grafo (Neo4j) + memória vetorial (Qdrant)."""
        steps: list[str] = []
        facts: list[dict[str, Any]] = []
        keywords = extract_keywords(message)
        steps.append(
            "Interpretando a pergunta (termos: %s)." % (", ".join(keywords) or "—")
        )

        try:
            rows = await self.graph.search_context(keywords)
        except Exception as exc:
            logger.warning("Grafo indisponível no chat: %s", exc)
            rows = []
        for row in rows or []:
            fact = "{} {} {}".format(
                row.get("subject", ""), row.get("predicate", ""), row.get("object", "")
            ).strip()
            if fact:
                facts.append({"fact": fact, "source": "neo4j"})
        if rows:
            steps.append(f"Grafo de conhecimento: {len(rows)} relação(ões) encontrada(s).")
        else:
            steps.append("Grafo sem relações correspondentes — consultando memória vetorial.")

        try:
            hits = self.vector.query_similarity(
                hash_embedding(message, self.embedding_dim), limit=3
            )
        except Exception as exc:
            logger.warning("Memória vetorial indisponível no chat: %s", exc)
            hits = []
        for hit in hits or []:
            payload = hit.get("payload", {}) or {}
            text = payload.get("text") or payload.get("content") or ""
            if text:
                facts.append({
                    "fact": text[:400],
                    "source": payload.get("url") or payload.get("source_url") or "qdrant",
                })
        if hits:
            steps.append(f"Memória vetorial: {len(hits)} fragmento(s) recuperado(s).")

        return facts, steps

    async def answer(self, message: str, session_id: str = "default") -> dict[str, Any]:
        message = (message or "").strip()
        session_id = session_id or "default"
        steps = ["Recebendo a pergunta."]

        if not message:
            return {
                "reply": "Por favor, envie uma mensagem para eu poder ajudar.",
                "session_id": session_id,
                "reasoning_steps": steps,
                "sources": [],
                "provider": self.llm.name,
                "context_size": 0,
            }

        if self._sessions.get(session_id):
            steps.append(
                f"Histórico da sessão: {len(self._sessions[session_id])} turno(s)."
            )

        facts, retrieval_steps = await self.retrieve_context(message)
        steps.extend(retrieval_steps)
        steps.append("Sintetizando a resposta final.")

        provider = self.llm.name
        reply = await self.llm.generate(message, facts)
        if not reply:
            reply = await ExtractiveResponder().generate(message, facts)
            provider = "extractive-fallback"

        self._remember(session_id, "user", message)
        self._remember(session_id, "assistant", reply)

        sources = sorted({f["source"] for f in facts if f.get("source")})
        return {
            "reply": reply,
            "session_id": session_id,
            "reasoning_steps": steps,
            "sources": sources,
            "provider": provider,
            "context_size": len(facts),
        }
