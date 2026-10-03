"""Fase B do #048.10M.1.2.R2 — probe read-only de domínio não-Wikimedia
para Garrincha --DEFENDEU--> Botafogo.

Orçamento rígido: max_requests_total=6, max_requests_per_domain=3,
timeout 15s, delay 3s entre requests, zero retries, sem burst/JS/CAPTCHA
bypass/login/paywall/UA alternativo após 403/429.

Salva apenas resumos sanitizados em
.autonomous/048_10m_1_2_r2/probes/garrincha_<domain>.json
(nada de HTML cru, payloads grandes ou segredos).

Lógica de avaliação é PURA (``evaluate_probe``) para testes offline.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx

OUT_DIR = Path(".autonomous/048_10m_1_2_r2/probes")
ALLOWED_DOMAINS = {"rsssf.org", "www.rsssf.org", "rsssfbrasil.com", "www.rsssfbrasil.com"}
PROHIBITED = (
    "transfermarkt", "soccerway", "worldfootball", "fbref", "almanaquedosclubes",
)
BUDGET = {
    "max_requests_total": 6,
    "max_requests_per_domain": 3,
    "timeout_seconds": 15,
    "delay_between_requests_seconds": 3,
    "max_retries": 0,
}

PROBE_URLS = [
    "https://www.rsssfbrasil.com/clubes/botafogo.htm",
    "https://www.rsssf.org/players/garrincha.html",
    "https://www.rsssf.org/tablesb/botafogo.html",
]


def sanitize_excerpt(html: str, limit: int = 200) -> str:
    """PURO — extrai trecho sanitizado ao redor de 'garrincha' (ou início)."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    idx = text.lower().find("garrincha")
    if idx == -1:
        return text[:limit].strip()
    start = max(0, idx - 80)
    return text[start : start + limit].strip()


def evaluate_probe(url: str, http_status: int, final_url: str, body: str | None) -> dict:
    """PURO — avalia um probe contra o critério de evidência do task."""
    domain = urlparse(url).netloc
    allowed = domain in ALLOWED_DOMAINS
    blocked_or_rate_limited = http_status in (403, 429) or (
        http_status == 200 and body is not None and "captcha" in body.lower()
    )
    mentions_garrincha = False
    mentions_botafogo = False
    mentions_defendeu_context = False
    evidence_location = "none"
    excerpt = ""
    if body:
        low = body.lower()
        mentions_garrincha = "garrincha" in low
        mentions_botafogo = "botafogo" in low
        for marker, loc in (
            ("career", "career_section"),
            ("table", "table"),
            (" jogador", "list"),
            ("list of", "list"),
        ):
            if marker in low:
                evidence_location = loc
        if mentions_garrincha:
            excerpt = sanitize_excerpt(body)
        mentions_defendeu_context = any(
            m in low for m in ("jogou", "defendeu", "atuou", "passou", "career", "played", "apear")
        )
    return {
        "candidate": "garrincha_botafogo",
        "domain": domain,
        "url": url,
        "http_status": http_status,
        "final_url": final_url,
        "evidence_location": evidence_location,
        "excerpt_sanitized": excerpt,
        "mentions_garrincha": mentions_garrincha,
        "mentions_botafogo": mentions_botafogo,
        "mentions_defendeu_context": mentions_defendeu_context,
        "blocked_or_rate_limited": blocked_or_rate_limited,
        "source_policy": "allowed" if allowed else "PROHIBIDO",
    }


def summarize(probes: list[dict]) -> dict:
    """PURO — veredito consolidado dos probes (allowlist explícito de domínio)."""
    ok = []
    for p in probes:
        domain = urlparse(p["url"]).netloc
        if domain not in ALLOWED_DOMAINS:
            continue  # fonte fora da política nunca vira mined_plausible
        if p["http_status"] != 200 or p["blocked_or_rate_limited"]:
            continue
        if p["source_policy"] != "allowed":
            continue
        if p["mentions_garrincha"] and p["mentions_botafogo"] and p["mentions_defendeu_context"]:
            ok.append(p)
    return {
        "probes_total": len(probes),
        "non_wiki_plausible": len(ok),
        "domains_plausible": sorted({urlparse(p["url"]).netloc for p in ok}),
        "evidence_sufficient": len(ok) >= 1,
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    probes: list[dict] = []
    total = 0
    per_domain: dict[str, int] = {}
    client = httpx.Client(
        timeout=BUDGET["timeout_seconds"],
        headers={"User-Agent": "NexusAlpha-R2-ReadOnly/1.0 (governed probe; no ingest)"},
        follow_redirects=True,
    )
    try:
        for url in PROBE_URLS:
            if total >= BUDGET["max_requests_total"]:
                break
            domain = urlparse(url).netloc
            if per_domain.get(domain, 0) >= BUDGET["max_requests_per_domain"]:
                continue
            if any(prohibited in url.lower() for prohibited in PROHIBITED):
                continue
            if total > 0:
                time.sleep(BUDGET["delay_between_requests_seconds"])
            try:
                res = client.get(url)
                http_status = res.status_code
                final_url = str(res.url)
                body = res.text if http_status == 200 else None
            except Exception as exc:  # noqa: BLE001 — probe registra falha, sem retry
                probes.append(evaluate_probe(url, 0, url, None) | {"error": str(exc)[:120]})
                total += 1
                continue
            probe = evaluate_probe(url, http_status, final_url, body)
            probes.append(probe)
            safe_name = domain.replace("www.", "")
            (OUT_DIR / f"garrincha_{safe_name}.json").write_text(
                json.dumps(probe, ensure_ascii=False, indent=1) + "\n", encoding="utf-8",
            )
            total += 1
            per_domain[domain] = per_domain.get(domain, 0) + 1
    finally:
        client.close()

    summary = summarize([p for p in probes if "error" not in p])
    stamp = {
        "audit_id": "garrincha_g1_source_probes_048_10m_1_2_r2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "read_only_probe",
        "budget": BUDGET,
        "requests_used": total,
        **summary,
        "probes": probes,
    }
    (OUT_DIR / "_summary_garrincha_048_10m_1_2_r2.json").write_text(
        json.dumps(stamp, ensure_ascii=False, indent=1) + "\n", encoding="utf-8",
    )
    print("SUMMARY", json.dumps({k: stamp[k] for k in ("requests_used", "non_wiki_plausible", "domains_plausible", "evidence_sufficient")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
