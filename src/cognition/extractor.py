"""Nexus-Alpha — Extrator de entidades (sujeito/predicado/objeto) baseado em spaCy.

Implementa a Etapa 2 do plano de conclusão:
- Carrega um modelo spaCy leve (pt/en).
- Decompõe sentenças em tripletas {subject, predicate, object}.
- Atribui score de confiança baseado em clareza gramatical.

Fallback: se o modelo spaCy não estiver instalado/baixado, opera em modo
regex-heurístico para que o pipeline continue funcional.
"""
from __future__ import annotations

import collections
import logging
import re
from dataclasses import dataclass, asdict
from typing import Any, Optional

from .predicate_mapper import INVALID_PREDICATE_REASONS, validate_predicate

logger = logging.getLogger(__name__)


@dataclass
class Triple:
    subject: str
    predicate: str
    object: str
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EntityExtractor:
    """Extrator leve de tripletas semânticas a partir de texto limpo."""

    DEFAULT_PREDICATES = {
        "é", "são", "foi", "usa", "utiliza", "processa", "cria", "gera",
        "causa", "resulta", "conecta", "possui", "tem", "define",
        "is", "are", "was", "uses", "uses", "processes", "creates",
        "generates", "causes", "results", "connects", "has", "defines",
    }

    def __init__(self, model: str = "pt_core_news_sm", enable_fallback: bool = True) -> None:
        self.model_name = model
        self.enable_fallback = enable_fallback
        self._nlp = None
        self.rejection_reasons: collections.Counter = collections.Counter()
        try:
            import spacy  # type: ignore
            self._nlp = spacy.load(model)
            logger.info("spaCy carregado: %s", model)
        except Exception as exc:
            logger.warning("spaCy indisponível (%s) — usando fallback heurístico.", exc)
            self._nlp = None

    @staticmethod
    def _is_clean(token: str) -> bool:
        return bool(token) and len(token) > 1 and not token.isspace()

    @staticmethod
    def _confidence_for(subject: str, obj: str, predicate: str) -> float:
        if not subject or not obj or not predicate:
            return 0.0
        base = 0.5
        if len(subject.split()) <= 4:
            base += 0.15
        if len(obj.split()) <= 4:
            base += 0.15
        if predicate.lower() in EntityExtractor.DEFAULT_PREDICATES:
            base += 0.15
        return round(min(0.99, base), 3)

    PRONOUN_STARTS = {
        "que", "isso", "isto", "aquilo", "ele", "ela", "eles", "elas", "seu",
        "sua", "seus", "suas", "este", "esta", "estes", "estas", "esse", "essa",
        "esses", "essas", "lhe", "lhes", "me", "te", "nos", "vos", "o", "a",
        "os", "as", "algo", "tudo", "nada",
    }

    TRAILING_STOP = {
        "que", "em", "de", "da", "do", "das", "dos", "a", "o", "as", "os",
        "e", "ao", "aos", "com", "para", "por", "no", "na", "nos", "nas",
        "se", "como", "mais",
    }

    @classmethod
    def _phrase_text(cls, token, max_tokens: int = 6) -> str:
        tokens = [t for t in token.subtree if not t.is_punct and not t.is_space]
        if len(tokens) > max_tokens:
            tokens = tokens[:max_tokens]
        while tokens and tokens[-1].lower_ in cls.TRAILING_STOP:
            tokens.pop()
        return " ".join(t.text for t in tokens).strip()

    NOISE_MARKERS = {
        "portal", "categoria", "wikipédia", "wikipedia", "editar", "código",
        "ver também", "commons", "wikcionário", "wikidata", "ficheiro",
    }

    LEADING_ARTICLES = {
        "o", "a", "os", "as", "um", "uma", "uns", "umas", "the", "an",
        "this", "that", "these", "those",
    }

    @classmethod
    def _normalize_term(cls, term: str) -> str:
        """Remove artigos/determinantes iniciais para aumentar o cruzamento entre fontes."""
        tokens = term.split()
        while tokens and tokens[0].lower() in cls.LEADING_ARTICLES:
            tokens.pop(0)
        return " ".join(tokens).strip()

    @classmethod
    def _valid_term(cls, term: str) -> bool:
        if not term or len(term) < 3:
            return False
        if "|" in term:
            return False
        lowered = term.lower()
        if any(marker in lowered for marker in cls.NOISE_MARKERS):
            return False
        tokens = term.split()
        if len(tokens) > 5:
            return False
        if tokens[0].lower() in cls.PRONOUN_STARTS:
            return False
        # Assinatura de lista de links: 4+ tokens com 3+ capitalizados ("sopa" de nomes próprios)
        capitalized = sum(1 for t in tokens if t[:1].isupper())
        if len(tokens) >= 4 and capitalized >= 3:
            return False
        return any(ch.isalpha() for ch in term)

    def extract_spacy(self, text: str, max_triples: int = 25) -> list[Triple]:
        if self._nlp is None:
            return []
        doc = self._nlp(text)
        triples: list[Triple] = []
        for sent in doc.sents:
            root = next((t for t in sent if t.dep_ == "ROOT"), None)
            if root is None or root.pos_ not in ("VERB", "AUX"):
                continue
            predicate, predicate_reason = validate_predicate(root.lemma_)
            if predicate_reason in INVALID_PREDICATE_REASONS:
                self.rejection_reasons[predicate_reason] += 1
                continue
            if predicate is None:
                predicate = root.lemma_.strip().upper()
            subj_tok = next(
                (c for c in root.children if c.dep_ in ("nsubj", "nsubj:pass")), None
            )
            obj_tok = next(
                (
                    c for c in root.children
                    if c.dep_ in ("obj", "dobj", "iobj", "attr", "obl", "xcomp")
                ),
                None,
            )
            if subj_tok is None or obj_tok is None:
                continue
            subject = self._normalize_term(self._phrase_text(subj_tok))
            obj = self._normalize_term(self._phrase_text(obj_tok))
            if not self._valid_term(subject) or not self._valid_term(obj):
                continue
            triples.append(Triple(
                subject=subject,
                predicate=predicate,
                object=obj,
                confidence=self._confidence_for(subject, obj, predicate),
            ))
            if len(triples) >= max_triples:
                break
        return triples

    def extract_fallback(self, text: str, max_triples: int = 10) -> list[Triple]:
        """Heurística regex para SVO sem dependências externas."""
        pattern = re.compile(
            r"([A-ZÁ-Ú][\wÀ-ſ\s]{2,40}?)\s+"
            r"(" + "|".join(re.escape(p) for p in self.DEFAULT_PREDICATES) + r")\s+"
            r"([\wÀ-ſ\s]{2,40})[\.\;\,]",
            re.IGNORECASE,
        )
        triples: list[Triple] = []
        for match in pattern.finditer(text):
            subj, pred, obj = (g.strip() for g in match.groups())
            subj = self._normalize_term(subj)
            obj = self._normalize_term(obj)
            predicate, predicate_reason = validate_predicate(pred)
            if predicate_reason in INVALID_PREDICATE_REASONS:
                self.rejection_reasons[predicate_reason] += 1
                continue
            if predicate is None:
                predicate = pred.strip().upper()
            triples.append(Triple(
                subject=subj,
                predicate=predicate,
                object=obj,
                confidence=self._confidence_for(subj, obj, predicate),
            ))
            if len(triples) >= max_triples:
                break
        return triples

    def extract(self, text: str, max_triples: int = 25) -> list[Triple]:
        triples = self.extract_spacy(text, max_triples=max_triples)
        if not triples and self.enable_fallback:
            triples = self.extract_fallback(text, max_triples=max_triples)
        return triples

    def enrich_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Adiciona extracted_entities ao NexusPayload a partir do conteúdo minerado."""
        text = payload.get("content") or payload.get("title") or ""
        triples = self.extract(text)
        payload["extracted_entities"] = [t.to_dict() for t in triples]
        rejected = sum(self.rejection_reasons.values())
        logger.info(
            "Extrator produziu %d tripletas (%d predicados rejeitados pelo guard: %s).",
            len(triples),
            rejected,
            dict(self.rejection_reasons),
        )
        return payload


if __name__ == "__main__":
    sample = (
        "Inteligência Artificial utiliza Redes Neurais. "
        "Redes Neurais processam grandes volumes de dados. "
        "O aprendizado profundo revolucionou a visão computacional."
    )
    extractor = EntityExtractor()
    for t in extractor.extract(sample):
        print(t.to_dict())