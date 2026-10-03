"""Nexus-Alpha — Extração canônica de triplas via LLM.

Substitui (de forma opt-in) a extração heurística por inferência guiada por um
schema canônico: predicados de um vocabulário controlado e entidades
normalizadas. O objetivo é a uniformidade estrutural na raiz da coleta, para que
triplas semanticamente equivalentes colidam e o quórum de triangulação feche.

Se nenhum LLM estiver configurado (``NEXUS_LLM_BASE_URL``), ``generate_text``
devolve ``""`` e o extrator retorna ``[]`` — o chamador deve então cair no
extrator heurístico (fallback resiliente).
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from .llm_provider import generate_text


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LLMCanonicalExtractor:
    DEFAULT_PREDICATES = ["UTILIZA", "EXECUTA", "PRODUZ", "CONECTA_A", "CONTRADIZ", "PERTENCE_A"]

    def __init__(self, allowed_predicates: Optional[List[str]] = None) -> None:
        self.allowed_predicates = allowed_predicates or list(self.DEFAULT_PREDICATES)
        self.system_prompt = (
            "Você é um extrator semântico de alta precisão para Grafos de Conhecimento.\n"
            "Sua tarefa é ler o texto e extrair fatos na estrutura (sujeito, predicado, objeto).\n\n"
            "[REGRAS ESTRITAS DE SCHEMA CANÔNICO]\n"
            f"1. O 'predicate' DEVE ser obrigatoriamente um destes: {', '.join(self.allowed_predicates)}. Não invente verbos.\n"
            "2. Simplifique e normalize 'subject' e 'object'. Use substantivos limpos, evite frases longas ou descrições.\n"
            '3. Retorne APENAS um JSON no formato: {"triplets": [{"subject": "S", "predicate": "P", "object": "O", "confidence": 0.9}]}\n'
            "4. Não adicione texto explicativo fora do JSON. Se não houver fatos claros, retorne {\"triplets\": []}."
        )

    @staticmethod
    def _clean_json(raw: str) -> str:
        text = (raw or "").strip()
        if "```json" in text:
            text = text.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in text:
            text = text.split("```", 1)[1].split("```", 1)[0].strip()
        # Fallback: isola o primeiro objeto JSON balanceado, descartando prosa residual.
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start : end + 1]
        return text

    def extract_canonical_triplets(self, text: str) -> List[Dict[str, Any]]:
        """Consome o LLM para extrair fatos dentro do vocabulário controlado."""
        if not text or len(text.strip()) < 20:
            return []

        user_prompt = f'Texto para extração:\n"""\n{text}\n"""'
        try:
            raw_response = generate_text(
                system_prompt=self.system_prompt, user_prompt=user_prompt
            )
            if not raw_response:
                return []

            parsed = json.loads(self._clean_json(raw_response))
            triplets = parsed.get("triplets", [])

            validated: List[Dict[str, Any]] = []
            for item in triplets:
                predicate = str(item.get("predicate", "")).strip().upper()
                if predicate not in self.allowed_predicates:
                    continue
                subject = str(item.get("subject", "")).strip()
                obj = str(item.get("object", "")).strip()
                if not subject or not obj:
                    continue
                validated.append({
                    "subject": subject.upper(),
                    "predicate": predicate,
                    "object": obj.upper(),
                    "confidence": round(float(item.get("confidence", 0.9)), 2),
                })

            logger.info("LLM EXTRACTOR: %d triplas canônicas validadas.", len(validated))
            return validated
        except Exception as exc:
            logger.error("Erro no pipeline do LLM Canonical Extractor: %s", exc)
            return []
