"""Nexus-Alpha — Canonicalização semântica de entidades e predicados.

Normaliza triplas cruas antes da validação/ingestão, forçando a colisão de
termos equivalentes (``IA`` ↔ ``inteligência artificial`` ↔ ``AI``) e de verbos
sinônimos (``usa`` ↔ ``emprega`` ↔ ``utiliza``) sob um **vocabulário controlado**.
Sem isso, fatos equivalentes escritos de formas diferentes nunca cruzam e o
quórum de triangulação não fecha (mantido em 3 — a canonicalização não o baixa).

Módulo original, sem dependências externas.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Artigos iniciais removidos da chave de lookup (mesmo conjunto do extrator,
# v1.13.0 item 3-lite #041: "A IA" e "IA" precisam colidir).
LEADING_ARTICLES = frozenset({
    "o", "a", "os", "as", "um", "uma", "uns", "umas",
    "the", "an", "this", "that", "these", "those",
})


def fold_lookup_key(text: str) -> str:
    """Chave determinística de lookup: minúsculas, sem acentos, sem artigos iniciais.

    ``_`` e ``-`` viram espaço (ex.: ``rede_neural``, ``conecta-se a``), pontuação
    é removida e espaços são colapsados. Usada tanto para consultar quanto para
    construir os dicionários — por isso variantes equivalentes sempre colidem.
    """
    folded = unicodedata.normalize("NFKD", (text or "").strip().lower())
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    folded = re.sub(r"[_-]+", " ", folded)
    folded = re.sub(r"[^\w\s]", "", folded)
    folded = re.sub(r"\s+", " ", folded).strip()
    tokens = folded.split(" ")
    while len(tokens) > 1 and tokens[0] in LEADING_ARTICLES:
        tokens.pop(0)
    return " ".join(tokens)


def _dedupe_folded(mapping: dict[str, str], name: str) -> dict[str, str]:
    """Reconstrói o dicionário com chaves foldadas; falha alto em colisão conflitante."""
    folded: dict[str, str] = {}
    for key, value in mapping.items():
        new_key = fold_lookup_key(key)
        if new_key in folded and folded[new_key] != value:
            raise ValueError(f"Colisão de chave foldada em {name}: {new_key!r}")
        folded[new_key] = value
    return folded


# Vocabulário controlado de predicados (alinhado ao LLMCanonicalExtractor).
CONTROLLED_PREDICATES = [
    "UTILIZA",
    "EXECUTA",
    "PRODUZ",
    "CONECTA_A",
    "PERTENCE_A",
    "CONTIENE",
    "CONTRADIZ",
    "DISTRIBUIR",
    "APRENDE",
    "DEFINE",
    "SER",
    "POSSUIR",
    "DERIVA_DE",
    "INFLUENCIA",
    "FUNDOU",
]


class SemanticCanonicalizer:
    """Mapeia entidades e predicados para formas canônicas."""

    def __init__(self) -> None:
        self.entity_synonyms: dict[str, str] = {
            # Inteligência Artificial
            "ia": "INTELIGÊNCIA ARTIFICIAL",
            "ai": "INTELIGÊNCIA ARTIFICIAL",
            "artificial intelligence": "INTELIGÊNCIA ARTIFICIAL",
            "inteligência artificial": "INTELIGÊNCIA ARTIFICIAL",
            "inteligencia artificial": "INTELIGÊNCIA ARTIFICIAL",
            # Machine Learning
            "ml": "MACHINE LEARNING",
            "machine learning": "MACHINE LEARNING",
            "aprendizado de máquina": "MACHINE LEARNING",
            "aprendizagem de máquina": "MACHINE LEARNING",
            "aprendizado de maquina": "MACHINE LEARNING",
            "aprendizagem de maquina": "MACHINE LEARNING",
            # Deep Learning
            "dl": "APRENDIZADO PROFUNDO",
            "deep learning": "APRENDIZADO PROFUNDO",
            "aprendizado profundo": "APRENDIZADO PROFUNDO",
            "aprendizagem profunda": "APRENDIZADO PROFUNDO",
            # Redes Neurais
            "redes neurais": "REDES NEURAIS",
            "rede neural": "REDES NEURAIS",
            "redes neurais artificiais": "REDES NEURAIS",
            "neural networks": "REDES NEURAIS",
            "neural network": "REDES NEURAIS",
            "artificial neural networks": "REDES NEURAIS",
            "ann": "REDES NEURAIS",
            # Processamento de Linguagem Natural
            "nlp": "PROCESSAMENTO DE LINGUAGEM NATURAL",
            "pln": "PROCESSAMENTO DE LINGUAGEM NATURAL",
            "processamento de linguagem natural": "PROCESSAMENTO DE LINGUAGEM NATURAL",
            "natural language processing": "PROCESSAMENTO DE LINGUAGEM NATURAL",
            # LLM
            "llm": "GRANDES MODELOS DE LINGUAGEM",
            "llms": "GRANDES MODELOS DE LINGUAGEM",
            "large language models": "GRANDES MODELOS DE LINGUAGEM",
            "grandes modelos de linguagem": "GRANDES MODELOS DE LINGUAGEM",
            # Visão Computacional
            "computer vision": "VISÃO COMPUTACIONAL",
            "visão computacional": "VISÃO COMPUTACIONAL",
            "visao computacional": "VISÃO COMPUTACIONAL",
            "cv": "VISÃO COMPUTACIONAL",
            # IA Generativa
            "genai": "IA GENERATIVA",
            "generative ai": "IA GENERATIVA",
            "ia generativa": "IA GENERATIVA",
            "inteligência artificial generativa": "IA GENERATIVA",
            # AGI
            "agi": "INTELIGÊNCIA ARTIFICIAL GERAL",
            "artificial general intelligence": "INTELIGÊNCIA ARTIFICIAL GERAL",
            "inteligência artificial geral": "INTELIGÊNCIA ARTIFICIAL GERAL",
            # Aprendizado por Reforço
            "reinforcement learning": "APRENDIZADO POR REFORÇO",
            "aprendizado por reforço": "APRENDIZADO POR REFORÇO",
            "aprendizado por reforco": "APRENDIZADO POR REFORÇO",
            # Redes Convolucionais / Transformers
            "cnn": "REDES NEURAIS CONVOLUCIONAIS",
            "convolutional neural networks": "REDES NEURAIS CONVOLUCIONAIS",
            "redes neurais convolucionais": "REDES NEURAIS CONVOLUCIONAIS",
            "transformer": "TRANSFORMERS",
            "transformers": "TRANSFORMERS",
            "transformadores": "TRANSFORMERS",
            # Domínio geral
            "dados": "DADOS",
            "data": "DADOS",
            "algoritmo": "ALGORITMO",
            "algoritmos": "ALGORITMO",
            "algorithm": "ALGORITMO",
            "algorithms": "ALGORITMO",
            "robótica": "ROBÓTICA",
            "robotica": "ROBÓTICA",
            "robotics": "ROBÓTICA",
            "ética": "ÉTICA",
            "etica": "ÉTICA",
            "ethics": "ÉTICA",
        }

        self.predicate_synonyms: dict[str, str] = {
            "usa": "UTILIZA", "usar": "UTILIZA", "usam": "UTILIZA",
            "emprega": "UTILIZA", "empregar": "UTILIZA", "empregam": "UTILIZA",
            "utiliza": "UTILIZA", "utilizar": "UTILIZA", "utilizam": "UTILIZA",
            "adota": "UTILIZA", "adotar": "UTILIZA", "adotam": "UTILIZA",
            "usa-se": "UTILIZA", "uses": "UTILIZA", "use": "UTILIZA",
            "roda": "EXECUTA", "rodar": "EXECUTA",
            "faz": "EXECUTA", "fazer": "EXECUTA",
            "executa": "EXECUTA", "executar": "EXECUTA", "executam": "EXECUTA",
            "runs": "EXECUTA", "run": "EXECUTA",
            "cria": "PRODUZ", "criar": "PRODUZ", "criam": "PRODUZ",
            "criou": "FUNDOU", "criaram": "FUNDOU", "fundou": "FUNDOU", "fundar": "FUNDOU",
            "gera": "PRODUZ", "gerar": "PRODUZ", "geram": "PRODUZ",
            "produz": "PRODUZ", "produzir": "PRODUZ", "produzem": "PRODUZ",
            "generates": "PRODUZ", "creates": "PRODUZ", "produces": "PRODUZ",
            "conecta": "CONECTA_A", "conectar": "CONECTA_A", "conecta a": "CONECTA_A",
            "associa": "CONECTA_A", "associar": "CONECTA_A",
            "vincula": "CONECTA_A", "vincular": "CONECTA_A",
            "pertence": "PERTENCE_A", "pertencem": "PERTENCE_A",
            "pertence_a": "PERTENCE_A", "pertence a": "PERTENCE_A",
            "contém": "CONTIENE", "contem": "CONTIENE", "inclui": "CONTIENE",
            "contradiz": "CONTRADIZ", "contradizem": "CONTRADIZ",
            "distribui": "DISTRIBUIR", "distribuir": "DISTRIBUIR",
            "difundiu": "DISTRIBUIR", "difundir": "DISTRIBUIR",
            "popularizou": "DISTRIBUIR", "popularizar": "DISTRIBUIR",
            "aprende": "APRENDE", "aprender": "APRENDE", "aprendem": "APRENDE",
            "define": "DEFINE", "definir": "DEFINE", "definem": "DEFINE",
            "é": "SER", "são": "SER", "era": "SER", "ser": "SER", "is": "SER", "are": "SER",
            "representa": "SER", "representam": "SER",
            "constitui": "SER", "constituem": "SER",
            "influencia": "INFLUENCIA", "influenciou": "INFLUENCIA",
            "influenciar": "INFLUENCIA", "impactou": "INFLUENCIA", "impacta": "INFLUENCIA",
            "possui": "POSSUIR", "possuem": "POSSUIR", "tem": "POSSUIR", "have": "POSSUIR", "has": "POSSUIR",
            "deriva": "DERIVA_DE", "derivam": "DERIVA_DE", "deriva de": "DERIVA_DE",
        }

        # v1.13.0 #041: dicionários indexados pela chave foldada — variantes
        # com/sem acento, com/sem artigo inicial e com `_`/`-` colidem no lookup.
        self.entity_synonyms = _dedupe_folded(self.entity_synonyms, "entity_synonyms")
        self.predicate_synonyms = _dedupe_folded(self.predicate_synonyms, "predicate_synonyms")

    def clean_string(self, text: str) -> str:
        """Chave determinística de lookup (minúsculas, sem acentos/artigos)."""
        if not text:
            return ""
        return fold_lookup_key(text)

    @staticmethod
    def _display_from_normalized(normalized: str) -> str:
        """Forma canônica determinística para entidades fora do dicionário (#041).

        Trade-off aprovado: desconhecidas equivalentes colapsam para a mesma
        string (UPPER, como os canônicos conhecidos; acentos foldados). Para
        preservar acentos de um termo, cadastrá-lo em ``entity_synonyms``.
        """
        return (normalized or "").upper()

    def canonicalize_entity(self, raw: str) -> str:
        """Sinônimo conhecido → valor canônico; desconhecido → forma determinística."""
        normalized = self.clean_string(raw)
        if not normalized:
            return ""
        resolved = self.entity_synonyms.get(normalized)
        if resolved:
            return resolved
        return self._display_from_normalized(normalized)

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
