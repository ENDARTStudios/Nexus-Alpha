"""#048.10G - Controlada ``LOCALIZADO_EM`` via OpenStreetMap/Nominatim.

Extrai fatos geograficos de ESTADIOS allowlisted:

    ESTADIO --LOCALIZADO_EM--> CIDADE

Fontes:
* JSON do Nominatim (OSM) - ``application/json`` apenas, host allowlisted;
* narrativa wiki (pt/en) - frases declarativas de localizacao com cidade limpa.

Read-only por design: nao escreve em Neo4j/Qdrant, nao chama /api/ingest.
Atribuicao OSM obrigatoria: ``(c) OpenStreetMap contributors`` (ODbL).
"""
from __future__ import annotations

import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PREDICATE = "LOCALIZADO_EM"
ATTRIBUTION = "(c) OpenStreetMap contributors"
LICENSE = "ODbL"
NOMINATIM_HOST = "nominatim.openstreetmap.org"
NOMINATIM_SEARCH = f"https://{NOMINATIM_HOST}/search"
USER_AGENT = "Nexus-Alpha/1.0 (semantic knowledge extraction; private research project)"
MAX_JSON_BYTES = 2_000_000
TIMEOUT = 20

# Alias estritos -> estadi canônico. Sem aliases genéricos perigosos.
CANONICAL_STADIUMS: dict[str, str] = {
    "ALLIANZ PARQUE": "ALLIANZ PARQUE",
    "MORUMBI": "MORUMBI",
    "PACAEMBU": "PACAEMBU",
    "NEO QUIMICA ARENA": "NEO QUÍMICA ARENA",
}

STADIUM_ALIASES: dict[str, str] = {
    "allianz parque": "ALLIANZ PARQUE",
    "arena allianz": "ALLIANZ PARQUE",
    "allianz arena": "ALLIANZ PARQUE",
    "nubank parque": "ALLIANZ PARQUE",
    "morumbi": "MORUMBI",
    "estadio do morumbi": "MORUMBI",
    "estadio cicero pompeu de toledo": "MORUMBI",
    "pacaembu": "PACAEMBU",
    "estadio do pacaembu": "PACAEMBU",
    "estadio municipal paulo machado de carvalho": "PACAEMBU",
    "neo quimica arena": "NEO QUÍMICA ARENA",
    "arena corinthians": "NEO QUÍMICA ARENA",
    # #048.10L — next batch
    "estadio olimpico nilton santos": "ESTÁDIO OLÍMPICO NILTON SANTOS",
    "nilton santos": "ESTÁDIO OLÍMPICO NILTON SANTOS",
    "nilton santos stadium": "ESTÁDIO OLÍMPICO NILTON SANTOS",
    "maracana": "MARACANÃ",
    "estadio do maracana": "MARACANÃ",
    "beira-rio": "BEIRA-RIO",
    "beira rio": "BEIRA-RIO",
    "jose pinheiro borda": "BEIRA-RIO",
    "mineirao": "MINEIRÃO",
    "governador magalhaes pinto": "MINEIRÃO",
    "arena fonte nova": "ARENA FONTE NOVA",
    "fonte nova": "ARENA FONTE NOVA",
}

# Cidade canônica (com acento) indexada pela forma dobrada (sem acento, maiúscula).
CANONICAL_CITIES: dict[str, str] = {
    "SAO PAULO": "SÃO PAULO",
    "RIO DE JANEIRO": "RIO DE JANEIRO",
    "SANTOS": "SANTOS",
    "PORTO ALEGRE": "PORTO ALEGRE",
    "BELO HORIZONTE": "BELO HORIZONTE",
    "SALVADOR": "SALVADOR",
}

# Nunca podem virar objeto-cidade.
FORBIDDEN_CITY_HINTS = {
    "ENGENHO DE DENTRO",
    "PERDIZES",
    "VILA BELMIRO",
    "BOTAFOGO",
    "POMPEIA",
    "LARANJEIRAS",
    "BARRA FUNDA",
    "SAO PAULO STATE",
    "RIO DE JANEIRO STATE",
}

