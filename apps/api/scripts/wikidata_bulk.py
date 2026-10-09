"""#056 — Extração e ingestão em massa via Wikidata SPARQL (quebra do acervo de ~100 URLs).

Fonte: query.wikidata.org (gratuita, sem auth, licença CC0). Converte fatos estruturados
(carreiras P54 → DEFENDEU; localização P131 → LOCALIZADO_EM) em payloads no formato
IngestionPayload, agrupados por item Wikidata (source_url = item), e envia via
/api/ingest — o MESMO pipeline de extração/contabilidade do worker.

D11: dotenv lazy. O2: space_base_url. #054.3: bounded retry com Retry-After.

Modos:
  extract-careers --limit N --out JSONL   (jogadores com P54 em clubes brasileiros)
  extract-stadiums --limit N --out JSONL  (estádios brasileiros com P131 cidade)
  ingest --jsonl FILE [--sleep SECONDS]   (POST dos payloads ao Space)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "Nexus-Alpha/1.0 wikidata bulk ingest (contato: endart.studios@gmail.com)"
BRASIL = "wd:Q155"
CLUBE_DE_FUTEBOL = "wd:Q476028"
ESTADIO = "wd:Q483110"

CAREERS_QUERY = """
SELECT ?club ?clubLabel ?playerLabel WHERE {
  ?club wdt:P31/wdt:P279* wd:Q476028 ;
        wdt:P17 wd:Q155 .
  ?player wdt:P54 ?club .
  ?club rdfs:label ?clubLabel . FILTER(LANG(?clubLabel) = "pt")
  ?player rdfs:label ?playerLabel . FILTER(LANG(?playerLabel) = "pt")
}
LIMIT {limit}
"""

STADIUMS_QUERY = """
SELECT ?stadium ?stadiumLabel ?cityLabel WHERE {
  ?stadium wdt:P31/wdt:P279* wd:Q483110 ;
           wdt:P17 wd:Q155 ;
           wdt:P131 ?city .
  ?stadium rdfs:label ?stadiumLabel . FILTER(LANG(?stadiumLabel) = "pt")
  ?city rdfs:label ?cityLabel . FILTER(LANG(?cityLabel) = "pt")
}
LIMIT {limit}
"""

VICTORIES_QUERY = """
SELECT ?club ?clubLabel ?compLabel WHERE {
  ?club wdt:P31/wdt:P279* wd:Q476028 ;
        wdt:P17 wd:Q155 ;
        p:P2522 ?v .
  ?v ps:P2522 ?competition .
  ?competition rdfs:label ?compLabel . FILTER(LANG(?compLabel) = "pt")
  ?club rdfs:label ?clubLabel . FILTER(LANG(?clubLabel) = "pt")
}
LIMIT {limit}
"""

VENUES_QUERY = """
SELECT ?club ?clubLabel ?venueLabel WHERE {
  ?club wdt:P31/wdt:P279* wd:Q476028 ;
        wdt:P17 wd:Q155 ;
        wdt:P115 ?venue .
  ?venue rdfs:label ?venueLabel . FILTER(LANG(?venueLabel) = "pt")
  ?club rdfs:label ?clubLabel . FILTER(LANG(?clubLabel) = "pt")
}
LIMIT {limit}
"""


def _sparql(query: str, timeout: int = 90) -> list[dict]:
    url = SPARQL_ENDPOINT + "?" + urllib.parse.urlencode({"query": query, "format": "json"})
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))
    return data["results"]["bindings"]


def _qid(uri: str) -> str:
    return uri.rsplit("/", 1)[-1]


def extract_careers(limit: int, out: Path) -> int:
    bindings = _sparql(CAREERS_QUERY.replace("{limit}", str(limit)))
    by_club: dict[str, dict] = {}
    for b in bindings:
        if "club" not in b or "clubLabel" not in b or "playerLabel" not in b:
            continue
        club_q = _qid(b["club"]["value"])
        club = b["clubLabel"]["value"].strip().upper()
        player = b["playerLabel"]["value"].strip()
        if not club or not player or player.lower() == club.lower():
            continue
        entry = by_club.setdefault(
            club_q,
            {
                "source_url": f"https://www.wikidata.org/wiki/{club_q}",
                "title": f"Wikidata — elenco/histórico: {club}",
                "domain_score": 0.9,
                "extracted_entities": [],
            },
        )
        entry["extracted_entities"].append(
            {"subject": player, "predicate": "DEFENDEU", "object": club, "confidence": 0.95}
        )
    _write(out, by_club)
    return len(by_club)


def extract_stadiums(limit: int, out: Path) -> int:
    bindings = _sparql(STADIUMS_QUERY.replace("{limit}", str(limit)))
    by_stadium: dict[str, dict] = {}
    for b in bindings:
        if "stadium" not in b or "stadiumLabel" not in b or "cityLabel" not in b:
            continue
        stadium_q = _qid(b["stadium"]["value"])
        stadium = b["stadiumLabel"]["value"].strip().upper()
        city = b["cityLabel"]["value"].strip().upper()
        if not stadium or not city or stadium == city:
            continue
        entry = by_stadium.setdefault(
            stadium_q,
            {
                "source_url": f"https://www.wikidata.org/wiki/{stadium_q}",
                "title": f"Wikidata — localização: {stadium}",
                "domain_score": 0.9,
                "extracted_entities": [],
            },
        )
        entry["extracted_entities"].append(
            {"subject": stadium, "predicate": "LOCALIZADO_EM", "object": city, "confidence": 0.95}
        )
    _write(out, by_stadium)
    return len(by_stadium)


def _write(out: Path, payloads: dict[str, dict]) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for payload in payloads.values():
            if payload["extracted_entities"]:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _post_payload(client: urllib.request.Request, url: str, payload: dict, headers: dict) -> tuple[int, float]:
    request = urllib.request.Request(
        url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), method="POST",
        headers={**headers, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, 0.0
    except urllib.error.HTTPError as exc:
        retry_after = float(exc.headers.get("Retry-After") or 5)
        return exc.code, max(0.0, min(retry_after, 30.0))


def ingest(jsonl: Path, sleep_seconds: float) -> int:
    from dotenv import load_dotenv

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from src.ops.space_env import nexus_api_token, space_base_url

    base = Path(__file__).resolve().parent.parent
    load_dotenv(base / ".env")
    load_dotenv(base / ".env.local")

    base_url = space_base_url()
    token = nexus_api_token()
    hf = os.environ.get("HF_TOKEN", "")
    if not base_url or not token:
        print("MISSING_SPACE_URL_OR_TOKEN", file=sys.stderr)
        return 1
    url = base_url + "/api/ingest"
    headers = {"Authorization": f"Bearer {hf}", "X-Nexus-Token": token}
    sent = failed = 0
    for line in jsonl.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        payload.setdefault("timestamp", int(time.time()))
        for attempt in range(3):
            status, retry_after = _post_payload(None, url, payload, headers)
            if status == 200:
                sent += 1
                break
            if status == 429 and attempt < 2:
                print(f"  429 — respeitando Retry-After ({retry_after:.0f}s)", flush=True)
                time.sleep(retry_after)
                continue
            failed += 1
            print(f"  falha {status} em {payload.get('source_url', '')[:60]}", file=sys.stderr)
            break
        time.sleep(sleep_seconds)
        if sent % 50 == 0 and sent:
            print(f"  enviados: {sent}", flush=True)
    print(f"ingest concluída: enviados={sent} falhas={failed}")
    return 0 if failed == 0 else 1


import os  # noqa: E402 — usado por ingest() após dotenv lazy


def main() -> int:

    parser = argparse.ArgumentParser(description="#056 — bulk Wikidata → Nexus-Alpha")
    sub = parser.add_subparsers(dest="mode", required=True)

    p_careers = sub.add_parser("extract-careers")
    p_careers.add_argument("--limit", type=int, default=2000)
    p_careers.add_argument("--out", default="data/wikidata_careers.jsonl")

    p_stadiums = sub.add_parser("extract-stadiums")
    p_stadiums.add_argument("--limit", type=int, default=1000)
    p_stadiums.add_argument("--out", default="data/wikidata_stadiums.jsonl")

    p_vic = sub.add_parser("extract-victories")
    p_vic.add_argument("--limit", type=int, default=3000)
    p_vic.add_argument("--out", default="data/wikidata_victories.jsonl")

    p_ven = sub.add_parser("extract-venues")
    p_ven.add_argument("--limit", type=int, default=1000)
    p_ven.add_argument("--out", default="data/wikidata_venues.jsonl")

    p_ing = sub.add_parser("ingest")
    p_ing.add_argument("--jsonl", required=True)
    p_ing.add_argument("--sleep", type=float, default=0.6)

    args = parser.parse_args()
    if args.mode == "extract-victories":
        bindings = _sparql(VICTORIES_QUERY.replace("{limit}", str(args.limit)))
        by_club: dict[str, dict] = {}
        for b in bindings:
            if "club" not in b or "clubLabel" not in b or "compLabel" not in b:
                continue
            club_q = _qid(b["club"]["value"])
            club = b["clubLabel"]["value"].strip().upper()
            comp = b["compLabel"]["value"].strip().upper()
            if not club or not comp or club == comp:
                continue
            entry = by_club.setdefault(club_q, {
                "source_url": f"https://www.wikidata.org/wiki/{club_q}",
                "title": f"Wikidata — títulos: {club}",
                "domain_score": 0.9, "extracted_entities": [],
            })
            entry["extracted_entities"].append({"subject": club, "predicate": "VENCEU", "object": comp, "confidence": 0.95})
        _write(Path(args.out), by_club)
        print(f"payloads (itens Wikidata): {len(by_club)} -> {args.out}")
        return 0

    if args.mode == "extract-venues":
        bindings = _sparql(VENUES_QUERY.replace("{limit}", str(args.limit)))
        by_club: dict[str, dict] = {}
        for b in bindings:
            if "club" not in b or "clubLabel" not in b or "venueLabel" not in b:
                continue
            club_q = _qid(b["club"]["value"])
            club = b["clubLabel"]["value"].strip().upper()
            venue = b["venueLabel"]["value"].strip().upper()
            if not club or not venue or club == venue:
                continue
            entry = by_club.setdefault(club_q, {
                "source_url": f"https://www.wikidata.org/wiki/{club_q}",
                "title": f"Wikidata — sede/estádio: {club}",
                "domain_score": 0.9, "extracted_entities": [],
            })
            entry["extracted_entities"].append({"subject": club, "predicate": "POSSUIR", "object": venue, "confidence": 0.95})
        _write(Path(args.out), by_club)
        print(f"payloads (itens Wikidata): {len(by_club)} -> {args.out}")
        return 0

    if args.mode == "extract-careers":
        n = extract_careers(args.limit, Path(args.out))
        print(f"payloads (itens Wikidata): {n} -> {args.out}")
        return 0
    if args.mode == "extract-stadiums":
        n = extract_stadiums(args.limit, Path(args.out))
        print(f"payloads (itens Wikidata): {n} -> {args.out}")
        return 0
    return ingest(Path(args.jsonl), args.sleep)


if __name__ == "__main__":
    sys.exit(main())
