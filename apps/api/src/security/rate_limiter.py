"""Nexus-Alpha — Limitador de taxa em memória (sliding window por identidade).

Protege endpoints caros (ex.: ``/api/chat``, que pode acionar o LLM) contra
abuso, sem nenhuma dependência externa (sem Redis). O estado vive no processo.

A chave é uma **identidade opaca** composta pelo chamador: ``ip:<host>`` para
rotas públicas e ``token:<fingerprint>`` para rotas autenticadas — o
fingerprint (sha256 truncado) evita que o segredo cru vaze em chaves em
memória ou na linha de log do bloqueio.

Memória é **bounded** por ``max_keys``: ao atingir o teto, janelas expiradas
são purgadas e, se ainda cheio, despeja-se a chave com atividade mais antiga
(LRU por último hit) — o número de chaves nunca cresce sem limite.
"""
from __future__ import annotations

import hashlib
import logging
import math
import time
from dataclasses import dataclass
from typing import Dict, List


logger = logging.getLogger(__name__)


def fingerprint_secret(secret: str) -> str:
    """Fingerprint não-reversível de um segredo, seguro para chave/log."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()[:12]


@dataclass
class RateLimitDecision:
    """Veredicto da verificação: permitido? quanto esperar (Retry-After)."""

    allowed: bool
    retry_after_seconds: int


class InMemoryRateLimiter:
    def __init__(
        self,
        requests_limit: int = 5,
        window_seconds: int = 60,
        max_keys: int = 10_000,
    ) -> None:
        self.requests_limit = requests_limit
        self.window_seconds = window_seconds
        self.max_keys = max_keys
        self.history: Dict[str, List[float]] = {}

    def _make_room(self, current_time: float) -> None:
        """Mantém o número de chaves dentro de ``max_keys``.

        1. Purga janelas expiradas (sem atividade dentro da janela).
        2. Se ainda no teto, despeja a chave com menor atividade recente.
           Pior caso: um chamador ativo recebe janela nova; o crescimento
           em memória permanece limitado por construção.
        """
        if len(self.history) < self.max_keys:
            return
        stale = [
            key for key, times in self.history.items()
            if not times or current_time - times[-1] > self.window_seconds
        ]
        for key in stale:
            del self.history[key]
        while len(self.history) >= self.max_keys:
            oldest_key = min(self.history, key=lambda k: self.history[k][-1])
            del self.history[oldest_key]

    def check(self, key: str) -> RateLimitDecision:
        """Verifica a cota da identidade ``key`` na janela deslizante."""
        current_time = time.time()
        self._make_room(current_time)

        timestamps = self.history.get(key)
        if timestamps is None:
            self.history[key] = [current_time]
            return RateLimitDecision(True, 0)

        valid = [t for t in timestamps if current_time - t <= self.window_seconds]
        valid.append(current_time)
        self.history[key] = valid

        if len(valid) > self.requests_limit:
            oldest = valid[0]
            retry_after = max(1, math.ceil(self.window_seconds - (current_time - oldest)))
            logger.warning(
                "RATE LIMIT: %s bloqueado (%d/%d na janela; Retry-After=%ds).",
                key, len(valid), self.requests_limit, retry_after,
            )
            return RateLimitDecision(False, retry_after)
        return RateLimitDecision(True, 0)

    def is_allowed(self, key: str) -> bool:
        """Compatibilidade: True se a identidade ainda tem cota na janela."""
        return self.check(key).allowed

    def clear_stale_keys(self) -> int:
        """Remove identidades sem atividade recente. Retorna quantas removeu."""
        current_time = time.time()
        stale = [
            key for key, times in self.history.items()
            if not times or current_time - times[-1] > self.window_seconds
        ]
        for key in stale:
            del self.history[key]
        return len(stale)
