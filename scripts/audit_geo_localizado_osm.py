"""#059E (B2) - Atlas read-only GEO: ESTADIO --LOCALIZADO_EM--> CIDADE via OpenStreetMap.

Read-only: nao escreve em Neo4j/Qdrant, nao usa /api/ingest, nao roda worker.

Fonte OSM: Nominatim (mesma base OSM; Overpass apresentou timeout/instabilidade nesta
janela e foi substituido pelo geocoder oficial OSM, respeitando rate limit >= 1s).
Atribuicao obrigatoria: (c) OpenStreetMap contributors (ODbL).

Uso:
    python scripts/audit_geo_localizado_osm.py
"""
from __future__ import annotations

import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "reports" / "geo_localizado_osm_atlas_059e.json"
RAW_DIR = ROOT / ".autonomous" / "geo"

UA = "NexusAlpha-059E-audit/1.0 (read-only; +https://github.com/ENDARTStudios/Nexus-Alpha)"
TIMEOUT = 25
NOMINATIM_SEARCH = "https://nominatim.openstreetmap.org/search"
ATTRIBUTION = "(c) OpenStreetMap contributors"
LICENSE = "ODbL"

ALLOWED_CITIES = ["RIO DE JANEIRO", "SANTOS", "SAO PAULO", "PORTO ALEGRE", "BELO HORIZONTE"]

STADIUMS = [
    {"entity": "ESTADIO OLIMPICO NILTON SANTOS", "query": "Estadio Olimpico Nilton Santos"},
    {"entity": "ESTADIO URBANO CALDEIRA", "query": "Estadio Urbano Caldeira"},
    {"entity": "MARACANA", "query": "Estadio do Maracana"},
    {"entity": "ALLIANZ PARQUE", "query": "Allianz Parque"},
    {"entity": "MINEIRAO", "query": "Estadio Mineirao"},
    {"entity": "BEIRA-RIO", "query": "Estadio Beira-Rio"},
    {"entity": "MORUMBI", "query": "Estadio do Morumbi"},
    {"entity": "PACAEMBU", "query": "Estadio do Pacaembu"},
    {"entity": "NEO QUIMICA ARENA", "query": "Neo Quimica Arena"},
    {"entity": "SAO JANUARIO", "query": "Estadio Sao Januario"},
]

WIKI_PAGES = {
    "ESTADIO OLIMPICO NILTON SANTOS": {
        "pt": "https://pt.wikipedia.org/wiki/Est%C3%A1dio_Ol%C3%ADmpico_Nilton_Santos",
        "en": "https://en.wikipedia.org/wiki/Nilton_Santos_Olympic_Stadium",
    },
    "ESTADIO URBANO CALDEIRA": {
        "pt": "https://pt.wikipedia.org/wiki/Est%C3%A1dio_Urbano_Caldeira",
        "en": "https://en.wikipedia.org/wiki/Est%C3%A1dio_Urbano_Caldeira",
    },
    "MARACANA": {
        "pt": "https://pt.wikipedia.org/wiki/Est%C3%A1dio_do_Maracan%C3%A3",
        "en": "https://en.wikipedia.org/wiki/Maracan%C3%A3_Stadium",
    },
    "ALLIANZ PARQUE": {
        "pt": "https://pt.wikipedia.org/wiki/Allianz_Parque",
        "en": "https://en.wikipedia.org/wiki/Allianz_Parque",
    },
    "MINEIRAO": {
        "pt": "https://pt.wikipedia.org/wiki/Est%C3%A1dio_Governador_Magalh%C3%A3es_Pinto",
        "en": "https://en.wikipedia.org/wiki/Mineir%C3%A3o",
    },
    "BEIRA-RIO": {
        "pt": "https://pt.wikipedia.org/wiki/Est%C3%A1dio_Beira-Rio",
        "en": "https://en.wikipedia.org/wiki/Est%C3%A1dio_Beira-Rio",
    },
    "MORUMBI": {
        "pt": "https://pt.wikipedia.org/wiki/Est%C3%A1dio_do_Morumbi",
        "en": "https://en.wikipedia.org/wiki/Morumbi_Stadium",
    },
    "PACAEMBU": {
        "pt": "https://pt.wikipedia.org/wiki/Est%C3%A1dio_do_Pacaembu",
        "en": "https://en.wikipedia.org/wiki/Pacaembu_Stadium",
    },
    "NEO QUIMICA ARENA": {
        "pt": "https://pt.wikipedia.org/wiki/Neo_Qu%C3%ADmica_Arena",
        "en": "https://en.wikipedia.org/wiki/Neo_Qu%C3%ADmica_Arena",
    },
    "SAO JANUARIO": {
        "pt": "https://pt.wikipedia.org/wiki/Est%C3%A1dio_S%C3%A3o_Janu%C3%A1rio",
        "en": "https://en.wikipedia.org/wiki/Est%C3%A1dio_S%C3%A3o_Janu%C3%A1rio",
    },
}