# Cidade esperada source-scoped por estadi canonico (#048.10H lote atual + #048.10L next batch).
# Fonte: reports/geo_expected_facts_048_10H.json + reports/geo_expected_facts_048_10L.json.
GEO_EXPECTED_CITY_BY_STADIUM: dict[str, str] = {
    "ALLIANZ PARQUE": "SÃO PAULO",
    "MORUMBI": "SÃO PAULO",
    "PACAEMBU": "SÃO PAULO",
    "NEO QUÍMICA ARENA": "SÃO PAULO",
    "ESTÁDIO OLÍMPICO NILTON SANTOS": "RIO DE JANEIRO",
    "MARACANÃ": "RIO DE JANEIRO",
    "BEIRA-RIO": "PORTO ALEGRE",
    "MINEIRÃO": "BELO HORIZONTE",
    "ARENA FONTE NOVA": "SALVADOR",
}

# Nominatim: tipo/class que NUNCA sao venue de estadio (viario/bairro/cidade/endereco).
_NON_VENUE_OSM_CLASSES = {"HIGHWAY", "ROUTE", "BOUNDARY", "PLACE"}
_NON_VENUE_OSM_TYPES = {
    "ROAD", "HIGHWAY", "RESIDENTIAL", "FOOTWAY", "PEDESTRIAN", "NEIGHBOURHOOD", "NEIGHBORHOOD",
    "SUBURB", "CITY", "TOWN", "VILLAGE", "ADMINISTRATIVE", "HOUSE", "HOUSE_NUMBER", "COUNTRY", "STATE",
}


def _fold(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value or "")
    without = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", without).strip().upper()


def _strip_html(value: str) -> str:
    value = re.sub(r"(?is)<(script|style).*?</\1>", " ", value or "")
    text = re.sub(r"(?s)<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", text).strip()


@dataclass(frozen=True)
class GeoAllowlist:
    """Allowlist estrita de estádios e cidades para extração GEO."""

    stadiums: dict[str, str]
    cities: dict[str, str]

    def resolve_stadium(self, text: str) -> str | None:
        folded = _fold(text)
        hits = {canon for alias, canon in self.stadiums.items() if _fold(alias) in folded}
        return next(iter(hits)) if len(hits) == 1 else None

    def city_from(self, raw: str | None) -> str | None:
        folded = _fold(raw or "")
        if not folded or folded in FORBIDDEN_CITY_HINTS:
            return None
        return self.cities.get(folded)


def default_geo_allowlist() -> GeoAllowlist:
    return GeoAllowlist(stadiums=dict(STADIUM_ALIASES), cities=dict(CANONICAL_CITIES))


def _is_non_venue_osm_entry(entry: dict) -> bool:
    """True quando o resultado Nominatim nao e um venue de estadio (viario/bairro/cidade)."""
    cls = _fold(str(entry.get("class") or entry.get("category") or ""))
    typ = _fold(str(entry.get("type") or ""))
    return cls in _NON_VENUE_OSM_CLASSES or typ in _NON_VENUE_OSM_TYPES


def resolve_expected_geo_city(url: str, allowlist: GeoAllowlist | None = None) -> str | None:
    """Cidade esperada source-scoped por fato/URL (registry GEO). Nao usa heuristica textual ampla.

    * URL wiki GEO -> sujeito pinado pela URL -> cidade do registry.
    * URL Nominatim -> ``q`` resolvido contra a allowlist de estadios -> cidade do registry.
    * Qualquer outra -> ``None`` (``expected_city_unresolved``).
    """
    allowlist = allowlist or default_geo_allowlist()
    from src.cognition.geo_wiki_parser import _pin_subject_by_url

    subject = _pin_subject_by_url(url)
    if subject:
        return GEO_EXPECTED_CITY_BY_STADIUM.get(subject)
    if is_geo_nominatim_url(url):
        try:
            query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("q", [""])[0]
        except Exception:
            query = ""
        stadium = allowlist.resolve_stadium(query) if query else None
        if stadium:
            return GEO_EXPECTED_CITY_BY_STADIUM.get(stadium)
    return None


