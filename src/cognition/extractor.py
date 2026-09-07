"""Nexus-Alpha — Extrator de entidades (sujeito/predicado/objeto) baseado em spaCy.

Implementa a Etapa 2 do plano de conclusão:
- Carrega um modelo spaCy leve (pt/en).
- Decompõe sentenças em tripletas {subject, predicate, object}.
- Atribui score de confiança baseado em clareza gramatical.

Fallback: se o modelo spaCy não estiver instalado/baixado, opera em modo
regex-heurístico para que o pipeline continue funcional.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, asdict
from typing import Any, Optional

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

    def extract_spacy(self, text: str, max_triples: int = 25) -> list[Triple]:
        if self._nlp is None:
            return []
        doc = self._nlp(text)
        triples: list[Triple] = []
        for sent in doc.sents:
            subj, obj, root = None, None, None
            for tok in sent:
                if "nsubj" in tok.dep_ and self._is_clean(tok.text):
                    subj = tok.text
                if "obj" in tok.dep_ and self._is_clean(tok.text):
                    obj = tok.text
                if tok.dep_ == "ROOT" and self._is_clean(tok.lemma_):
                    root = tok.lemma_.upper()
            if subj and obj and root:
                triples.append(Triple(
                    subject=subj.strip(),
                    predicate=root,
                    object=obj.strip(),
                    confidence=self._confidence_for(subj, obj, root),
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
            triples.append(Triple(
                subject=subj,
                predicate=pred.upper(),
                object=obj,
                confidence=self._confidence_for(subj, obj, pred),
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
        logger.info("Extrator produziu %d tripletas.", len(triples))
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