FORBIDDEN_CITY_HINTS = {
    "ENGENHO DE DENTRO",
    "VILA BELMIRO",
    "POMPEIA",
    "PERDIZES",
    "BOTAFOGO",
    "RIO GRANDE DO SUL",
    "SAO PAULO (STATE)",
    "RIO DE JANEIRO (STATE)",
}


def strip_accents(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", value) if unicodedata.category(c) != "Mn")


def norm(value: str) -> str:
    return strip_accents(value or "").strip().upper()


def match_city(value: str | None) -> str | None:
    """Retorna a cidade allowlisted canonica se `value` casar; senão None (rejeita bairro/estado)."""
    if not value:
        return None
    folded = norm(value)
    if folded in FORBIDDEN_CITY_HINTS:
        return None
    for city in ALLOWED_CITIES:
        if re.search(rf"(^|\b){re.escape(city)}(\b|$)", folded):
            return city
    return None


def nominatim_city(address: dict | None) -> str | None:
    """Cidade allowlisted a partir do bloco `address` do Nominatim (addr:city > town > municipality)."""
    if not isinstance(address, dict):
        return None
    for key in ("city", "town", "municipality"):
        city = match_city(address.get(key))
        if city:
            return city
    return None


def wiki_city(text: str) -> str | None:
    """Extrai cidade allowlisted de frases de localizacao (PT/EN); rejeita bairro/clausula."""
    if not text:
        return None
    folded = strip_accents(text)
    patterns = [
        r"cidade\s+(?:do|de|da)\s+([A-Za-z'`\-\s]{3,40})",
        r"munic[ií]pio\s+de\s+([A-Za-z'`\-\s]{3,40})",
        r"(?:localizado|situado|localizada|situada|fica)\s+(?:em|na cidade de|no municipio de)\s+([A-Za-z'`\-\s]{3,40})",
        r"city of\s+([A-Za-z'`\-\s]{3,40})",
        r"(?:is located in|is situated in|located in the city of|is in)\s+([A-Za-z'`\-\s]{3,40})",
    ]
    for pat in patterns:
        for m in re.finditer(pat, folded, re.IGNORECASE):
            fragment = re.split(r"[,;().]| by | where | which ", m.group(1))[0]
            city = match_city(fragment)
            if city:
                return city
    return None


def http_get(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:  # noqa: S310 (fixed allowlist hosts)
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, ""
    except Exception:
        return 0, ""


def osm_search(query: str) -> dict | None:
    url = NOMINATIM_SEARCH + "?" + urllib.parse.urlencode(
        {"q": query, "format": "jsonv2", "addressdetails": "1", "limit": "1"}
    )
    code, body = http_get(url)
    if code != 200 or not body:
        return None
    try:
        arr = json.loads(body)
    except Exception:
        return None
    return arr[0] if arr else None


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    generated = datetime.now(timezone.utc).isoformat()

    candidates = []
    summary = {
        "stadiums_evaluated": 0,
        "osm_features_found": 0,
        "osm_city_evidence_found": 0,
        "geo_full_collision_facts": 0,
        "geo_partial_collision_facts": 0,
        "predicted_new_verified": 0,
        "eligible_for_runtime": False,
        "recommended_next_step": "",
    }

    for stadium in STADIUMS:
        entity = stadium["entity"]
        summary["stadiums_evaluated"] += 1

        feature = osm_search(stadium["query"])
        osm_features = []
        osm_city = None
        if feature:
            summary["osm_features_found"] += 1
            addr = feature.get("address", {}) or {}
            osm_city = nominatim_city(addr)
            if osm_city:
                summary["osm_city_evidence_found"] += 1
            osm_features.append(
                {
                    "osm_type": feature.get("osm_type"),
                    "osm_id": feature.get("osm_id"),
                    "display_name": (feature.get("display_name") or "")[:120],
                    "address": addr,
                    "resolved_city": osm_city,
                    "eligible": bool(osm_city),
                    "blocking_reason": None if osm_city else "no_clean_city_evidence",
                    "attribution": ATTRIBUTION,
                    "license": LICENSE,
                }
            )
            slug = re.sub(r"[^a-z0-9]+", "_", norm(stadium["query"]).lower()).strip("_")
            (RAW_DIR / f"osm_{slug}.json").write_text(
                json.dumps(feature, ensure_ascii=False), encoding="utf-8"
            )
        time.sleep(2)

        wiki_sources = []
        wiki_city_map = {}
        for lang, url in WIKI_PAGES.get(entity, {}).items():
            code, text = http_get(url)
            city = wiki_city(text) if code == 200 else None
            wiki_city_map[lang] = city
            wiki_sources.append({"lang": lang, "url": url, "http_status": code, "city": city})
            time.sleep(2)

        domains = set()
        if osm_city:
            domains.add("openstreetmap.org")
        if wiki_city_map.get("pt"):
            domains.add("pt.wikipedia.org")
        if wiki_city_map.get("en"):
            domains.add("en.wikipedia.org")

        same_city = None
        if osm_city and (wiki_city_map.get("pt") == osm_city or wiki_city_map.get("en") == osm_city):
            same_city = osm_city

        collision = "no_collision"
        eligible = False
        blocking = None
        if same_city and len(domains) >= 3:
            collision = "full_collision"
            eligible = True
            summary["geo_full_collision_facts"] += 1
        elif same_city and len(domains) == 2:
            collision = "partial_collision"
            blocking = "needs_third_domain"
            summary["geo_partial_collision_facts"] += 1
        elif osm_city:
            collision = "partial_collision"
            blocking = "osm_only_no_wiki_collision"
            summary["geo_partial_collision_facts"] += 1
        else:
            blocking = "no_city_evidence"

        families = []
        if osm_city:
            families.append("OpenStreetMap")
        if wiki_city_map.get("pt") or wiki_city_map.get("en"):
            families.append("Wikimedia")

        candidates.append(
            {
                "entity": entity,
                "osm_query": stadium["query"],
                "osm_features": osm_features,
                "wiki_sources": wiki_sources,
                "resolved_city": same_city or osm_city,
                "predicted_domains": sorted(domains),
                "predicted_domain_count": len(domains),
                "predicted_publishers": sorted(domains),
                "predicted_publisher_families": families,
                "predicted_effective_publisher_count": len(families),
                "collision_status": collision,
                "eligible_for_runtime": eligible,
                "blocking_reason": blocking,
            }
        )

    summary["eligible_for_runtime"] = summary["geo_full_collision_facts"] >= 3
    summary["predicted_new_verified"] = summary["geo_full_collision_facts"]
    if summary["geo_full_collision_facts"] >= 3:
        summary["recommended_next_step"] = (
            "#048.10F runtime condicional para LOCALIZADO_EM via OSM (somente apos Space no HEAD)."
        )
    else:
        summary["recommended_next_step"] = "Ampliar evidencia geo (mais estadios/cidades) antes do runtime."

    atlas = {
        "audit_id": "geo_localizado_osm_atlas_059e",
        "generated_at": generated,
        "policy": {
            "allowed_stadiums": [s["entity"] for s in STADIUMS],
            "allowed_cities": ALLOWED_CITIES,
            "osm_endpoints": [NOMINATIM_SEARCH],
            "attribution": ATTRIBUTION,
            "license": LICENSE,
            "forbidden_objects": ["NEIGHBORHOOD", "ADDRESS", "COUNTRY", "COORDINATE", "STATE_AS_CITY"],
        },
        "candidates": candidates,
        "summary": summary,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(atlas, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("WROTE", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
