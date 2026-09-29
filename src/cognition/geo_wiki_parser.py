"""#048.10H.2.1 — Parser wiki GEO dedicado (subject pinado por URL, cidade na mesma frase/infobox).

Estrito, deterministico e allowlisted. NAO faz rede, NAO usa LLM, NAO escreve em grafo.
So emite ``ESTADIO --LOCALIZADO_EM--> CIDADE`` para URLs de estadios whitelisted,
com a cidade allowlisted do lote atual.

Motivo: a extracao narrativa generica produz ruido (ex.: ``SAO PAULO FUTEBOL CLUBE
--LOCALIZADO_EM--> ESTADIO DO MORUMBI``) e nao a chave canonica esperada.
"""
from __future__ import annotations

import re
import unicodedata
from urllib.parse import unquote, urlparse

PREDICATE = "LOCALIZADO_EM"

# Lote atual #048.10H: todos em SAO PAULO.
ALLOWED_CITIES = {"SAO PAULO": "SÃO PAULO"}

# URL (match por token no path) -> sujeito canonico esperado.
_URL_SUBJECT_TOKENS = (
    ("allianz_parque", "ALLIANZ PARQUE"),
    ("allianz_parque", "ALLIANZ PARQUE"),
    ("estadio_do_morumbi", "MORUMBI"),
    ("morumbi_stadium", "MORUMBI"),
    ("estadio_do_pacaembu", "PACAEMBU"),
    ("pacaembu_stadium", "PACAEMBU"),
    ("neo_quimica_arena", "NEO QUÍMICA ARENA"),
)

FORBIDDEN_TOKENS = (
    "bairro", "neighborhood", "district", "suburb", "borough", "estado", "state of",
    "country", "brasil", "brazil", "rua", "avenida", "avenue", "street", "postcode",
    "coordenada", "coordinate", "owner", "tenant", "clube", "futebol clube",
    "palmeiras", "corinthians", "santos futebol",
)

_CITY_ALIASES = {
    "sao paulo": "SAO PAULO",
    "são paulo": "SAO PAULO",
}

CUE_PATTERNS = [
    r"localizado\s+(?:em|na cidade de|no municipio de)",
    r"localizada\s+(?:em|na cidade de|no municipio de)",
    r"situado\s+(?:em|na cidade de)",
    r"situada\s+(?:em|na cidade de)",
    r"localiza-se\s+em",
    r"fica\s+em",
    r"é um estádio[^.]{0,40}localizado em",
    r"located in",
    r"situated in",
    r"stadium in",
]


def _fold(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value or "")
    return " ".join("".join(c for c in decomposed if unicodedata.category(c) != "Mn").upper().split())


def normalize_url(url: str) -> str:
    try:
        parsed = urlparse(url or "")
    except Exception:
        return ""
    return _fold(unquote(parsed.path)).lower().strip("/")


def _is_geo_wiki_url(url: str) -> bool:
    host = urlparse(url or "").netloc.lower()
    if host not in ("pt.wikipedia.org", "en.wikipedia.org"):
        return False
    path = normalize_url(url)
    return any(token in path for token, _ in _URL_SUBJECT_TOKENS)


# API publica (mantem o alias privado para testes internos).
is_geo_wiki_url = _is_geo_wiki_url


def _pin_subject_by_url(url: str) -> str | None:
    path = normalize_url(url)
    for token, subject in _URL_SUBJECT_TOKENS:
        if token in path:
            return subject
    return None


def _is_forbidden_location_object(value: str) -> bool:
    folded = _fold(value).lower()
    return any(tok in folded for tok in FORBIDDEN_TOKENS)


def _extract_city_from_sentence(sentence: str) -> str | None:
    """Cidade allowlisted se a frase tiver cue de localizacao e nao for bairro/pais/estado/clube/endereco."""
    folded = _fold(sentence).lower()
    if not any(re.search(p, folded) for p in CUE_PATTERNS):
        return None
    found = {canon for alias, canon in _CITY_ALIASES.items() if re.search(rf"\b{re.escape(alias)}\b", folded)}
    if len(found) != 1:
        return None  # nenhuma ou multiplas cidades -> ambiguo
    city = next(iter(found))

    # Rejeicoes por token em qualquer lugar da frase.
    for tok in ("bairro", "neighborhood", "district", "suburb", "borough", "owner", "tenant", "clube", "futebol clube"):
        if re.search(rf"\b{re.escape(tok)}\b", folded):
            return None
    for tok in ("rua", "avenida", "avenue", "street", "postcode", "coordenada", "coordinate"):
        if re.search(rf"\b{re.escape(tok)}\b", folded):
            return None

    # Cidade usada como ESTADO (ex.: "São Paulo state" / "São Paulo, estado de São Paulo") -> rejeitar.
    idx = folded.find(_fold(city).lower())
    if idx >= 0:
        tail = folded[idx + len(_fold(city)): idx + len(_fold(city)) + 14]
        if re.search(r"\b(state|estado)\b", tail):
            return None
    return city


def _extract_city_from_infobox(html: str) -> str | None:
    """Cidade de campos de infobox de localizacao (PT/EN). Nao usa endereco/owner/capacidade."""
    if not html:
        return None
    for label in ("localização", "localizacao", "cidade", "location", "city", "municipality"):
        for m in re.finditer(rf"(?is){label}.{{0,80}}", html):
            window = m.group(0)
            if _is_forbidden_location_object(window):
                continue
            folded = _fold(window).lower()
            for alias, canon in _CITY_ALIASES.items():
                if re.search(rf"\b{re.escape(alias)}\b", folded):
                    return canon
    return None


def _build_geo_triple(subject: str, city_folded: str, evidence_type: str, excerpt: str, source_url: str) -> dict:
    city = ALLOWED_CITIES.get(city_folded, "SÃO PAULO")
    return {
        "subject": subject,
        "predicate": PREDICATE,
        "object": city,
        "confidence": 0.95 if evidence_type == "infobox" else 0.90,
        "metadata": {
            "source_type": "wiki_narrative",
            "extraction_method": "geo_wiki_dedicated_parser",
            "geo_schema": "stadium_city_localization",
            "publisher_family": "Wikimedia",
            "subject_pin": "url_cluster",
            "evidence_type": evidence_type,
            "evidence_excerpt": excerpt[:160],
            "source_url": source_url,
        },
    }


def html_to_text(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"(?s)<[^>]+>", " ", html or "")).strip()


def extract_geo_localizado_from_wiki(
    source_url: str,
    cleaned_text: str,
    html: str | None = None,
) -> list[dict]:
    """Triples GEO allowlisted de uma pagina wiki de estadio (subject pinado pela URL)."""
    subject = _pin_subject_by_url(source_url)
    if not subject:
        return []

    city = _extract_city_from_infobox(html) if html else None
    evidence_type = "infobox"
    excerpt = ""
    if not city:
        text = cleaned_text or (html_to_text(html) if html else "")
        for sentence in re.split(r"(?<=[.!?])\s+", text):
            city = _extract_city_from_sentence(sentence)
            if city:
                evidence_type = "lead_sentence"
                excerpt = sentence.strip()
                break
    if not city:
        return []
    return [_build_geo_triple(subject, city, evidence_type, excerpt, source_url)]
