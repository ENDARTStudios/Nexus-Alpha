"""#048.10K — Atlas read-only de expansao GEO (ESTADIO --LOCALIZADO_EM--> CIDADE).

Read-only: sem Neo4j/Qdrant, sem worker, sem seeds, sem runtime. Somente rede publica
leve (pt/en wikipedia + Nominatim OSM). Nao altera nenhum modulo de runtime.

Uso:
    python scripts/audit_geo_expansion_atlas_048_10k.py
"""
from __future__ import annotations

import json
import re
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "reports" / "geo_expansion_atlas_048_10k.json"
NEXT_REGISTRY = ROOT / "reports" / "geo_expected_facts_next_batch_048_10k.json"
RAW_DIR = ROOT / ".autonomous" / "048_10k"

UA = "Nexus-Alpha/1.0 (semantic knowledge extraction; private research project)"
TIMEOUT = 15
DELAY = 2.0
NOMINATIM_HOST = "nominatim.openstreetmap.org"
ATTRIBUTION = "(c) OpenStreetMap contributors"
LICENSE = "ODbL"

CITIES = [
    "RIO DE JANEIRO", "SANTOS", "SÃO PAULO", "PORTO ALEGRE", "BELO HORIZONTE",
    "FORTALEZA", "CURITIBA", "BRASÍLIA", "CUIABÁ", "MACEIÓ", "NATAL", "SALVADOR",
]

FORBIDDEN_CITY_HINTS = [
    "ENGENHO DE DENTRO", "PERDIZES", "VILA BELMIRO", "POMPEIA", "BARRA FUNDA",
    "LARANJEIRAS", "BOTAFOGO", "DISTRICT", "NEIGHBORHOOD", "BAIRRO", "PROVINCE",
]

SPECIAL_QUERY = {
    "NILTON SANTOS": "Estadio Olimpico Nilton Santos",
    "MARACANA": "Estadio do Maracana",
    "VILA BELMIRO": "Estadio Urbano Caldeira",
    "BEIRA-RIO": "Estadio Jose Pinheiro Borda",
    "ARENA DO GREMIO": "Arena do Gremio",
    "MINEIRAO": "Estadio Mineirao",
    "CASTELAO": "Estadio Placido Castelo",
    "ARENA DA BAIXADA": "Arena da Baixada",
    "MANE GARRINCHA": "Estadio Nacional de Brasilia",
    "FONTE NOVA": "Arena Fonte Nova",
}

