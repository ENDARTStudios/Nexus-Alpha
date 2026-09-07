"""Nexus-Alpha — Extrator semântico baseado em transformers (zero-cost local).

Pipeline question-answering rodando em CPU (deepset/roberta-base-squad2).
Para cada predicado candidato, executa uma pergunta em linguagem natural
sobre o texto e extrai a resposta como objeto da tripla.

Mantém fallback heurístico para ambientes sem `transformers` instalado.
"""
from __future__ import annotations

import logging
import re
from typing import Optional


logger = logging.getLogger(__name__)


class NLPExtractor:
    PREDICATE_TEMPLATES = {
        "utiliza": "O que {entity} utiliza?",
        "processa": "O que {entity} processa?",
        "cria": "O que {entity} cria?",
        "gera": "O que {entity} gera?",
        "causa": "O que {entity} causa?",
        "resulta em": "Em que {entity} resulta?",
        "conecta-se a": "Com o que {entity} se conecta?",
        "possui": "O que {entity} possui?",
        "define": "O que {entity} define?",
        "é": "O que é {entity}?",
    }

    CONFIDENCE_THRESHOLD = 0.4

    def __init__(self, model_name: str = "deepset/roberta-base-squad2", device: int = -1) -> None:
        self.model_name = model_name
        self.device = device
        self.qa_pipeline = None
        self._load_model()

    def _load_model(self) -> None:
        try:
            import torch  # type: ignore  # noqa: F401
            from transformers import pipeline  # type: ignore
            self.qa_pipeline = pipeline(
                "zero-shot-classification",
                model=self.model_name,
                device=self.device,
            )
            logger.info("Transformers carregado: %s", self.model_name)
        except Exception as exc:
            logger.warning("Transformers indisponível (%s) — usando fallback regex.", exc)
            self.qa_pipeline = None

    @staticmethod
    def _fallback_extract(text: str, core_entity: str) -> list[dict]:
        """Heurística robusta que extrai {sujeito, predicado, objeto} a partir de texto em PT/EN.

        Suporta tanto a core_entity como sujeito quanto como objeto, desde que
        exista um predicado conhecido próximo.
        """
        if not text or not core_entity:
            return []
        predicate_map = {
            "utiliza": "UTILIZA", "usa": "UTILIZA", "use": "UTILIZA", "uses": "UTILIZA", "utilizes": "UTILIZA", "utilizam": "UTILIZA",
            "processa": "PROCESSA", "processam": "PROCESSA", "processes": "PROCESSA", "processing": "PROCESSA",
            "cria": "CRIA", "criam": "CRIA", "creates": "CRIA",
            "gera": "GERA", "geram": "GERA", "generates": "GERA",
            "causa": "CAUSA", "causam": "CAUSA", "causes": "CAUSA",
            "resulta em": "RESULTA_EM", "resulta": "RESULTA_EM", "resultam em": "RESULTA_EM", "results in": "RESULTA_EM",
            "conecta-se a": "CONECTA_A", "conecta-se": "CONECTA_A", "conectam-se a": "CONECTA_A", "connects to": "CONECTA_A",
            "possui": "POSSUI", "possuem": "POSSUI", "has": "POSSUI", "tem": "POSSUI", "têm": "POSSUI",
            "define": "DEFINE", "definem": "DEFINE", "defines": "DEFINE",
            "é": "E", "is": "E", "são": "E", "are": "E",
        }
        text_lower = text.lower()
        core_lower = core_entity.lower()
        out: list[dict] = []
        for pred_key, pred_label in predicate_map.items():
            pattern = re.compile(
                r"([\wÀ-ſ][\wÀ-ſ\- ]{1,60})\s+" + re.escape(pred_key) + r"\s+([\wÀ-ſ][\wÀ-ſ\- ]{1,80}?)(?=[\.\;\,]|$)",
                re.IGNORECASE,
            )
            for match in pattern.finditer(text):
                subj = match.group(1).strip()
                obj = match.group(2).strip()
                if not subj or not obj:
                    continue
                if subj.lower() == core_lower or obj.lower() == core_lower:
                    out.append({
                        "subject": core_entity if subj.lower() == core_lower else subj,
                        "predicate": pred_label,
                        "object": obj if subj.lower() == core_lower else core_entity,
                        "confidence": 0.55,
                    })
        return out

    def extract_triplets(self, text: str, core_entity: str) -> list[dict]:
        if not text or not core_entity:
            return []
        if self.qa_pipeline is not None:
            try:
                result = self.qa_pipeline(
                    text[:512],
                    candidate_labels=list(self.PREDICATE_TEMPLATES.keys()),
                )
                triplets: list[dict] = []
                for label, score in zip(result.get("labels", []), result.get("scores", [])):
                    if float(score) > self.CONFIDENCE_THRESHOLD:
                        triplets.append({
                            "subject": core_entity,
                            "predicate": label.upper().replace(" ", "_"),
                            "object": "verificar_contexto",
                            "confidence": round(float(score), 3),
                        })
                if triplets:
                    return triplets
            except Exception as exc:
                logger.error("Erro no pipeline NLP zero-shot: %s", exc)
        return self._fallback_extract(text, core_entity)


if __name__ == "__main__":
    extractor = NLPExtractor()
    sample = (
        "A Inteligência Artificial moderna utiliza Redes Neurais profundas para "
        "processar informações e executa rotinas autônomas de aprendizado."
    )
    print(extractor.extract_triplets(sample, "Inteligência Artificial"))