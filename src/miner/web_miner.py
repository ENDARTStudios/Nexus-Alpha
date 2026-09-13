"""Nexus-Alpha — Web Mining Engine assíncrono com rotação de proxies e tratamento de erros."""
from __future__ import annotations

import asyncio
import logging
import random
import re
import ssl
import time
from pathlib import Path
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from .anti_block import AntiBlockSystem
from .agent_reach import AgentReach
from .browser_miner import BrowserMiner


logger = logging.getLogger(__name__)


class ProxyRotator:
    """Lê proxies de um arquivo (um por linha) e faz rotação round-robin com fallback."""

    def __init__(self, proxy_file: Optional[str] = None, enabled: bool = False) -> None:
        self.enabled = enabled
        self.proxies: list[str] = []
        if proxy_file and Path(proxy_file).exists():
            self.proxies = [
                line.strip() for line in Path(proxy_file).read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.startswith("#")
            ]
        self._idx = 0
        logger.info("ProxyRotator: %d proxies carregados (enabled=%s).", len(self.proxies), enabled)

    def next(self) -> Optional[str]:
        if not self.enabled or not self.proxies:
            return None
        proxy = self.proxies[self._idx % len(self.proxies)]
        self._idx += 1
        return proxy

    def report_failure(self, proxy: str) -> None:
        logger.warning("Proxy %s falhou — removendo do pool.", proxy)
        if proxy in self.proxies:
            self.proxies.remove(proxy)

    def random_order(self) -> "ProxyRotator":
        random.shuffle(self.proxies)
        return self