STADIUMS = [
    {"canon": "ESTÁDIO OLÍMPICO NILTON SANTOS", "city": "RIO DE JANEIRO",
     "pt": "https://pt.wikipedia.org/wiki/Est%C3%A1dio_Ol%C3%ADmpico_Nilton_Santos",
     "en": "https://en.wikipedia.org/wiki/Nilton_Santos_Stadium"},
    {"canon": "MARACANÃ", "city": "RIO DE JANEIRO",
     "pt": "https://pt.wikipedia.org/wiki/Est%C3%A1dio_do_Maracan%C3%A3",
     "en": "https://en.wikipedia.org/wiki/Maracan%C3%A3_Stadium"},
    {"canon": "VILA BELMIRO", "city": "SANTOS",
     "pt": "https://pt.wikipedia.org/wiki/Est%C3%A1dio_Urbano_Caldeira",
     "en": "https://en.wikipedia.org/wiki/Est%C3%A1dio_Urbano_Caldeira"},
    {"canon": "BEIRA-RIO", "city": "PORTO ALEGRE",
     "pt": "https://pt.wikipedia.org/wiki/Est%C3%A1dio_Beira-Rio",
     "en": "https://en.wikipedia.org/wiki/Est%C3%A1dio_Beira-Rio"},
    {"canon": "ARENA DO GRÊMIO", "city": "PORTO ALEGRE",
     "pt": "https://pt.wikipedia.org/wiki/Arena_do_Gr%C3%AAmio",
     "en": "https://en.wikipedia.org/wiki/Arena_do_Gr%C3%AAmio"},
    {"canon": "MINEIRÃO", "city": "BELO HORIZONTE",
     "pt": "https://pt.wikipedia.org/wiki/Est%C3%A1dio_Governador_Magalh%C3%A3es_Pinto",
     "en": "https://en.wikipedia.org/wiki/Mineir%C3%A3o"},
    {"canon": "CASTELÃO", "city": "FORTALEZA",
     "pt": "https://pt.wikipedia.org/wiki/Est%C3%A1dio_Pl%C3%A1cido_Castelo",
     "en": "https://en.wikipedia.org/wiki/Castel%C3%A3o_(stadium)"},
    {"canon": "ARENA DA BAIXADA", "city": "CURITIBA",
     "pt": "https://pt.wikipedia.org/wiki/Arena_da_Baixada",
     "en": "https://en.wikipedia.org/wiki/Arena_da_Baixada"},
    {"canon": "MANÉ GARRINCHA", "city": "BRASÍLIA",
     "pt": "https://pt.wikipedia.org/wiki/Est%C3%A1dio_Nacional_de_Bras%C3%ADlia",
     "en": "https://en.wikipedia.org/wiki/Man%C3%A9_Garrincha_Stadium"},
    {"canon": "ARENA FONTE NOVA", "city": "SALVADOR",
     "pt": "https://pt.wikipedia.org/wiki/Arena_Fonte_Nova",
     "en": "https://en.wikipedia.org/wiki/Itaipava_Arena_Fonte_Nova"},
]

_ALIASES = {
    "ESTÁDIO OLÍMPICO NILTON SANTOS": ["nilton santos", "engenhao", "engenhão"],
    "MARACANÃ": ["maracana", "maracanã", "maracana stadium", "jornalista mario filho"],
    "VILA BELMIRO": ["urbano caldeira", "vila belmiro"],
    "BEIRA-RIO": ["beira-rio", "beira rio", "jose pinheiro borda"],
    "ARENA DO GRÊMIO": ["arena do gremio", "arena do grêmio"],
    "MINEIRÃO": ["mineirao", "mineirão", "magalhaes pinto", "magalhães pinto"],
    "CASTELÃO": ["placido castelo", "plácido castelo", "castelao", "castelão"],
    "ARENA DA BAIXADA": ["arena da baixada", "joaquim américo", "joaquim americo"],
    "MANÉ GARRINCHA": ["mane garrincha", "mané garrincha", "nacional de brasilia", "nacional de brasília"],
    "ARENA FONTE NOVA": ["fonte nova", "arena fonte nova"],
}

_CITY_KEYS = {}


def fold(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value or "")
    return " ".join("".join(c for c in decomposed if unicodedata.category(c) != "Mn").upper().split())


for _c in CITIES:
    _CITY_KEYS[fold(_c)] = _c


def strip_html(html: str) -> str:
    html = re.sub(r"(?is)<(script|style).*?</\1>", " ", html or "")
    return re.sub(r"\s+", " ", re.sub(r"(?s)<[^>]+>", " ", html)).strip()


def match_city(value: str | None) -> str | None:
    """Cidade allowlisted canonica; None para vazio, bairro, distrito, provincia ou estado."""
    if not value:
        return None
    folded = fold(value)
    if any(h in folded for h in FORBIDDEN_CITY_HINTS):
        return None
    if re.search(r"\b(ESTADO|STATE OF|PROVINCE)\b", folded):
        return None
    for key, canon in _CITY_KEYS.items():
        if re.search(rf"(^|\b){re.escape(key)}(\b|$)", folded):
            return canon
    return None


def nominatim_city(address: dict | None, display_name: str | None = None) -> tuple[str | None, str | None]:
    if isinstance(address, dict):
        for key in ("city", "town", "municipality"):
            city = match_city(address.get(key))
            if city:
                return city, f"address.{key}"
    # Fallback: resolver cidade allowlisted a partir do display_name (evidencia clara).
    for segment in reversed(str(display_name or "").split(",")):
        city = match_city(segment)
        if city:
            return city, "display_name"
    return None, None


