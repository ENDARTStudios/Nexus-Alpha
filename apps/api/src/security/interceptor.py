"""Nexus-Alpha — Interceptor de requisições da API (Task #105).

Barrera payloads gigantes (>1MB) e registra apenas metadados limpos.
"""
from __future__ import annotations

import logging
import os

from .log_sanitizer import sanitize_text

logger = logging.getLogger(__name__)

MAX_PAYLOAD_BYTES = 1_048_576  # 1 MB


class RequestInterceptor:
    def __init__(self, max_bytes: int = MAX_PAYLOAD_BYTES) -> None:
        self.max_bytes = max_bytes

    def check_size(self, content_length: int | None) -> bool:
        if content_length is None:
            return True
        if content_length > self.max_bytes:
            logger.warning(
                "Interceptor rejeitou payload: %d bytes (> %d)",
                content_length, self.max_bytes,
            )
            return False
        return True

    def sanitize_and_log(self, msg: str) -> None:
        logger.info("%s", sanitize_text(msg))

    def block_brute(self, client_ip: str, attempts: int, max_attempts: int = 10) -> bool:
        if attempts > max_attempts:
            logger.warning("Interceptor bloqueou IP %s (force brute %d/%d)", client_ip, attempts, max_attempts)
            return True
        return False