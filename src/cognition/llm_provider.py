"""Nexus-Alpha — Camada de geração de linguagem natural plugável.

O pilar do projeto é Custo Zero, então a geração de resposta é abstraída:

*   ``ExtractiveResponder`` (padrão): sintetiza a resposta diretamente do
    contexto validado, sem nenhuma dependência ou chave. Funciona no runtime
    lite do Hugging Face Space.
*   ``OpenAICompatibleLLM`` (opcional): usa qualquer endpoint compatível com a
    API da OpenAI via variáveis de ambiente. Cobre Hugging Face Inference,
    OpenRouter, OpenAI e um **LLM local** servido por Ollama/vLLM
    (``NEXUS_LLM_BASE_URL=http://localhost:11434/v1``).

Se o endpoint remoto estiver configurado, ele é preferido; caso contrário, o
responder extrativo assume automaticamente — nunca há falha dura.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

import httpx


logger = logging.getLogger(__name__)


SYSTEM_PROMPT = (
    "Você é a Nexus-Alpha, uma IA de mineração semântica. Responda em português, "
    "de forma objetiva e factual, usando APENAS o contexto validado fornecido. "
    "Se o contexto não cobrir a pergunta, diga honestamente que ainda não há "
    "fatos verificados sobre o tema."
)


def _format_context(context: list[dict[str, Any]]) -> str:
    lines = []
    for item in context:
        text = item.get("fact") or item.get("text") or ""
        if text:
            source = item.get("source") or item.get("source_url") or ""
            lines.append(f"- {text}" + (f" (fonte: {source})" if source else ""))
    return "\n".join(lines)


class ExtractiveResponder:
    """Responder padrão sem dependências — sintetiza a partir do contexto."""

    name = "extractive"

    def available(self) -> bool:
        return True

    async def generate(self, question: str, context: list[dict[str, Any]]) -> str:
        facts = [item.get("fact") or item.get("text") for item in context]
        facts = [f for f in facts if f]
        if not facts:
            return (
                "Ainda não tenho fatos verificados sobre isso na minha memória. "
                "Registrei o tema para mineração no próximo ciclo autônomo."
            )
        bullets = "\n".join(f"- {fact}" for fact in facts[:5])
        return (
            "Com base no conhecimento validado que já reuni:\n"
            f"{bullets}\n\n"
            "(Resposta sintetizada diretamente da memória híbrida.)"
        )


class OpenAICompatibleLLM:
    """LLM remoto/local via endpoint compatível com a API da OpenAI."""

    name = "openai-compatible"

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 45.0,
    ) -> None:
        self.base_url = (base_url or os.environ.get("NEXUS_LLM_BASE_URL") or "").rstrip("/")
        self.api_key = api_key if api_key is not None else (os.environ.get("NEXUS_LLM_API_KEY") or "")
        self.model = model or os.environ.get("NEXUS_LLM_MODEL") or "meta-llama/Meta-Llama-3-8B-Instruct"
        self.timeout = timeout

    def available(self) -> bool:
        return bool(self.base_url and self.model)

    async def generate(self, question: str, context: list[dict[str, Any]]) -> str:
        if not self.available():
            return ""
        context_block = _format_context(context) or "(sem contexto validado)"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Contexto validado:\n{context_block}\n\nPergunta: {question}",
                },
            ],
            "temperature": 0.2,
            "max_tokens": 512,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions", json=payload, headers=headers
                )
                response.raise_for_status()
                data = response.json()
                return (data["choices"][0]["message"]["content"] or "").strip()
        except Exception as exc:
            logger.warning("LLM remoto falhou (%s) — caindo para resposta extrativa.", exc)
            return ""


def get_llm_provider() -> Any:
    """Devolve o melhor provider disponível: remoto se configurado, senão extrativo."""
    remote = OpenAICompatibleLLM()
    if remote.available():
        logger.info("LLM provider: %s (%s)", remote.name, remote.model)
        return remote
    logger.info("LLM provider: extrativo (nenhum endpoint remoto configurado).")
    return ExtractiveResponder()
