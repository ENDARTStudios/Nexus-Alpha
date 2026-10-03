"""Testes do probe read-only (#048.10M.1 §12.3) — offline, sem rede."""
from __future__ import annotations

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "probe_defendeu",
    Path(__file__).resolve().parents[1] / "scripts" / "probe_defendue_candidates_readonly_048_10m_1.py",
)
PROBE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(PROBE)


def test_probe_allows_only_whitelisted_domains():
    assert PROBE.is_allowed_url("https://pt.wikipedia.org/wiki/Garrincha") is True
    assert PROBE.is_allowed_url("https://en.wikipedia.org/wiki/Garrincha") is True
    assert PROBE.is_allowed_url("http://www.rsssfbrasil.com/x.htm") is True
    assert PROBE.is_allowed_url("https://www.transfermarkt.com/x") is False
    assert PROBE.is_allowed_url("https://www.soccerway.com/x") is False
    assert PROBE.is_allowed_url("https://evil.example.com/x") is False


def test_probe_budget_total_enforced():
    budget = {"total": PROBE.MAX_REQUESTS_TOTAL, "per_domain": {}}
    result = PROBE.probe_url("https://pt.wikipedia.org/wiki/X", budget)
    assert result["error"] == "budget_exhausted"
    assert result["blocked_or_rate_limited"] is True


def test_probe_budget_per_domain_enforced():
    budget = {"total": 0, "per_domain": {"pt.wikipedia.org": PROBE.MAX_REQUESTS_PER_DOMAIN}}
    result = PROBE.probe_url("https://pt.wikipedia.org/wiki/X", budget)
    assert result["error"] == "domain_budget_exhausted"


def test_probe_never_bypasses_bot_protection(monkeypatch):
    """403/429 → blocked, sem retry e sem User-Agent alternativo."""
    import urllib.error
    import urllib.request as ur

    calls = []

    class FakeResponse:
        def __init__(self):
            self.status = 200

        def read(self):
            return b"<html>ok</html>"

    class FakeHTTPError(urllib.error.HTTPError):
        def __init__(self):
            super().__init__("https://pt.wikipedia.org/wiki/X", 403, "forbidden", None, None)

    def fake_urlopen(request, timeout):
        calls.append(dict(request.headers))
        raise FakeHTTPError()

    monkeypatch.setattr(ur, "urlopen", fake_urlopen)
    budget = {"total": 0, "per_domain": {}}
    result = PROBE.probe_url("https://pt.wikipedia.org/wiki/X", budget)
    assert result["blocked_or_rate_limited"] is True
    assert result["http_status"] == 403
    assert len(calls) == 1  # sem retry em 403
    # UA fixo em todas as chamadas (nunca alternativo)
    assert all(c.get("User-agent") == PROBE.USER_AGENT for c in calls)


def test_probe_saves_sanitized_summary_only(tmp_path):
    """Resumo sanitizado: sem HTML bruto, excerpt ≤200 chars."""
    html = "<html><body>" + "x" * 5000 + " Flabbergasted " + "y" * 5000 + "</body></html>"
    candidate = {"object": "CLUBE", "object_aliases": ["Flabbergasted"]}
    location, excerpt = PROBE.classify_evidence(html, candidate)
    assert location is not None
    assert len(excerpt) <= 200
    assert "<html>" not in excerpt


def test_probe_testable_offline_with_fixture():
    html = (
        "<html><body><table class='wikitable'>História do clube Botafogo de "
        "Futebol e Regatas desde 1904.</table></body></html>"
    )
    candidate = {"object": "BOTAFOGO DE FUTEBOL E REGATAS", "object_aliases": ["Botafogo"]}
    location, excerpt = PROBE.classify_evidence(html, candidate)
    assert location in {"infobox", "table"}
    assert "Botafogo" in excerpt


def test_probe_constant_budgets():
    assert PROBE.MAX_REQUESTS_TOTAL == 45
    assert PROBE.MAX_REQUESTS_PER_DOMAIN == 15
    assert PROBE.TIMEOUT_SECONDS == 15
    assert PROBE.DELAY_BETWEEN_REQUESTS == 2.0
    assert PROBE.MAX_RETRIES == 1
