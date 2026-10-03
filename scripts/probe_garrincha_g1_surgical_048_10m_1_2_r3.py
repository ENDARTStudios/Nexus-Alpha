"""Fase B do #048.10M.1.2.R3 — probe cirúrgico read-only (≤3 requisições).

Ordem exata do task (caminhos derivados de logs do piloto e seeds):
1. https://www.rsssfbrasil.com/sel/jogclub.htm  (jogadores-por-clube)
2. https://www.rsssf.org/tablesb/brazchamp.html (200 OK no piloto)
3. https://www.rsssf.org/sacups/copalib.html    (200 OK no piloto)

Critério de confirmação por URL (§5.3): HTTP 200 E (Garrincha ou Manuel
Francisco dos Santos) E Botafogo E contexto de passagem/atuacao/defesa,
sem ambiguidade grave, fonte permitida, sem segredo/PII.

Lógica de avaliação PURA (``evaluate_surgical_probe``) para testes offline.

Saída: reports/garrincha_g1_surgical_probe_048_10m_1_2_r3.json
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx

OUT_PATH = Path("reports/garrincha_g1_surgical_probe_048_10m_1_2_r3.json")
ALLOWED_DOMAINS = {"rsssf.org", "www.rsssf.org", "rsssfbrasil.com", "www.rsssfbrasil.com"}
PROHIBITED_FRAGMENTS = (
    "transfermarkt", "soccerway", "worldfootball", "fbref", "almanaquedosclubes",
)
BUDGET = {
    "max_requests_total": 3,
    "max_requests_per_domain": 2,
    "timeout_seconds": 15,
    "delay_between_requests_seconds": 3,
    "max_retries": 0,
}
SURGICAL_URLS = [
    "https://www.rsssfbrasil.com/sel/jogclub.htm",
    "https://www.rsssf.org/tablesb/brazchamp.html",
    "https://www.rsssf.org/sacups/copalib.html",
]

SUBJECT_TOKENS = ("garrincha", "manuel francisco dos santos")
OBJECT_TOKEN = "botafogo"
CONTEXT_TOKENS = (
    "jogou", "defendeu", "atuou", "passou", "career", "played", "appeare",
    "clube", "club", "squad", "lineup", "elenco",
)


def sanitize_excerpt(html: str, limit: int = 200) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    idx = text.lower().find("garrincha")
    if idx == -1:
        idx = text.lower().find("manuel francisco")
    if idx == -1:
        return text[:limit].strip()
    start = max(0, idx - 80)
    return text[start : start + limit].strip()


def evaluate_surgical_probe(
    order: int,
    url: str,
    http_status: int,
    final_url: str,
    body: str | None,
) -> dict:
    """PURO — avalia um probe cirúrgico contra o critério §5.3 do task."""
    domain = urlparse(url).netloc
    prohibited = any(frag in url.lower() for frag in PROHIBITED_FRAGMENTS)
    low = (body or "").lower()
    mentions_garrincha = any(tok in low for tok in SUBJECT_TOKENS)
    mentions_botafogo = OBJECT_TOKEN in low
    mentions_context = any(tok in low for tok in CONTEXT_TOKENS)
    confirmed = bool(
        http_status == 200
        and domain in ALLOWED_DOMAINS
        and not prohibited
        and mentions_garrincha
        and mentions_botafogo
        and mentions_context
    )
    return {
        "order": order,
        "domain": domain,
        "url": url,
        "http_status": http_status,
        "final_url": final_url,
        "blocked_or_rate_limited": http_status in (403, 429),
        "mentions_garrincha": mentions_garrincha,
        "mentions_manuel_francisco_dos_santos": "manuel francisco dos santos" in low,
        "mentions_botafogo": mentions_botafogo,
        "mentions_defendeu_context": mentions_context,
        "evidence_excerpt_sanitized": sanitize_excerpt(body) if body else None,
        "source_policy": "PROHIBIDO" if prohibited else "allowed",
        "confirmed_for_g1": confirmed,
    }


def main() -> int:
    results: list[dict] = []
    used = 0
    client = httpx.Client(
        timeout=BUDGET["timeout_seconds"],
        headers={"User-Agent": "NexusAlpha-R3-ReadOnly/1.0 (governed surgical probe; no ingest)"},
        follow_redirects=True,
    )
    try:
        for i, url in enumerate(SURGICAL_URLS, start=1):
            if used >= BUDGET["max_requests_total"]:
                break
            if used > 0:
                time.sleep(BUDGET["delay_between_requests_seconds"])
            try:
                res = client.get(url)
                row = evaluate_surgical_probe(i, url, res.status_code, str(res.url), res.text)
            except Exception as exc:  # noqa: BLE001 — registra falha, sem retry
                row = evaluate_surgical_probe(i, url, 0, url, None)
                row["error"] = str(exc)[:120]
            results.append(row)
            used += 1
            if row["confirmed_for_g1"]:
                break  # stop early — confirmação suficiente
    finally:
        client.close()

    confirmed_domain = next(
        (r["domain"] for r in results if r["confirmed_for_g1"]), None,
    )
    out = {
        "audit_id": "garrincha_g1_surgical_probe_048_10m_1_2_r3",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "read_only_http_probe",
        "candidate": "garrincha_botafogo",
        "budget": {
            "max_requests_total": BUDGET["max_requests_total"],
            "requests_used": used,
            "max_requests_per_domain": BUDGET["max_requests_per_domain"],
            "retries": 0,
        },
        "results": results,
        "confirmed_non_wikimedia_domain": confirmed_domain,
        "confirmed_urls": [r["url"] for r in results if r["confirmed_for_g1"]],
        "source_policy_violations": 0,
        "bypass_attempted": False,
        "result": "PASS" if confirmed_domain else "PARTIAL",
        "blocking_reason": None if confirmed_domain else (
            "nenhum dos 3 caminhos confirmou Garrincha/Manuel Francisco + Botafogo + contexto de passagem"
        ),
    }
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"ok → {OUT_PATH} · result={out['result']} · confirmed={confirmed_domain}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