class WebMiner:
    NOISE_SELECTORS = [
        "nav", "footer", "header", "script", "style", "aside",
        ".ads", "#sidebar", ".comments", ".advertisement",
        ".cookie-banner", ".popup", "[role='navigation']",
        ".mw-editsection", "#catlinks", ".navbox", ".toc", ".reference",
        ".mw-empty-elt", ".printfooter", ".metadata", ".hatnote",
        ".mw-jump-link", ".noprint",
    ]

    RETRYABLE_STATUS = {403, 408, 425, 429, 500, 502, 503, 504}

    def __init__(
        self,
        user_agent: Optional[str] = None,
        timeout: float = 10.0,
        max_retries: int = 3,
        proxy_rotator: Optional[ProxyRotator] = None,
        anti_block: Optional[AntiBlockSystem] = None,
        reach: Optional[AgentReach] = None,
        renderer: Optional[BrowserMiner] = None,
        min_content_length: int = 200,
    ) -> None:
        self.timeout = timeout
        self.max_retries = max_retries
        self.anti_block = anti_block or AntiBlockSystem()
        self.headers = self.anti_block.generate_headers()
        if user_agent:
            self.headers["User-Agent"] = user_agent
        self.proxy_rotator = proxy_rotator
        self.reach = reach
        self.renderer = renderer
        self.min_content_length = min_content_length

    async def fetch_page(self, client: httpx.AsyncClient, url: str) -> str:
        last_exc: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            proxy = self.proxy_rotator.next() if self.proxy_rotator else None
            try:
                request_kwargs = dict(
                    headers=self.headers,
                    timeout=self.timeout,
                    follow_redirects=True,
                )
                if proxy:
                    request_kwargs["proxy"] = proxy
                response = await client.get(url, **request_kwargs)
                if response.status_code == 200:
                    return response.text
                if response.status_code in self.RETRYABLE_STATUS:
                    logger.warning(
                        "[%s] status %s — tentativa %d/%d",
                        url, response.status_code, attempt, self.max_retries,
                    )
                    await asyncio.sleep(min(2 ** attempt, 8))
                    continue
                logger.error("[%s] status %s não recuperável.", url, response.status_code)
                return ""
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
                last_exc = exc
                logger.warning("[%s] erro de conexão (%s) — tentativa %d/%d", url, exc, attempt, self.max_retries)
                await asyncio.sleep(min(2 ** attempt, 8))
            except (ssl.SSLError, httpx.RemoteProtocolError, httpx.DecodingError) as exc:
                last_exc = exc
                logger.warning("[%s] erro SSL/protocolo (%s) — tentativa %d/%d", url, exc, attempt, self.max_retries)
                await asyncio.sleep(min(2 ** attempt, 8))
            except httpx.HTTPError as exc:
                logger.error("[%s] erro HTTP não recuperável: %s", url, exc)
                return ""
            except Exception as exc:
                logger.error("[%s] erro inesperado: %s", url, exc)
                return ""
        logger.error("[%s] esgotado após %d tentativas (%s).", url, self.max_retries, last_exc)
        return ""

    def clean_html(self, html_content: str, source_url: str = "") -> dict:
        if not html_content:
            return {"title": "", "content": "", "metadata": {}, "payload": None}

        soup = BeautifulSoup(html_content, "html.parser")

        for selector in self.NOISE_SELECTORS:
            for element in soup.select(selector):
                element.decompose()

        title = soup.title.string.strip() if soup.title and soup.title.string else ""

        author_tag = soup.find("meta", attrs={"name": "author"})
        date_tag = soup.find("meta", attrs={"property": "article:published_time"})

        metadata = {
            "author": author_tag["content"].strip() if author_tag and author_tag.get("content") else None,
            "published_at": date_tag["content"].strip() if date_tag and date_tag.get("content") else None,
        }

        text = soup.get_text(separator=" ")
        text = re.sub(r"\s+", " ", text).strip()

        payload = self.build_payload(
            source_url=source_url,
            title=title,
            text=text,
            metadata=metadata,
        )

        return {"title": title, "content": text, "metadata": metadata, "payload": payload}

    def build_payload(
        self,
        source_url: str,
        title: str,
        text: str,
        metadata: dict,
        extracted_entities: Optional[list] = None,
    ) -> dict:
        return {
            "source_url": source_url,
            "timestamp": int(time.time()),
            "domain_score": 0.0,
            "metadata": metadata,
            "title": title,
            "content": text,
            "extracted_entities": extracted_entities or [],
        }

    async def mine_urls(self, urls: list[str], client: Optional[httpx.AsyncClient] = None) -> list[dict]:
        if client is not None:
            return await self._mine_with_client(client, urls)

        limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
        async with httpx.AsyncClient(limits=limits, verify=True) as built:
            return await self._mine_with_client(built, urls)

    async def _mine_with_client(self, client: httpx.AsyncClient, urls: list[str]) -> list[dict]:
        # Rotaciona identidade a cada ciclo de mineração
        self.headers = self.anti_block.generate_headers()
        raw_pages = await asyncio.gather(
            *[self.fetch_page(client, url) for url in urls],
            return_exceptions=False,
        )
        cleaned = []
        for url, html in zip(urls, raw_pages):
            if html:
                data = self.clean_html(html, source_url=url)
            else:
                data = {"title": "", "content": "", "metadata": {}, "payload": None}
            if len(data.get("content", "")) < self.min_content_length:
                fallback = await self._fallback_fetch(url)
                if fallback is not None:
                    data = fallback
            if data.get("payload"):
                cleaned.append(data)
        if urls:
            await self.anti_block.dynamic_delay()
        return cleaned

    async def _fallback_fetch(self, url: str) -> Optional[dict]:
        """Renderização dinâmica (browser-use) e depois primitivos do AgentReach."""
        if self.renderer is not None and self.renderer.available():
            payload = await self.renderer.fetch_rendered(url)
            if payload:
                return self._to_clean_dict(payload)
        if self.reach is not None:
            payload = await self.reach.fetch(url)
            if payload:
                return self._to_clean_dict(payload)
        return None

    @staticmethod
    def _to_clean_dict(payload: dict) -> dict:
        return {
            "title": payload.get("title", ""),
            "content": payload.get("content", ""),
            "metadata": payload.get("metadata", {}),
            "payload": payload,
        }


if __name__ == "__main__":
    miner = WebMiner()
    targets = ["https://pt.wikipedia.org/wiki/Intelig%C3%AAncia_artificial"]
    results = asyncio.run(miner.mine_urls(targets))
    print(f"Minerado: {len(results)} página(s) limpa(s).")