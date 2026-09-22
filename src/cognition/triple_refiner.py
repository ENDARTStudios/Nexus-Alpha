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

import collections
import hashlib
import json
import logging
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .canonicalizer import SemanticCanonicalizer
from .predicate_mapper import CONTROLLED_PREDICATES, map_predicate

logger = logging.getLogger(__name__)


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
        if map_predicate(token)[0]:
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
    return map_predicate(predicate)[0]


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


def refine_triple_ex(
    raw: dict[str, Any], canonicalizer: Optional[SemanticCanonicalizer] = None
) -> tuple[Optional[dict[str, Any]], str]:
    """Como :func:`refine_triple`, mas devolve também o motivo (reason).

    Motivos: ``ok``, ``missing_entity``, ``unmapped_predicate``, ``self_loop``.
    """
    canonicalizer = canonicalizer or SemanticCanonicalizer()
    raw_subject = str(raw.get("subject", ""))
    raw_predicate = str(raw.get("predicate", ""))
    raw_object = str(raw.get("object", ""))

    subject = link_entity(raw_subject, canonicalizer)
    if not subject:
        return None, "missing_entity"

    predicate, reason = map_predicate(raw_predicate)
    if not predicate:
        return None, reason

    obj = link_entity(raw_object, canonicalizer)
    if not obj:
        return None, "missing_entity"

    if subject == obj:
        return None, "self_loop"

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
    return refined, "ok"


def refine_triple(raw: dict[str, Any], canonicalizer: Optional[SemanticCanonicalizer] = None) -> Optional[dict[str, Any]]:
    """Refina uma tripla bruta; devolve ``None`` se for ruído/rejeitada."""
    refined, _reason = refine_triple_ex(raw, canonicalizer)
    return refined


class RejectionQuarantine:
    """Quarentena **volátil** (``/tmp``) e **limitada** de triplas rejeitadas.

    Uso restrito a análise/expansão do ``PREDICATE_MAP``:
    - nunca é exposta ao frontend público;
    - nunca promove fato para o grafo;
    - teto de registros com rotação simples por tamanho.
    """

    def __init__(self, path: Optional[Path | str] = None, max_records: int = 10000) -> None:
        base = Path(path) if path is not None else Path(tempfile.gettempdir()) / "nexus_quarantine"
        try:
            base.mkdir(parents=True, exist_ok=True)
        except Exception:  # pragma: no cover - ambiente read-only
            base = Path(tempfile.gettempdir())
        self.file_path = base / "rejected_triples.jsonl"
        self.max_records = max_records
        self._count = self._current_count()
        self.reasons: collections.Counter = collections.Counter()

    def _current_count(self) -> int:
        try:
            with self.file_path.open("r", encoding="utf-8") as fh:
                return sum(1 for _ in fh)
        except FileNotFoundError:
            return 0
        except Exception:
            return 0

    def record(self, raw: dict[str, Any], reason: str, source_domain: str = "") -> None:
        if self._count >= self.max_records:
            self._rotate()
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "raw_subject": str(raw.get("subject", "")),
            "raw_predicate": str(raw.get("predicate", "")),
            "raw_object": str(raw.get("object", "")),
            "source_domain": source_domain,
            "sentence_hash": hashlib.sha256(
                f"{raw.get('subject')}|{raw.get('predicate')}|{raw.get('object')}".encode()
            ).hexdigest()[:16],
        }
        try:
            with self.file_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
            self._count += 1
            self.reasons[reason] += 1
        except Exception as exc:  # pragma: no cover - IO defensivo
            logger.warning("Falha ao gravar quarentena de rejeitados: %s", exc)

    def _rotate(self) -> None:
        try:
            self.file_path.replace(self.file_path.with_name(self.file_path.name + ".1"))
        except Exception:  # pragma: no cover
            pass
        self._count = 0

    def stats(self) -> dict[str, int]:
        return {"total": int(sum(self.reasons.values())), **{k: int(v) for k, v in self.reasons.items()}}
