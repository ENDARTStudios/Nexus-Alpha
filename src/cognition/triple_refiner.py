"""Nexus-Alpha — Refinador determinístico de triplas (item 3-lite, sem LLM).

Pipeline leve, puro e testável aplicado **antes** da persistência (Neo4j/Qdrant):

1. filtra frases ruidosas (tutorial/UI/navegação);
2. pontua sentenças candidatas;
3. normaliza o predicado para o **vocabulário controlado**;
4. liga entidades pelo **dicionário canônico** (+ normalização) — sem embedding;
5. registra ``raw_*`` vs canônico para auditar onde a extração quebra.

Regra de ouro: **nenhuma** regra promove fato por embedding nesta fase; o quórum
de triangulação permanece 3. Embedding só entrará como sugestão (item 2).
"""
from __future__ import annotations

import re
from typing import Any, Optional

from .canonicalizer import CONTROLLED_PREDICATES, SemanticCanonicalizer


UI_MARKERS = (
    "clique", "execute o", "execute este", "instale", "instalar o pacote",
    "configure o", "rode o", "rode o comando", "abra o", "acesse o", "baixe o",
    "copie o", "import ", "print(", "console.log", "npm ", "pip install", "pip3 install",
    "```", "referências", "referencias", "ver também", "ver tambem", "editar",
    "leia mais", "saiba mais", "assine", "newsletter", "compartilhe", "siga-nos",
    "categoria:", "cookie", "tutorial", "passo a passo",
)

IMPERATIVE_STARTS = (
    "clique", "execute", "instale", "configure", "rode", "acesse", "baixe",
    "copie", "importe", "abra", "crie o", "adicione",
)

MIN_SENTENCE_LEN = 15
MAX_SENTENCE_LEN = 320
MIN_TERM_LEN = 3
MAX_TERM_TOKENS = 6


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def filter_noisy_sentence(sentence: str) -> Optional[str]:
    """Frase limpa, ou ``None`` se for ruído (tutorial/UI/curta/longa/interrogativa)."""
    text = _collapse(sentence)
    if not text:
        return None
    if len(text) < MIN_SENTENCE_LEN or len(text) > MAX_SENTENCE_LEN:
        return None
    if text.endswith("?"):
        return None
    low = text.lower()
    if low.startswith(IMPERATIVE_STARTS):
        return None
    if any(marker in low for marker in UI_MARKERS):
        return None
    return text


def _has_controlled_predicate(text: str, canonicalizer: SemanticCanonicalizer) -> bool:
    for token in re.findall(r"[^\W_]+", (text or "").lower()):
        if canonicalizer.predicate_synonyms.get(token) in CONTROLLED_PREDICATES:
            return True
    return False


def score_candidate_sentence(sentence: str, canonicalizer: Optional[SemanticCanonicalizer] = None) -> float:
    """Score heurístico 0..1 de uma frase como candidata a tripla declarativa."""
    canonicalizer = canonicalizer or SemanticCanonicalizer()
    text = _collapse(sentence)
    if not text:
        return 0.0
    low = text.lower()
    score = 0.5
    if _has_controlled_predicate(text, canonicalizer):
        score += 0.2
    if 40 <= len(text) <= 220:
        score += 0.1
    if any(marker in low for marker in UI_MARKERS):
        score -= 0.5
    if low.startswith(IMPERATIVE_STARTS) or text.endswith("?"):
        score -= 0.3
    return max(0.0, min(1.0, round(score, 3)))


def normalize_predicate(predicate: str, canonicalizer: Optional[SemanticCanonicalizer] = None) -> Optional[str]:
    """Mapeia o predicado ao vocabulário controlado; ``None`` se não pertencer."""
    canonicalizer = canonicalizer or SemanticCanonicalizer()
    canonical = canonicalizer.canonicalize_predicate(predicate)
    return canonical if canonical in CONTROLLED_PREDICATES else None


def _is_valid_term(term: str) -> bool:
    text = _collapse(term)
    if not text or len(text) < MIN_TERM_LEN:
        return False
    tokens = text.split()
    if len(tokens) > MAX_TERM_TOKENS:
        return False
    if not any(ch.isalpha() for ch in text):
        return False
    low = text.lower()
    if any(marker in low for marker in UI_MARKERS):
        return False
    return True


def link_entity(entity: str, canonicalizer: Optional[SemanticCanonicalizer] = None) -> Optional[str]:
    """Liga a entidade ao canônico (dicionário + normalização). Sem embedding."""
    canonicalizer = canonicalizer or SemanticCanonicalizer()
    canonical = canonicalizer.canonicalize_entity(entity)
    return canonical if _is_valid_term(canonical) else None


def refine_triple(raw: dict[str, Any], canonicalizer: Optional[SemanticCanonicalizer] = None) -> Optional[dict[str, Any]]:
    """Refina uma tripla bruta; devolve ``None`` se for ruído/rejeitada."""
    canonicalizer = canonicalizer or SemanticCanonicalizer()
    raw_subject = str(raw.get("subject", ""))
    raw_predicate = str(raw.get("predicate", ""))
    raw_object = str(raw.get("object", ""))

    subject = link_entity(raw_subject, canonicalizer)
    predicate = normalize_predicate(raw_predicate, canonicalizer)
    obj = link_entity(raw_object, canonicalizer)
    if not subject or not predicate or not obj or subject == obj:
        return None

    try:
        confidence = float(raw.get("confidence", 0.5))
    except (TypeError, ValueError):
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))

    refined: dict[str, Any] = {
        "subject": subject,
        "predicate": predicate,
        "object": obj,
        "confidence": round(confidence, 3),
        "raw_subject": raw_subject,
        "raw_predicate": raw_predicate,
        "raw_object": raw_object,
        "extraction_confidence": round(confidence, 3),
    }
    if "source_url" in raw:
        refined["source_url"] = raw["source_url"]
    return refined
