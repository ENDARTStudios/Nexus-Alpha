"""Nexus-Alpha — Mapeador determinístico de predicados (v1.13.0 item 3.1).

Converte verbos/expressões variantes para o **vocabulário controlado** sem
embedding, sem NLP externo (spaCy etc.) e sem baixar o quórum de verificação.

Regras de projeto:
- cada predicado canônico é explícito e testado (``tests/test_predicate_mapper.py``);
- o vocabulário controlado é pequeno e auditável (<= ``MAX_CONTROLLED_PREDICATES``);
- na dúvida, **rejeitar** (``None``) em vez de criar predicado ambíguo;
- nunca inferir predicado por similaridade vaga.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Optional

from .canonicalizer import CONTROLLED_PREDICATES as BASE_PREDICATES


# --- Vocabulário controlado (auditável) ------------------------------------
# Extensões à base do canonicalizer. Cada item precisa de justificativa + teste.
EXTRA_PREDICATES: tuple[str, ...] = (
    "PRESERVA",     # X preserva Y (ex.: regularização preserva generalização)
    "TEORIZA",      # X teoriza Y (texto acadêmico)
    "É_AMIGÁVEL",   # X é amigável a Y (tech/docs: friendly, user-friendly)
)

CONTROLLED_PREDICATES: tuple[str, ...] = tuple(BASE_PREDICATES) + EXTRA_PREDICATES

# Teto do vocabulário controlado (risco de inflar demais).
MAX_CONTROLLED_PREDICATES = 30

# --- Entradas explícitas (chave = já normalizada por _normalize) ------------
EXTRA_MAP: dict[str, str] = {
    # PRESERVA
    "preserva": "PRESERVA",
    "preservam": "PRESERVA",
    "preservar": "PRESERVA",
    "preservado": "PRESERVA",
    "preservada": "PRESERVA",
    "preservacao": "PRESERVA",
    "preservir": "PRESERVA",
    "preserve": "PRESERVA",
    "preserves": "PRESERVA",
    "preserved": "PRESERVA",
    # TEORIZA
    "teoriza": "TEORIZA",
    "teorizam": "TEORIZA",
    "teorizar": "TEORIZA",
    "teoricar": "TEORIZA",
    "teorizacao": "TEORIZA",
    "teoriza se": "TEORIZA",
    # É_AMIGÁVEL
    "amigavel": "É_AMIGÁVEL",
    "amigaveis": "É_AMIGÁVEL",
    "friendly": "É_AMIGÁVEL",
    "user friendly": "É_AMIGÁVEL",
    "userfriendly": "É_AMIGÁVEL",
}

_PREDICATE_MAP: Optional[dict[str, str]] = None


def _normalize(raw: str) -> str:
    """minúsculas, sem acentos, sem pontuação, whitespace colapsado."""
    text = unicodedata.normalize("NFKD", (raw or "").strip().lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    return re.sub(r"\s+", " ", text)


def _singularize(key: str) -> str:
    """Plural básico → singular (só quando seguro)."""
    if key.endswith("s") and len(key) > 3 and not key.endswith("ss"):
        return key[:-1]
    return key


def predicate_map() -> dict[str, str]:
    """Mapa completo (buckets do canonicalizer + extensões), chaves normalizadas."""
    global _PREDICATE_MAP
    if _PREDICATE_MAP is None:
        from .canonicalizer import SemanticCanonicalizer

        base = SemanticCanonicalizer().predicate_synonyms
        merged = {**base, **EXTRA_MAP}
        _PREDICATE_MAP = {_normalize(k): v for k, v in merged.items()}
    return _PREDICATE_MAP


def normalize_predicate_key(raw: str) -> str:
    """Chave normalizada de um predicado (exposta para testes/auditoria)."""
    return _normalize(raw)


def map_predicate(raw: str) -> tuple[Optional[str], str]:
    """Mapeia ``raw`` para o vocabulário controlado.

    Retorna ``(canonical, reason)``:
    - ``(PREDICADO, "ok")`` quando há equivalência clara;
    - ``(None, "unmapped_predicate")`` quando fora do vocabulário.
    """
    key = _normalize(raw)
    if not key:
        return None, "unmapped_predicate"

    mapping = predicate_map()
    canonical = mapping.get(key)
    if canonical is None:
        canonical = mapping.get(_singularize(key))
    if canonical in CONTROLLED_PREDICATES:
        return canonical, "ok"
    return None, "unmapped_predicate"
