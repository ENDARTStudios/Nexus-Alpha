"""O2 — loader canônico de ambiente do Space (fonte única de verdade).

Resolve a URL base do Space a partir de ``HF_SPACE_URL`` OU ``NEXUS_SPACE_URL``
(alias histórico), normalizando a barra final. Todos os scripts (worker,
telemetria, deploy) devem usar esta função em vez de ler as variáveis ad hoc.
"""
from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Optional


def space_base_url(environ: Optional[Mapping[str, str]] = None) -> str:
    """URL base do Space sem barra final; string vazia se nenhuma variável existir."""
    env = environ if environ is not None else os.environ
    url = (env.get("HF_SPACE_URL") or env.get("NEXUS_SPACE_URL") or "").strip()
    return url.rstrip("/")


def nexus_api_token(environ: Optional[Mapping[str, str]] = None) -> str:
    """Token de ingest do Space (variável ``NEXUS_API_TOKEN``)."""
    env = environ if environ is not None else os.environ
    return env.get("NEXUS_API_TOKEN", "")
