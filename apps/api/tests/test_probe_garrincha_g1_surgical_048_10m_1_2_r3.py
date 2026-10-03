"""Testes offline do R3 Fase B — avaliação cirúrgica de probe (fixtures).

Nenhum teste faz HTTP, escreve em Neo4j/Qdrant, chama /api/ingest ou roda worker.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.probe_garrincha_g1_surgical_048_10m_1_2_r3 import (  # noqa: E402
    evaluate_surgical_probe,
    sanitize_excerpt,
    SURGICAL_URLS,
    ALLOWED_DOMAINS,
)


def eval_ok(url: str, body: str) -> dict:
    return evaluate_surgical_probe(1, url, 200, url, body)


def test_url_1_jogclub_sem_garrincha_nao_confirma() -> None:
    body = "<html><body>Botafogo jogou o campeonato. Elenco e squad histórico do clube.</body></html>"
    out = eval_ok("https://www.rsssfbrasil.com/sel/jogclub.htm", body)
    assert out["confirmed_for_g1"] is False
    assert out["mentions_botafogo"] is True
    assert out["mentions_garrincha"] is False
    assert out["source_policy"] == "allowed"


def test_url_1_com_garrincha_e_botafogo_confirma() -> None:
    body = "<html><body>Garrincha jogou no Botafogo por uma década. Career: 1953-1965.</body></html>"
    out = eval_ok("https://www.rsssfbrasil.com/sel/jogclub.htm", body)
    assert out["confirmed_for_g1"] is True
    assert out["mentions_garrincha"] is True
    assert out["mentions_defendeu_context"] is True


def test_manuel_francisco_dos_santos_tambem_confirma() -> None:
    body = "<html><body>Manuel Francisco dos Santos atuou no Botafogo.</body></html>"
    out = eval_ok("https://www.rsssf.org/tablesb/brazchamp.html", body)
    assert out["confirmed_for_g1"] is True


def test_404_nunca_confirma() -> None:
    out = evaluate_surgical_probe(1, SURGICAL_URLS[0], 404, SURGICAL_URLS[0], None)
    assert out["confirmed_for_g1"] is False
    assert out["blocked_or_rate_limited"] is False


def test_429_marca_blocked_sem_confirma() -> None:
    out = evaluate_surgical_probe(1, SURGICAL_URLS[0], 429, SURGICAL_URLS[0], None)
    assert out["blocked_or_rate_limited"] is True
    assert out["confirmed_for_g1"] is False


def test_fonte_proibida_marca_proibido_e_nao_confirma() -> None:
    out = eval_ok("https://www.transfermarkt.com/garrincha/profil", "<html>Garrincha Botafogo jogou</html>")
    assert out["source_policy"] == "PROHIBIDO"
    assert out["confirmed_for_g1"] is False


def test_garrincha_sem_botafogo_nao_confirma() -> None:
    body = "<html><body>Garrincha jogou no Corinthians em 1966.</body></html>"
    out = eval_ok("https://www.rsssf.org/tablesb/brazchamp.html", body)
    assert out["confirmed_for_g1"] is False


def test_botafogo_sem_contexto_nao_confirma() -> None:
    body = "<html><body>Botafogo campeão. Garrincha citado em lista de nomes.</body></html>"
    out = eval_ok("https://www.rsssf.org/tablesb/brazchamp.html", body)
    # "campeão" não é token de contexto; sem jogou/atuou/etc não confirma
    assert out["confirmed_for_g1"] is False


def test_ordem_das_urls_cirurgicas_e_a_do_task() -> None:
    assert SURGICAL_URLS == [
        "https://www.rsssfbrasil.com/sel/jogclub.htm",
        "https://www.rsssf.org/tablesb/brazchamp.html",
        "https://www.rsssf.org/sacups/copalib.html",
    ]
    for u in SURGICAL_URLS:
        assert urlparse_netloc(u) in ALLOWED_DOMAINS


def urlparse_netloc(u: str) -> str:
    from urllib.parse import urlparse

    return urlparse(u).netloc


def test_sanitize_excerpt_limita_200_chars() -> None:
    out = sanitize_excerpt("<html>" + "x " * 300 + "garrincha " + "y " * 300 + "</html>")
    assert len(out) <= 200
    assert "garrincha" in out.lower()
