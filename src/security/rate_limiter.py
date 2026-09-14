"""Nexus-Alpha — Limitador de taxa em memória (sliding window por IP).

Protege endpoints caros (ex.: ``/api/chat``, que pode acionar o LLM) contra
abuso, sem nenhuma dependência externa (sem Redis). O estado vive no processo;
``clear_stale_ips`` libera entradas inativas para conter o uso de RAM.
"""
from __future__ import annotations

import logging
import time
from typing import Dict, List


logger = logging.getLogger(__name__)


class InMemoryRateLimiter:
    def __init__(self, requests_limit: int = 5, window_seconds: int = 60) -> None:
        self.requests_limit = requests_limit
        self.window_seconds = window_seconds
        self.ip_history: Dict[str, List[float]] = {}

    def is_allowed(self, client_ip: str) -> bool:
        """True se o IP ainda tem cota na janela; False se excedeu (bloqueia)."""
        current_time = time.time()

        timestamps = self.ip_history.get(client_ip)
        if timestamps is None:
            self.ip_history[client_ip] = [current_time]
            return True

        valid = [t for t in timestamps if current_time - t <= self.window_seconds]
        valid.append(current_time)
        self.ip_history[client_ip] = valid

        if len(valid) > self.requests_limit:
            logger.warning(
                "RATE LIMIT: IP %s bloqueado (%d/%d na janela).",
                client_ip, len(valid), self.requests_limit,
            )
            return False
        return True

    def clear_stale_ips(self) -> int:
        """Remove IPs sem atividade recente. Retorna quantos removeu."""
        current_time = time.time()
        stale = [
            ip for ip, times in self.ip_history.items()
            if not times or current_time - times[-1] > self.window_seconds
        ]
        for ip in stale:
            del self.ip_history[ip]
        return len(stale)