# Excecao estrita homonimo estado/cidade (source-scoped). SAO PAULO (#048.10H) e RIO DE JANEIRO (#048.10L).
HOMONYM_STATE_CITY_ALLOWLIST: dict[str, dict[str, set[str]]] = {
    "SAO PAULO": {"country": {"BRAZIL", "BRASIL"}, "state": {"SAO PAULO"}},
    "RIO DE JANEIRO": {"country": {"BRAZIL", "BRASIL"}, "state": {"RIO DE JANEIRO"}},
}
def build_geo_allowlist_from_atlas(atlas_path: Path | str) -> GeoAllowlist:
    """Allowlist a partir das colisões full do atlas #059E (fallback: default)."""
    path = Path(atlas_path)
    if not path.exists():
        return default_geo_allowlist()
    try:
        atlas = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default_geo_allowlist()

    stadiums: dict[str, str] = {}
    cities: dict[str, str] = {}
    for candidate in atlas.get("candidates") or []:
        if candidate.get("collision_status") != "full_collision":
            continue
        if not candidate.get("eligible_for_runtime"):
            continue
        entity = _fold(candidate.get("entity") or "")
        canon = CANONICAL_STADIUMS.get(entity)
        if canon:
            stadiums[entity.lower()] = canon
        city_folded = _fold(candidate.get("resolved_city") or "")
        city = CANONICAL_CITIES.get(city_folded)
        if city:
            cities[city_folded] = city
    if not stadiums:
        return default_geo_allowlist()
    # Preserva aliases estritos para os estádios canônicos selecionados.
    for alias, canon in STADIUM_ALIASES.items():
        if canon in stadiums.values():
            stadiums.setdefault(alias, canon)
    return GeoAllowlist(stadiums=stadiums, cities=cities or dict(CANONICAL_CITIES))


def _triple(subject: str, obj: str, metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "subject": subject,
        "predicate": PREDICATE,
        "object": obj,
        "confidence": float(metadata.get("confidence", 0.9)),
        "metadata": metadata,
    }