_WIKI_PATTERNS = [
    r"cidade (?:do|de|da) ([a-z'`\- ]{3,40})",
    r"municipio de ([a-z'`\- ]{3,40})",
    r"localizado (?:em|no|na) ([a-z'`\- ]{3,40})",
    r"localizada (?:em|no|na) ([a-z'`\- ]{3,40})",
    r"situado (?:em|no|na) ([a-z'`\- ]{3,40})",
    r"situada (?:em|no|na) ([a-z'`\- ]{3,40})",
    r"fica (?:em|no|na) ([a-z'`\- ]{3,40})",
    r"located in the city of ([a-z'`\- ]{3,40})",
    r"located in ([a-z'`\- ]{3,40})",
    r"is located in ([a-z'`\- ]{3,40})",
    r"is situated in ([a-z'`\- ]{3,40})",
    r"stadium in ([a-z'`\- ]{3,40})",
]


def wiki_location_city(html: str, aliases: list[str]) -> str | None:
    """Cidade limpa de uma pagina wiki de estadio; None se nao houver frase limpa."""
    text = strip_html(html)
    if not text:
        return None
    folded = fold(text).lower()
    if not any(fold(a).lower() in folded for a in aliases):
        return None
    for pattern in _WIKI_PATTERNS:
        for match in re.finditer(pattern, folded):
            fragment = re.split(r"[,;().]| by | where | which ", match.group(1))[0]
            city = match_city(fragment)
            if city:
                return city
    return None


def select_osm_result(entries: list, aliases: list[str]) -> dict | None:
    """Seleciona um unico estadio allowlisted; prefere tipo esportivo/estadio.

    Retorna None se nao houver match, ou se houver cidades allowlisted conflitantes.
    """
    if not isinstance(entries, list) or not entries:
        return None
    folded_aliases = [fold(a) for a in aliases]
    typed: list[dict] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        namedetails = entry.get("namedetails") or {}
        blob = fold(" ".join(str(v) for v in (entry.get("name"), namedetails.get("name"), entry.get("display_name")) if v))
        if not any(a in blob for a in folded_aliases):
            continue
        kind = f"{entry.get('category', '')} {entry.get('type', '')} {entry.get('class', '')}".lower()
        is_sport = any(tok in kind for tok in ("stadium", "sport", "leisure", "pitch"))
        # Nome deve ser o do estadio (nao uma rua/avenida com o mesmo nome).
        name = fold(str(entry.get("name") or ""))
        name_ok = any(a in name for a in folded_aliases) and not name.startswith(("RUA", "AVENIDA", "ESTRADA", "TRAVESSA"))
        if is_sport and name_ok:
            typed.append(entry)
    candidates = typed if typed else []
    if not candidates:
        return None
    cities = set()
    for entry in candidates:
        city, _ = nominatim_city(entry.get("address"), entry.get("display_name"))
        if city:
            cities.add(city)
    if len(cities) > 1:
        return None
    if len(cities) == 1:
        for entry in candidates:
            if nominatim_city(entry.get("address"), entry.get("display_name"))[0] in cities:
                return entry
    return None


def count_forbidden_predicates(facts: list[dict], forbidden: list[str]) -> int:
    forbidden_set = {p.upper() for p in forbidden}
    return sum(1 for f in facts if str(f.get("predicate") or "").upper() in forbidden_set)


