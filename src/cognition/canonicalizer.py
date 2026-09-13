"""Nexus-Alpha — Canonicalização semântica de entidades e predicados.

Normaliza triplas cruas antes da validação/ingestão, forçando a colisão de
termos equivalentes (``IA`` ↔ ``inteligência artificial`` ↔ ``AI``) e de verbos
sinônimos (``usa`` ↔ ``emprega`` ↔ ``utiliza``). Sem isso, fatos equivalentes
escritos de formas diferentes nunca cruzam e o quórum de triangulação não fecha.

Módulo original, sem dependências externas.
"""
from __future__ import annotations

import logging
import re
from typing import Any


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SemanticCanonicalizer:
    """Mapeia entidades e predicados para formas canônicas."""

    def __init__(self) -> None:
        self.entity_synonyms: dict[str, str] = {
            # Inteligência Artificial
            "ia": "Inteligência Artificial",
            "ai": "Inteligência Artificial",
            "artificial intelligence": "Inteligência Artificial",
            "inteligência artificial": "Inteligência Artificial",
            # Machine Learning
            "ml": "Machine Learning",
            "machine learning": "Machine Learning",
            "aprendizado de máquina": "Machine Learning",
            "aprendizagem de máquina": "Machine Learning",
            # Deep Learning
            "dl": "Aprendizado Profundo",
            "deep learning": "Aprendizado Profundo",
            "aprendizado profundo": "Aprendizado Profundo",
            # Redes Neurais
            "redes neurais": "Redes Neurais",
            "rede neural": "Redes Neurais",
            "neural networks": "Redes Neurais",
            "neural network": "Redes Neurais",
            # LLM / NLP
            "llm": "Grandes Modelos de Linguagem",
            "large language models": "Grandes Modelos de Linguagem",
            "nlp": "Processamento de Linguagem Natural",
            "pln": "Processamento de Linguagem Natural",
            "processamento de linguagem natural": "Processamento de Linguagem Natural",
        }

        self.predicate_synonyms: dict[str, str] = {
            "usa": "UTILIZA",
            "usar": "UTILIZA",
            "emprega": "UTILIZA",
            "empregar": "UTILIZA",
            "utiliza": "UTILIZA",
            "utilizar": "UTILIZA",
            "roda": "EXECUTA",
            "rodar": "EXECUTA",
            "faz": "EXECUTA",
            "executa": "EXECUTA",
            "executar": "EXECUTA",
            "cria": "PRODUZ",
            "criar": "PRODUZ",
            "gera": "PRODUZ",
            "gerar": "PRODUZ",
            "produz": "PRODUZ",
            "produzir": "PRODUZ",
            "conecta": "CONECTA_A",
            "associa": "CONECTA_A",
            "vincula": "CONECTA_A",
            "é": "SER",
            "são": "SER",
            "era": "SER",
            "possui": "POSSUIR",
            "tem": "POSSUIR",
            "contém": "CONTER",
        }

    def clean_string(self, text: str) -> str:
        """Remove espaços/pontuação residuais e normaliza para minúsculas."""
        if not text:
            return ""
        text = text.strip().lower()
        text = re.sub(r"[^\w\s\-]", "", text)
        return text

    def canonicalize_entity(self, raw: str) -> str:
        cleaned = self.clean_string(raw)
        if cleaned in self.entity_synonyms:
            return self.entity_synonyms[cleaned]
        return (raw or "").strip().title()

    def canonicalize_predicate(self, raw: str) -> str:
        cleaned = self.clean_string(raw)
        if cleaned in self.predicate_synonyms:
            return self.predicate_synonyms[cleaned]
        return (raw or "").strip().upper()

    def canonicalize_triplet(self, triplet: dict[str, Any]) -> dict[str, Any]:
        """Recebe uma tripla bruta e devolve os termos mapeados nas formas canônicas."""
        return {
            "subject": self.canonicalize_entity(triplet.get("subject", "")),
            "predicate": self.canonicalize_predicate(triplet.get("predicate", "")),
            "object": self.canonicalize_entity(triplet.get("object", "")),
            "confidence": triplet.get("confidence", 0.5),
            "source_url": triplet.get("source_url", ""),
        }


if __name__ == "__main__":
    canonicalizer = SemanticCanonicalizer()
    raw_triplet_1 = {"subject": "AI", "predicate": "usa", "object": "redes neurais", "confidence": 0.9}
    raw_triplet_2 = {"subject": "Inteligência Artificial", "predicate": "emprega", "object": "Redes Neurais", "confidence": 0.85}
    print("Normalizado 1:", canonicalizer.canonicalize_triplet(raw_triplet_1))
    print("Normalizado 2:", canonicalizer.canonicalize_triplet(raw_triplet_2))