def extract_geo_localizado_from_osm_json(
    payload: dict | list,
    source_url: str,
    allowlist: GeoAllowlist,
    expected_city: str | None = None,
) -> list[dict[str, Any]]:
    """Extrai ``ESTADIO --LOCALIZADO_EM--> CIDADE`` de um payload JSON do Nominatim."""
    entries = payload if isinstance(payload, list) else [payload]
    by_stadium: dict[str, set[str]] = {}
    meta_by_key: dict[tuple[str, str], dict[str, Any]] = {}

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        namedetails = entry.get("namedetails") or {}
        blob = " ".join(
            str(v) for v in (entry.get("name"), namedetails.get("name"), entry.get("display_name")) if v
        )
        stadium = allowlist.resolve_stadium(blob)
        if not stadium or _is_non_venue_osm_entry(entry):
            continue
        address = entry.get("address") or {}
        city = None
        city_key = None
        expected_folded = _fold(expected_city) if expected_city else None
        structured_conflict = False
        for key in ("city", "town", "municipality"):
            found = allowlist.city_from(address.get(key))
            if found:
                if expected_folded and _fold(found) != expected_folded:
                    structured_conflict = True  # cidade estruturada conflita com a esperada -> ambiguo
                    break
                city, city_key = found, f"address.{key}"
                break
        if structured_conflict:
            continue
        if not city and expected_city is None:
            # Sem expected_city (legado): aceita cidade do display_name desde que nao homonima.
            for segment in reversed(str(entry.get("display_name") or "").split(",")):
                found = allowlist.city_from(segment)
                if found and _fold(found) not in HOMONYM_STATE_CITY_ALLOWLIST:
                    city, city_key = found, "display_name"
                    break
        if not city and expected_city and expected_folded not in HOMONYM_STATE_CITY_ALLOWLIST:
            # Fallback source-scoped: so aceita a cidade JA ESPERADA pelo cluster (nunca infere generico)
            # e rejeita se outra cidade allowlisted conflitar no display_name (ambiguidade).
            display = _fold(str(entry.get("display_name") or ""))
            if re.search(rf"\b{re.escape(expected_folded)}\b", display):
                conflicting = {
                    canonical for canonical in CANONICAL_CITIES.values()
                    if _fold(canonical) != expected_folded
                    and re.search(rf"\b{re.escape(_fold(canonical))}\b", display)
                }
                if not conflicting:
                    city, city_key = expected_city, "display_name_expected_context"
        homonym = False
        if not city and expected_city:
            spec = HOMONYM_STATE_CITY_ALLOWLIST.get(_fold(expected_city))
            addr = entry.get("address") or {}
            if (
                spec
                and _fold(str(addr.get("country") or "")) in spec["country"]
                and _fold(str(addr.get("state") or "")) in spec["state"]
                and re.search(rf"\b{re.escape(_fold(expected_city))}\b", _fold(str(entry.get("display_name") or "")))
            ):
                city, city_key = expected_city, "homonym_state_city_exception"
                homonym = True
        if not city:
            continue
        by_stadium.setdefault(stadium, set()).add(city)
        meta_by_key[(stadium, city)] = {
            "source_type": "geo_osm",
            "extraction_method": "nominatim_json",
            "geo_schema": "stadium_city_localization",
            "publisher_family": "OpenStreetMap",
            "license": LICENSE,
            "attribution": ATTRIBUTION,
            "osm_place_id": entry.get("place_id"),
            "osm_type": entry.get("osm_type"),
            "osm_id": entry.get("osm_id"),
            "city_tag_key": city_key,
            "city_source": city_key,
            "confidence": 0.85 if homonym else 0.9,
            "confidence_basis": (
                "homonym_state_city_exception"
                if homonym
                else ("explicit_city_tag" if city_key != "display_name" else "display_address_city")
            ),
            "source_url": source_url,
        }

    triples: list[dict[str, Any]] = []
    for stadium, cities in by_stadium.items():
        if len(cities) != 1:  # ambíguo: resultado múltiplo sem desempate seguro
            continue
        city = next(iter(cities))
        triples.append(_triple(stadium, city, meta_by_key[(stadium, city)]))
    return triples


_WIKI_CITY_PATTERNS = [
    r"cidade (?:do|de|da) ([a-z'`\- ]{3,40})",
    r"municipio de ([a-z'`\- ]{3,40})",
    r"localizado em ([a-z'`\- ]{3,40})",
    r"localizada em ([a-z'`\- ]{3,40})",
    r"situado em ([a-z'`\- ]{3,40})",
    r"fica em ([a-z'`\- ]{3,40})",
    r"located in the city of ([a-z'`\- ]{3,40})",
    r"located in ([a-z'`\- ]{3,40})",
    r"is located in ([a-z'`\- ]{3,40})",
    r"is situated in ([a-z'`\- ]{3,40})",
]


