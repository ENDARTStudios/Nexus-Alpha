"""Nexus-Alpha — Sistema anti-bloqueio (rotação de identidade + delays humanos)."""
from __future__ import annotations

import asyncio
import random
from typing import Optional


class AntiBlockSystem:
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    ]

    REFERERS = [
        "https://google.com",
        "https://bing.com",
        "https://yahoo.com",
        "https://duckduckgo.com",
        "https://scholar.google.com",
    ]

    def __init__(self, min_delay: float = 1.5, max_delay: float = 4.0) -> None:
        self.min_delay = min_delay
        self.max_delay = max_delay

    def generate_headers(self, target_url: Optional[str] = None) -> dict:
        return {
            "User-Agent": random.choice(self.USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,pt-BR;q=0.8,pt;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": random.choice(self.REFERERS),
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "cross-site",
            "Cache-Control": "max-age=0",
        }

    async def dynamic_delay(self) -> None:
        await asyncio.sleep(random.uniform(self.min_delay, self.max_delay))