"""Probe read-only de evidência para o piloto DEFENDEU (#048.10M.1).

Orçamento rígido (§7.1): max 45 requests no total, 15 por domínio, delay 2s
entre requests, timeout 15s, max_retries=1 (somente rede/5xx — nunca retry em
403/429, nunca User-Agent alternativo). Domínios permitidos apenas:
wikipedia PT/EN, rsssf.org, rsssfbrasil.com. Sem JS, sem CAPTCHA bypass, sem
login, sem paywall.

Salva apenas resumo sanitizado em ``.autonomous/048_10m_1/probes/<id>.json``
(nunca HTML bruto, nunca segredos). Funções puras testáveis offline.
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SELECTION_PATH = (Path(__file__).resolve().parents[1] / "reports" / "defendeu_pilot_candidate_selection_048_10m_1.json")
PROBES_DIR = Path(".autonomous/048_10m_1/probes")

MAX_REQUESTS_TOTAL = 45
MAX_REQUESTS_PER_DOMAIN = 15
TIMEOUT_SECONDS = 15
DELAY_BETWEEN_REQUESTS = 2.0
MAX_RETRIES = 1
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

ALLOWED_DOMAINS = {
    "pt.wikipedia.org",
    "en.wikipedia.org",
    "rsssf.org",
    "www.rsssf.org",
    "rsssfbrasil.com",
    "www.rsssfbrasil.com",
}

# Título canônico do artigo por candidato (pt, en). Fallback de URL 404 degrada
# a evidência daquele domínio — nunca contornar bloqueio nem adivinhar 3x.
CANDIDATE_TITLES = {
    "defendeu_manuelfranciscodossantos_001": ("Garrincha", "Garrincha"),
    "defendeu_jairzinho_002": ("Jairzinho", "Jairzinho"),
    "defendeu_zito_003": ("Zito_(futebolista)", "Zito_(footballer)"),
    "defendeu_arthurantunescoimbra_004": ("Rivelino", "Rivelino"),
    "defendeu_socratesbrasileirosampai_005": ("S%C3%B3crates_(futebolista)", "S%C3%B3crates_(footballer)"),
    "defendeu_romariodesouzafaria_006": ("Rom%C3%A1rio", "Rom%C3%A1rio"),
    "defendeu_carlosalbertotorres_007": ("Carlos_Alberto_Torres", "Carlos_Alberto_Torres"),
    "defendeu_rogerioceni_012": ("Rog%C3%A9rio_Ceni", "Rog%C3%A9rio_Ceni"),
}

# RSSSF: páginas de clubes/convocações conhecidas e estáveis (1 por objeto).
RSSSF_URLS = {
    "BOTAFOGO DE FUTEBOL E REGATAS": "http://www.rsssfbrasil.com/clubs/botafogo.htm",
    "SANTOS FUTEBOL CLUBE": "http://www.rsssfbrasil.com/clubs/santos.htm",
    "CLUBE DE REGATAS DO FLAMENGO": "http://www.rsssfbrasil.com/clubs/flamengo.htm",
    "SPORT CLUB CORINTHIANS PAULISTA": "http://www.rsssfbrasil.com/clubs/corinthians.htm",
    "CLUBE DE REGATAS VASCO DA GAMA": "http://www.rsssfbrasil.com/clubs/vasco.htm",
    "SÃO PAULO FUTEBOL CLUBE": "http://www.rsssfbrasil.com/clubs/saopaulo.htm",
}


def wikipedia_url(domain: str, title: str) -> str:
    return f"https://{domain}/wiki/{title}"


def is_allowed_url(url: str) -> bool:
    host = urllib.parse.urlparse(url).netloc.lower()
    return host in ALLOWED_DOMAINS


def extract_text_excerpt(html: str, needle: str, radius: int = 100) -> str | None:
    """Snippet sanitizado em torno da primeira ocorrência (≤200 chars)."""
    lower = html.lower()
    idx = lower.find(needle.lower())
    if idx < 0:
        return None
    start = max(0, idx - radius)
    excerpt = html[start : idx + radius]
    excerpt = re.sub(r"<[^>]+>", " ", excerpt)
    excerpt = re.sub(r"\s+", " ", excerpt).strip()
    return excerpt[:200]


def classify_evidence(html: str, candidate: dict) -> tuple[str | None, str | None]:
    """Retorna (evidence_location, excerpt_sanitizado) para o candidato."""
    needles = [candidate["object"]] + [
        a for a in candidate.get("object_aliases", []) if len(a) >= 5
    ]
    for needle in needles:
        excerpt = extract_text_excerpt(html, needle)
        if excerpt is not None:
            if "wikitable" in html.lower() or "infobox" in html.lower():
                location = "infobox"
            elif "<table" in html.lower():
                location = "table"
            else:
                location = "lead"
            return location, excerpt
    return None, None


def probe_url(
    url: str, budget: dict
) -> dict:
    """1 request orçado. Nunca contorna 403/429; retry só rede/5xx (max 1)."""
    if not is_allowed_url(url):
        return {"url": url, "http_status": None, "blocked_or_rate_limited": True, "error": "domain_not_allowed"}
    if budget["total"] >= MAX_REQUESTS_TOTAL:
        return {"url": url, "http_status": None, "blocked_or_rate_limited": True, "error": "budget_exhausted"}
    host = urllib.parse.urlparse(url).netloc.lower()
    if budget["per_domain"].get(host, 0) >= MAX_REQUESTS_PER_DOMAIN:
        return {"url": url, "http_status": None, "blocked_or_rate_limited": True, "error": "domain_budget_exhausted"}
    time.sleep(DELAY_BETWEEN_REQUESTS)
    for attempt in range(MAX_RETRIES + 1):
        budget["total"] += 1
        budget["per_domain"][host] = budget["per_domain"].get(host, 0) + 1
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                return {"url": url, "http_status": response.status, "html": response.read().decode("utf-8", "replace")}
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 429):
                return {"url": url, "http_status": exc.code, "blocked_or_rate_limited": True}
            if exc.code < 500 and attempt == 0:
                return {"url": url, "http_status": exc.code, "blocked_or_rate_limited": False}
            if attempt < MAX_RETRIES:
                time.sleep(2)
                continue
            return {"url": url, "http_status": exc.code, "blocked_or_rate_limited": False}
        except (urllib.error.URLError, OSError) as exc:  # rede/DNS/timeout: 1 retry
            if attempt < MAX_RETRIES:
                time.sleep(2)
                continue
            return {"url": url, "http_status": None, "error": type(exc).__name__, "blocked_or_rate_limited": False}
    return {"url": url, "http_status": None, "error": "unreachable", "blocked_or_rate_limited": False}


def probe_candidate(candidate: dict, budget: dict) -> dict:
    cid = candidate["candidate_id"]
    checked = []
    titles = CANDIDATE_TITLES.get(cid)
    urls: list[str] = []
    if titles:
        urls.append(wikipedia_url("pt.wikipedia.org", titles[0]))
        urls.append(wikipedia_url("en.wikipedia.org", titles[1]))
    rsssf = RSSSF_URLS.get(candidate["object"])
    if rsssf:
        urls.append(rsssf)
    confirmed_domains: list[str] = []
    for url in urls:
        result = probe_url(url, budget)
        html = result.pop("html", None)
        entry = {
            "domain": urllib.parse.urlparse(url).netloc.lower(),
            "url": url,
            "http_status": result.get("http_status"),
            "final_url": url,
            "evidence_location": None,
            "excerpt_sanitized": None,
            "blocked_or_rate_limited": result.get("blocked_or_rate_limited", False),
        }
        if html and result.get("http_status") == 200:
            location, excerpt = classify_evidence(html, candidate)
            entry["evidence_location"] = location or "none"
            entry["excerpt_sanitized"] = excerpt
            if location:
                confirmed_domains.append(entry["domain"])
        checked.append(entry)
    strength = "REAL_PAGE_READONLY" if len(confirmed_domains) >= 3 else None
    return {
        "candidate_id": cid,
        "subject": candidate["subject"],
        "object": candidate["object"],
        "domains_checked": checked,
        "confirmed_domains": confirmed_domains,
        "evidence_strength": strength,  # None → LOCAL_EXISTING_EVIDENCE pelo dry-run
        "blocking_reason": None if strength else "menos de 3 domínios confirmados por probe",
    }


def main() -> int:
    selection = json.loads(SELECTION_PATH.read_text(encoding="utf-8"))
    PROBES_DIR.mkdir(parents=True, exist_ok=True)
    budget = {"total": 0, "per_domain": {}}
    for candidate in selection["selected"]:
        report = probe_candidate(candidate, budget)
        (PROBES_DIR / f"{candidate['candidate_id']}.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(json.dumps({
            "candidate_id": report["candidate_id"],
            "confirmed": len(report["confirmed_domains"]),
            "strength": report["evidence_strength"] or "LOCAL_EXISTING_EVIDENCE",
        }, ensure_ascii=False))
    print(json.dumps({"budget_total": budget["total"], "per_domain": budget["per_domain"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
