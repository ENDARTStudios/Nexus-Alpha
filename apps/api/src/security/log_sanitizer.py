"""Nexus-Alpha — Sanitização de logs e textos (anti-vazamento de credenciais).

Expõe ``sanitize_text`` (usado por ``interceptor.py`` e por qualquer logger) e o
``SafeLogFormatter`` que aplica a máscara a toda mensagem formatada.
"""
from __future__ import annotations

import logging
import re


_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # URLs de conexão Neo4j (bolt://, bolt+s://, neo4j://, neo4j+s://) com senha
    (re.compile(r"((?:bolt|neo4j)(?:\+s|\+ssc)?://[^:@/\s]+:)[^@/\s]+(@)"), r"\1[MASKED]\2"),
    # Cabeçalho/par X-Nexus-Token
    (re.compile(r"(X-Nexus-Token['\"]?\s*[:=]\s*['\"]?)[a-zA-Z0-9_\-]+", re.IGNORECASE), r"\1[MASKED]"),
    # Chaves genéricas (api_key=, token=, password=, secret=)
    (re.compile(r"((?:api[_-]?key|token|password|secret|passwd)['\"]?\s*[:=]\s*['\"]?)[^\s'\"]{8,}", re.IGNORECASE), r"\1[MASKED]"),
    # Bearer tokens
    (re.compile(r"(Bearer\s+)[a-zA-Z0-9._\-]{8,}", re.IGNORECASE), r"\1[MASKED]"),
]


def sanitize_text(message: str) -> str:
    """Substitui qualquer credencial reconhecível por ``[MASKED]``."""
    if not isinstance(message, str):
        return message
    for pattern, replacement in _PATTERNS:
        message = pattern.sub(replacement, message)
    return message


class SafeLogFormatter(logging.Formatter):
    """Formatter que aplica a máscara anti-vazamento a cada registro."""

    def format(self, record: logging.LogRecord) -> str:
        return sanitize_text(super().format(record))


def setup_secure_logging() -> None:
    """Configura o logger raiz para usar o formatador blindado."""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(SafeLogFormatter("%(asctime)s - %(levelname)s - %(message)s"))
    if logger.handlers:
        logger.handlers.clear()
    logger.addHandler(handler)
    logging.info("Sistema de logs seguro ativado. Blindagem anti-vazamento operacional.")


if __name__ == "__main__":
    setup_secure_logging()
    logging.warning("Falha ao conectar na URL: bolt://neo4j:S3nh4Fake@neo4j-db:7687")
    logging.error("Requisição rejeitada com o cabeçalho: {'X-Nexus-Token': 'ChaveSecretaPadraoParaDesenvolvimento'}")
