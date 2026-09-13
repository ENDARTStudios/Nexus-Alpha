"""Nexus-Alpha — Embedding local determinístico (feature hashing).

Sem dependências externas nem chave de API: converte texto em um vetor
normalizado via *signed feature hashing* (blake2b). Não substitui um modelo
semântico, mas torna a busca vetorial **lexicalmente útil** — diferente do
placeholder anterior (``[0.1] * dim``), em que todos os vetores eram idênticos
e a similaridade não carregava informação alguma.

Se um provedor de embedding real for configurado no futuro, basta trocar o
gerador mantendo a mesma assinatura.
"""
from __future__ import annotations

import hashlib
import math
import re

_TOKEN_RE = re.compile(r"[0-9a-zà-ÿ]+", re.IGNORECASE)


def hash_embedding(text: str, dim: int = 384) -> list[float]:
    """Vetor normalizado (L2) de dimensão ``dim`` para o texto informado."""
    if dim <= 0:
        raise ValueError("dim deve ser positivo")
    vector = [0.0] * dim
    tokens = _TOKEN_RE.findall((text or "").lower())
    if not tokens:
        return vector

    for token in tokens:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        value = int.from_bytes(digest, "big")
        index = value % dim
        sign = 1.0 if (value >> 8) & 1 else -1.0
        vector[index] += sign

    norm = math.sqrt(sum(component * component for component in vector))
    if norm:
        vector = [component / norm for component in vector]
    return vector


def get_embedding(text: str, dim: int = 384) -> list[float]:
    """Alias estável do embedding local (feature hashing) para uso em resolução de entidades."""
    return hash_embedding(text, dim)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Similaridade de cosseno entre dois vetores (0.0 se incompatíveis/vazios)."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if not norm_a or not norm_b:
        return 0.0
    return dot / (norm_a * norm_b)
