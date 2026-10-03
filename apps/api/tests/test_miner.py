"""Testes do WebMiner com transporte mockado."""
from __future__ import annotations

import pytest

from src.miner.web_miner import WebMiner


SAMPLE_HTML = """
<html>
  <head><title>IA</title><meta name="author" content="Ada"></head>
  <body>
    <nav>menu inútil</nav>
    <script>alert('x')</script>
    <aside class="ads">propaganda</aside>
    <h1>Inteligência Artificial</h1>
    <p>Redes neurais profundas revolucionaram o campo.</p>
    <footer>rodapé</footer>
  </body>
</html>
"""


class FakeClient:
    def __init__(self, html_map: dict[str, str]):
        self.html_map = html_map

    async def get(self, url: str, headers=None, timeout=None, follow_redirects=None, proxy=None):
        class Resp:
            def __init__(self, status, text):
                self.status_code = status
                self.text = text

        return Resp(200, self.html_map.get(url, ""))


@pytest.mark.asyncio
async def test_clean_html_strips_noise():
    miner = WebMiner()
    fake = FakeClient({"https://example.com": SAMPLE_HTML})
    results = await miner.mine_urls(["https://example.com"], client=fake)  # type: ignore[arg-type]

    assert len(results) == 1
    text = results[0]["content"]
    for noise in ["menu inútil", "propaganda", "alert", "rodapé"]:
        assert noise not in text
    assert "Redes neurais" in text
    assert results[0]["payload"]["source_url"] == "https://example.com"