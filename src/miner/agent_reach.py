"""Nexus-Alpha — Agent Reach adapter.

Camada de "alcance" opcional que alimenta o minerador com fontes que o scraper
estático não cobre bem: páginas JS-heavy (via Jina Reader), feeds RSS/Atom
(via feedparser) e transcrições do YouTube (via yt-dlp).

Baseado nos primitivos gratuitos usados pelo projeto Agent-Reach
(https://github.com/Panniantong/Agent-Reach): nenhuma chave de API é exigida.

Design: degradação graciosa. Se uma ferramenta/CLI não estiver disponível, o
método devolve ``None`` e registra um aviso — nunca levanta exceção para o
pipeline de mineração.
"""
from __future__ import annotations

import asyncio
import importlib.util
import logging
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Optional

import httpx


logger = logging.getLogger(__name__)


JINA_READER_BASE = "https://r.jina.ai/"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (compatible; NexusAlpha/1.2; "
    "+https://github.com/ENDARTStudios/Nexus-Alpha)"
)

_TIMESTAMP_RE = re.compile(
    r"^\d{2}:\d{2}:\d{2}\.\d{3}\s+-->\s+\d{2}:\d{2}:\d{2}\.\d{3}.*$"
)
_TAG_RE = re.compile(r"<[^>]+>")


class AgentReach:
    """Wrapper assíncrono sobre primitivos gratuitos de acesso à web."""

    def __init__(self, timeout: float = 20.0, user_agent: Optional[str] = None) -> None:
        self.timeout = timeout
        self.user_agent = user_agent or DEFAULT_USER_AGENT

    @staticmethod
    def _has_module(name: str) -> bool:
        return importlib.util.find_spec(name) is not None

    @staticmethod
    def available_tools() -> dict[str, bool]:
        """Diagnóstico: quais backends opcionais estão presentes no host."""
        return {
            "agent-reach": shutil.which("agent-reach") is not None,
            "yt-dlp": shutil.which("yt-dlp") is not None,
            "gh": shutil.which("gh") is not None,
            "feedparser": AgentReach._has_module("feedparser"),
            "jina-reader": True,  # HTTP puro — sempre disponível
        }

    def available(self) -> bool:
        """Jina Reader não exige CLI, portanto o adaptador está sempre ativo."""
        return True

    @staticmethod
    def _build_payload(url: str, title: str, text: str, provider: str) -> dict[str, Any]:
        import time

        return {
            "source_url": url,
            "timestamp": int(time.time()),
            "domain_score": 0.0,
            "metadata": {"provider": provider},
            "title": title or url,
            "content": text,
            "extracted_entities": [],
        }

    async def read_web(
        self, url: str, client: Optional[httpx.AsyncClient] = None
    ) -> Optional[dict[str, Any]]:
        """Lê uma página via Jina Reader, devolvendo markdown limpo."""
        target = f"{JINA_READER_BASE}{url}"
        headers = {"User-Agent": self.user_agent, "Accept": "text/plain"}
        owns_client = client is None
        client = client or httpx.AsyncClient(timeout=self.timeout)
        try:
            response = await client.get(target, headers=headers, follow_redirects=True)
            if response.status_code != 200:
                logger.warning("AgentReach/Jina: %s -> HTTP %s", url, response.status_code)
                return None
            text = (response.text or "").strip()
            if len(text) < 200:
                logger.info("AgentReach/Jina: conteúdo insuficiente para %s", url)
                return None
            return self._build_payload(url, "", text, "jina-reader")
        except Exception as exc:
            logger.warning("AgentReach/Jina falhou (%s): %s", url, exc)
            return None
        finally:
            if owns_client:
                await client.aclose()

    async def read_rss(self, url: str) -> Optional[dict[str, Any]]:
        """Lê um feed RSS/Atom via feedparser (se instalado)."""
        if not self._has_module("feedparser"):
            logger.info("AgentReach/RSS indisponível: feedparser não instalado.")
            return None
        try:
            import feedparser  # type: ignore

            feed = feedparser.parse(url)
            entries = getattr(feed, "entries", []) or []
            if not entries:
                return None
            blocks = []
            for entry in entries[:20]:
                title = entry.get("title", "")
                summary = entry.get("summary", "") or entry.get("description", "")
                summary = _TAG_RE.sub(" ", summary)
                blocks.append(f"{title}. {summary}".strip())
            text = "\n\n".join(b for b in blocks if b)
            if not text:
                return None
            feed_title = getattr(feed, "feed", {}).get("title", url)
            return self._build_payload(url, feed_title, text, "feedparser")
        except Exception as exc:
            logger.warning("AgentReach/RSS falhou (%s): %s", url, exc)
            return None

    @staticmethod
    def _clean_vtt(vtt_text: str) -> str:
        lines: list[str] = []
        for raw in vtt_text.splitlines():
            line = raw.strip()
            if not line or line == "WEBVTT" or line.startswith(("NOTE", "Kind:", "Language:")):
                continue
            if _TIMESTAMP_RE.match(line) or line.isdigit():
                continue
            clean = _TAG_RE.sub("", line).strip()
            if clean and (not lines or lines[-1] != clean):
                lines.append(clean)
        return " ".join(lines)

    async def read_youtube(self, url: str) -> Optional[dict[str, Any]]:
        """Extrai a transcrição de um vídeo do YouTube via yt-dlp (se instalado)."""
        if shutil.which("yt-dlp") is None:
            logger.info("AgentReach/YouTube indisponível: yt-dlp não instalado.")
            return None
        with tempfile.TemporaryDirectory() as tmp:
            try:
                proc = await asyncio.create_subprocess_exec(
                    "yt-dlp",
                    "--skip-download",
                    "--write-auto-subs",
                    "--write-subs",
                    "--sub-langs", "pt.*,en.*",
                    "--sub-format", "vtt",
                    "-o", os.path.join(tmp, "%(id)s.%(ext)s"),
                    url,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await proc.communicate()
                vtt_files = sorted(Path(tmp).glob("*.vtt"))
                if not vtt_files:
                    return None
                text = self._clean_vtt(
                    vtt_files[0].read_text(encoding="utf-8", errors="ignore")
                )
                if len(text) < 200:
                    return None
                return self._build_payload(url, "", text, "yt-dlp")
            except Exception as exc:
                logger.warning("AgentReach/YouTube falhou (%s): %s", url, exc)
                return None

    async def fetch(self, url: str) -> Optional[dict[str, Any]]:
        """Despacha a URL para o backend adequado (RSS → YouTube → web)."""
        lowered = url.lower()
        if any(token in lowered for token in (".rss", ".atom", "/feed", "/rss")):
            result = await self.read_rss(url)
            if result:
                return result
        if "youtube.com" in lowered or "youtu.be" in lowered:
            result = await self.read_youtube(url)
            if result:
                return result
        return await self.read_web(url)
