"""Nexus-Alpha — Browser Use adapter (opcional).

Renderiza páginas dinâmicas (SPA / JS-heavy) com o agente `browser-use` quando
disponível. Exige ``pip install browser-use`` **e** uma chave de LLM (ex.:
``OPENAI_API_KEY``), portanto é estritamente opt-in e degrada graciosamente
devolvendo ``None`` quando ausente — nunca levanta exceção para o pipeline.
"""
from __future__ import annotations

import importlib.util
import logging
import os
import time
from typing import Any, Optional

from .agent_reach import DEFAULT_USER_AGENT  # noqa: F401  (mantém estilo de UA do projeto)


logger = logging.getLogger(__name__)


class BrowserMiner:
    """Backend de renderização dinâmica via browser-use (requer LLM)."""

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key_env: str = "OPENAI_API_KEY",
        max_steps: int = 15,
        enabled: Optional[bool] = None,
    ) -> None:
        self.model = model
        self.api_key_env = api_key_env
        self.max_steps = max_steps
        self.enabled = self._detect() if enabled is None else enabled

    @staticmethod
    def _has_module() -> bool:
        return importlib.util.find_spec("browser_use") is not None

    def _detect(self) -> bool:
        if not self._has_module():
            logger.info("BrowserMiner: browser-use não instalado — backend dinâmico desativado.")
            return False
        if not os.environ.get(self.api_key_env):
            logger.info(
                "BrowserMiner: %s ausente — backend dinâmico desativado.", self.api_key_env
            )
            return False
        return True

    def available(self) -> bool:
        return self.enabled

    async def fetch_rendered(self, url: str) -> Optional[dict[str, Any]]:
        """Retorna o texto visível da página renderizada, ou ``None`` em falha."""
        if not self.enabled:
            return None
        try:
            from browser_use import Agent, ChatOpenAI  # type: ignore

            llm = ChatOpenAI(model=self.model)
            agent = Agent(
                task=(
                    "Return only the complete visible text content of this page, "
                    f"as plain text, with no commentary: {url}"
                ),
                llm=llm,
            )
            history = await agent.run(max_steps=self.max_steps)
            text = (history.final_result() or "").strip()
            if len(text) < 200:
                return None
            return {
                "source_url": url,
                "timestamp": int(time.time()),
                "domain_score": 0.0,
                "metadata": {"provider": "browser-use", "model": self.model},
                "title": url,
                "content": text,
                "extracted_entities": [],
            }
        except Exception as exc:
            logger.warning("BrowserMiner falhou (%s): %s", url, exc)
            return None