def extract_geo_localizado_from_wiki_html(
    html_or_text: str,
    source_url: str,
    allowlist: GeoAllowlist,
) -> list[dict[str, Any]]:
    """Extrai ``ESTADIO --LOCALIZADO_EM--> CIDADE`` de narrativa wiki (pt/en)."""
    text = _strip_html(html_or_text)
    stadium = allowlist.resolve_stadium(text)
    if not stadium:
        return []
    folded = _fold(text).lower()
    for pattern in _WIKI_CITY_PATTERNS:
        match = re.search(pattern, folded)
        if not match:
            continue
        fragment = re.split(r"[,;().]| by | where | which ", match.group(1))[0]
        city = allowlist.city_from(fragment)
        if city:
            return [
                _triple(
                    stadium,
                    city,
                    {
                        "source_type": "wiki_narrative",
                        "extraction_method": "geo_target_aware_wiki",
                        "geo_schema": "stadium_city_localization",
                        "publisher_family": "Wikimedia",
                        "license": "CC",
                        "attribution": "Wikipédia/Wikimedia",
                        "city_tag_key": None,
                        "confidence_basis": "wiki_location_phrase",
                        "source_url": source_url,
                    },
                )
            ]
    return []


def fetch_nominatim_json(url: str, timeout: int = TIMEOUT, retries: int = 2) -> list:
    """Fetch JSON seguro do Nominatim (host/format allowlisted). Retry conservador de 5xx."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.netloc.lower() != NOMINATIM_HOST:
        raise ValueError(f"host Nominatim não permitido: {parsed.netloc!r}")
    query = urllib.parse.parse_qs(parsed.query)
    if "json" not in (query.get("format", [""])[0] or "").lower():
        raise ValueError("Nominatim exige format=json")

    attempt = 0
    while True:
        attempt += 1
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (host allowlisted)
                content_type = (response.headers.get("Content-Type") or "").lower()
                if "application/json" not in content_type:
                    return []
                raw = response.read(MAX_JSON_BYTES + 1)
            break
        except urllib.error.HTTPError as exc:
            if exc.code in (500, 502, 503, 504) and attempt <= retries:
                time.sleep(5)
                continue
            return []
        except Exception:
            return []
    if len(raw) > MAX_JSON_BYTES:
        return []
    try:
        data = json.loads(raw.decode("utf-8", errors="replace"))
    except Exception:
        return []
    return data if isinstance(data, list) else ([data] if isinstance(data, dict) else [])


def is_geo_nominatim_url(url: str) -> bool:
    """True apenas para ``https://nominatim.openstreetmap.org/search?...format=json``."""
    try:
        parsed = urllib.parse.urlparse(url or "")
    except Exception:
        return False
    if parsed.scheme != "https" or parsed.netloc.lower() != NOMINATIM_HOST:
        return False
    if not parsed.path.startswith("/search"):
        return False
    query = urllib.parse.parse_qs(parsed.query)
    return "json" in (query.get("format", [""])[0] or "").lower()


def fetch_and_extract_geo(
    url: str,
    allowlist: GeoAllowlist | None = None,
    expected_city: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Caminho isolado do worker: fetch JSON + extrai triplas GEO (sem tocar HTML).

    Retorna ``(triples, telemetry)``. Nunca levanta por erro de rede/parse.
    """
    allowlist = allowlist or default_geo_allowlist()
    telemetry: dict[str, Any] = {
        "osm_url": url,
        "osm_json_parsed": 0,
        "geo_triples_raw": 0,
        "rejection_reasons": {},
    }
    if not is_geo_nominatim_url(url):
        telemetry["rejection_reasons"]["not_geo_nominatim_url"] = 1
        return [], telemetry
    try:
        data = fetch_nominatim_json(url)
    except ValueError:
        telemetry["rejection_reasons"]["invalid_url"] = 1
        return [], telemetry
    if not data:
        telemetry["rejection_reasons"]["empty_or_invalid_json"] = 1
        return [], telemetry
    telemetry["osm_json_parsed"] = len(data)
    triples = extract_geo_localizado_from_osm_json(data, url, allowlist, expected_city=expected_city)
    telemetry["geo_triples_raw"] = len(triples)
    if not triples:
        telemetry["rejection_reasons"]["no_clean_city_evidence"] = 1
    return triples, telemetry