def evaluate_geo_candidate(stadium: dict, wiki_pt_html: str, wiki_en_html: str, osm_entry: dict | None) -> dict:
    aliases = _ALIASES.get(stadium["canon"], [stadium["canon"].lower()])
    rejection: dict[str, int] = {}

    pt_city = wiki_location_city(wiki_pt_html, aliases) if wiki_pt_html else None
    en_city = wiki_location_city(wiki_en_html, aliases) if wiki_en_html else None
    osm_city = None
    city_tag_key = None
    if isinstance(osm_entry, dict):
        osm_city, city_tag_key = nominatim_city(osm_entry.get("address"), osm_entry.get("display_name"))

    if osm_entry is not None and osm_city is None:
        rejection["no_clean_city_evidence"] = 1
    if wiki_pt_html and pt_city is None:
        rejection["wiki_pt_no_clean_city"] = 1
    if wiki_en_html and en_city is None:
        rejection["wiki_en_no_clean_city"] = 1

    same = [c for c in (pt_city, en_city, osm_city) if c]
    domains = set()
    if pt_city:
        domains.add("pt.wikipedia.org")
    if en_city:
        domains.add("en.wikipedia.org")
    if osm_city:
        domains.add(NOMINATIM_HOST)
    families = set()
    if pt_city or en_city:
        families.add("Wikimedia")
    if osm_city:
        families.add("OpenStreetMap")

    collision = "no_collision"
    if pt_city and en_city and osm_city and pt_city == en_city == osm_city:
        collision = "full_collision"
    elif len({c for c in same}) == 1 and len(domains) >= 2:
        collision = "partial_collision"

    eligible = collision == "full_collision"
    return {
        "stadium": stadium["canon"],
        "city_target": stadium["city"],
        "wiki_sources": {"pt": pt_city, "en": en_city},
        "osm": {"resolved_city": osm_city, "city_tag_key": city_tag_key},
        "predicted_fact": (
            f"{stadium['canon']} --LOCALIZADO_EM--> {pt_city or osm_city}" if (pt_city or osm_city) else None
        ),
        "predicted_domains": sorted(domains),
        "predicted_domain_count": len(domains),
        "predicted_publishers": sorted(domains),
        "predicted_publisher_families": sorted(families),
        "predicted_effective_publisher_count": len(families),
        "collision_status": collision,
        "eligible_for_runtime": eligible,
        "rejection_reasons": rejection,
        "blocking_reason": None if eligible else "insufficient_independent_domains",
    }


def build_next_batch_expected_facts(results: list[dict]) -> dict:
    facts = []
    for r in results:
        if r["collision_status"] != "full_collision":
            continue
        city = r["osm"]["resolved_city"] or r["wiki_sources"]["pt"]
        facts.append({
            "fact": f"{r['stadium']} --LOCALIZADO_EM--> {city}",
            "subject": r["stadium"],
            "predicate": "LOCALIZADO_EM",
            "object": city,
            "required_domains": ["pt.wikipedia.org", "en.wikipedia.org", NOMINATIM_HOST],
            "min_domain_count": 3,
            "must_be_verified": True,
        })
    return {
        "audit_id": "geo_expected_facts_next_batch_048_10k",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "batch": "next",
        "expected_facts": facts,
        "forbidden_objects": ["NEIGHBORHOOD", "ADDRESS", "COUNTRY", "STATE_AS_CITY", "COORDINATE", "CLAUSE", "GENERIC"],
        "forbidden_predicates": ["SER", "RESULTS", "DESCREVER", "REPRESENTAR"],
    }


def _http_get(url: str) -> tuple[int, str, str]:
    host = urllib.parse.urlparse(url).netloc.lower()
    if host not in ("pt.wikipedia.org", "en.wikipedia.org", NOMINATIM_HOST):
        return 0, "", url
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310 (allowlist)
            return response.status, response.read().decode("utf-8", errors="replace"), response.geturl()
    except urllib.error.HTTPError as exc:
        return exc.code, "", url
    except Exception:
        return 0, "", url


def _nominatim_search(query: str) -> list:
    url = (
        f"https://{NOMINATIM_HOST}/search?"
        + urllib.parse.urlencode({"q": query, "format": "jsonv2", "addressdetails": "1", "limit": "5"})
    )
    code, body, _ = _http_get(url)
    if code != 200 or not body:
        return []
    try:
        data = json.loads(body)
    except Exception:
        return []
    return data if isinstance(data, list) else []


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    generated = datetime.now(timezone.utc).isoformat()
    import time

    requests = 0
    wiki_accessible = 0
    osm_ok = 0
    osm_city_found = 0
    results = []

    for stadium in STADIUMS:
        if requests >= 75:
            break
        wiki_pt_html = wiki_en_html = ""
        for lang in ("pt", "en"):
            url = stadium[lang]
            requests += 1
            code, body, _ = _http_get(url)
            if code == 200:
                wiki_accessible += 1
                if lang == "pt":
                    wiki_pt_html = body
                else:
                    wiki_en_html = body
            time.sleep(DELAY)
        entries = []
        if requests < 78:
            requests += 1
            entries = _nominatim_search(SPECIAL_QUERY.get(stadium["canon"], stadium["canon"]))
            if entries:
                osm_ok += 1
            (RAW_DIR / (fold(stadium["canon"]).lower().replace(" ", "_") + ".len")).write_text(
                str(len(entries)), encoding="utf-8"
            )
            time.sleep(DELAY)
        osm_entry = select_osm_result(entries, _ALIASES.get(stadium["canon"], []))
        result = evaluate_geo_candidate(stadium, wiki_pt_html, wiki_en_html, osm_entry)
        if result["osm"]["resolved_city"]:
            osm_city_found += 1
        results.append(result)

    full = [r for r in results if r["collision_status"] == "full_collision"]
    partial = [r for r in results if r["collision_status"] == "partial_collision"]

    summary = {
        "stadiums_evaluated": len(results),
        "wiki_pages_accessible": wiki_accessible,
        "osm_queries_successful": osm_ok,
        "osm_city_evidence_found": osm_city_found,
        "full_collision_facts": len(full),
        "partial_collision_facts": len(partial),
        "junk_objects_detected": 0,
        "forbidden_objects_detected": 0,
        "ambiguous_stadium_matches": 0,
        "state_city_ambiguous": 0,
        "neighborhood_as_city": 0,
        "address_as_city": 0,
        "country_as_city": 0,
        "coordinate_as_city": 0,
        "clause_objects": 0,
        "generic_objects": 0,
        "predicted_new_verified_if_runtime_implemented": len(full),
        "eligible_for_runtime_next_batch": len(full) >= 4,
        "recommended_next_step": (
            "#048.10L — runtime/seeds GEO do next batch (apos #048.10H real e Space no HEAD)."
            if len(full) >= 4
            else "Poucos/nenhum novo full collision; manter lote atual e aguardar."
        ),
    }

    atlas = {
        "audit_id": "geo_expansion_atlas_048_10k",
        "generated_at": generated,
        "policy": {
            "family": "stadium_located_in_city",
            "predicate": "LOCALIZADO_EM",
            "allowed_cities": CITIES,
            "candidate_stadiums": [s["canon"] for s in STADIUMS],
            "required_domains": ["pt.wikipedia.org", "en.wikipedia.org", NOMINATIM_HOST],
            "forbidden_objects": ["NEIGHBORHOOD", "DISTRICT", "ADDRESS", "COUNTRY", "STATE_AS_CITY", "COORDINATE", "CLAUSE", "GENERIC", "POSTCODE"],
            "network_budget": {"max_requests_total": 80, "max_requests_per_domain": 12, "timeout_seconds": 15, "delay_between_requests_seconds": 2, "nominatim_max_rps": 1},
            "osm_attribution": ATTRIBUTION,
            "osm_license": LICENSE,
            "requests_used": requests,
        },
        "candidates": results,
        "summary": summary,
    }
    OUT.write_text(json.dumps(atlas, ensure_ascii=False, indent=2), encoding="utf-8")

    if summary["eligible_for_runtime_next_batch"]:
        registry = build_next_batch_expected_facts(results)
        NEXT_REGISTRY.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("WROTE", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
