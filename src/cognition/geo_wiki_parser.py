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

# Lotes #048.10H (SÃO PAULO) + #048.10L (next batch).
ALLOWED_CITIES = {
    "SAO PAULO": "SÃO PAULO",
    "RIO DE JANEIRO": "RIO DE JANEIRO",
    "PORTO ALEGRE": "PORTO ALEGRE",
    "BELO HORIZONTE": "BELO HORIZONTE",
    "SALVADOR": "SALVADOR",
}

# URL (match por token no path) -> sujeito canonico esperado.
_URL_SUBJECT_TOKENS = (
    ("allianz_parque", "ALLIANZ PARQUE"),
    ("estadio_do_morumbi", "MORUMBI"),
    ("morumbi_stadium", "MORUMBI"),
    ("estadio_do_pacaembu", "PACAEMBU"),
    ("pacaembu_stadium", "PACAEMBU"),
    ("neo_quimica_arena", "NEO QUÍMICA ARENA"),
    # #048.10L — next batch
    ("nilton_santos", "ESTÁDIO OLÍMPICO NILTON SANTOS"),
    ("maracana", "MARACANÃ"),
    ("beira-rio", "BEIRA-RIO"),
    ("beira_rio", "BEIRA-RIO"),
    ("mineirao", "MINEIRÃO"),
    ("governador_magalhaes", "MINEIRÃO"),
    ("magalhaes_pinto", "MINEIRÃO"),
    ("fonte_nova", "ARENA FONTE NOVA"),
)

FORBIDDEN_TOKENS = (
    "bairro", "neighborhood", "district", "suburb", "borough", "estado", "state",
    "country", "brasil", "brazil", "rua", "avenida", "avenue", "street", "postcode",
    "coordenada", "coordinate", "owner", "tenant", "operator", "clube", "club",
    "futebol clube", "capacity", "surface", "architect", "opened", "home team",
    "address", "endereco",
    "palmeiras", "corinthians", "santos futebol",
)

# Alias -> chave dobrada (upper, sem acento) usada em ALLOWED_CITIES.
_CITY_ALIASES = {
    "sao paulo": "SAO PAULO",
    "rio de janeiro": "RIO DE JANEIRO",
    "porto alegre": "PORTO ALEGRE",
    "belo horizonte": "BELO HORIZONTE",
    "salvador": "SALVADOR",
}

CUE_PATTERNS = [
    r"localizado\s+(?:em|no|na|na cidade de|no municipio de)",
    r"localizada\s+(?:em|no|na|na cidade de|no municipio de)",
    r"situado\s+(?:em|no|na|na cidade de)",
    r"situada\s+(?:em|no|na|na cidade de)",
    r"localiza-se\s+em",
    r"fica\s+(?:em|no|na)",
    r"é um estádio[^.]{0,40}localizado\s+(?:em|no|na)",
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


def _extract_city_from_sentence(sentence: str, expected_city: str | None = None) -> str | None:
    """Cidade allowlisted se a frase tiver cue de localizacao e nao for bairro/pais/estado/clube/endereco.

    Se ``expected_city`` for fornecido (source-scoped), a frase so e aceita quando a cidade
    encontrada e EXATAMENTE a esperada -- rejeita cross-city (ex.: "Rio de Janeiro" no Mineirao).
    """
    folded = _fold(sentence).lower()
    if not any(re.search(p, folded) for p in CUE_PATTERNS):
        return None
    found = {canon for alias, canon in _CITY_ALIASES.items() if re.search(rf"\b{re.escape(alias)}\b", folded)}
    if not found:
        return None

    # Rejeicoes por token em qualquer lugar da frase (inclui estado/state como cidade).
    for tok in ("bairro", "neighborhood", "district", "suburb", "borough", "owner", "tenant", "clube", "club", "home of", "futebol clube", "estado", "state"):
        if re.search(rf"\b{re.escape(tok)}\b", folded):
            return None
    for tok in ("rua", "avenida", "avenue", "street", "postcode", "coordenada", "coordinate"):
        if re.search(rf"\b{re.escape(tok)}\b", folded):
            return None

    if expected_city:
        expected_key = _fold(expected_city)
        return expected_key if expected_key in found else None
    if len(found) != 1:
        return None  # nenhuma ou multiplas cidades -> ambiguo
    return next(iter(found))


def _extract_city_from_infobox(html: str, expected_city: str | None = None) -> str | None:
    """Cidade de campos de infobox de localizacao (PT/EN). Nao usa endereco/owner/capacidade.

    Se ``expected_city`` for fornecido, retorna SOMENTE a cidade esperada (ignora/ rejeita
    qualquer outra cidade na mesma pagina -- evita contaminacao cross-city de infobox).
    """
    if not html:
        return None
    expected_key = _fold(expected_city) if expected_city else None
    for label in ("localização", "localizacao", "cidade", "location", "city", "municipality"):
        for m in re.finditer(rf"(?is){label}.{{0,80}}", html):
            window = m.group(0)
            if _is_forbidden_location_object(window):
                continue
            folded = _fold(window).lower()
            found = {canon for alias, canon in _CITY_ALIASES.items() if re.search(rf"\b{re.escape(alias)}\b", folded)}
            if expected_key:
                if expected_key in found:
                    return expected_key
                continue
            for alias, canon in _CITY_ALIASES.items():
                if re.search(rf"\b{re.escape(alias)}\b", folded):
                    return canon
    return None


def _build_geo_triple(subject: str, city_folded: str, evidence_type: str, excerpt: str, source_url: str) -> dict:
    city = ALLOWED_CITIES.get(city_folded, city_folded)
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
    expected_city: str | None = None,
) -> list[dict]:
    """Triples GEO allowlisted de uma pagina wiki de estadio (subject pinado pela URL).

    ``expected_city`` (source-scoped) restringe a extracao a cidade esperada do cluster/fato,
    rejeitando contaminacao cross-city (ex.: Mineirao capturando "Rio de Janeiro").
    """
    subject = _pin_subject_by_url(source_url)
    if not subject:
        return []

    city = _extract_city_from_infobox(html, expected_city) if html else None
    evidence_type = "infobox"
    excerpt = ""
    if not city:
        text = cleaned_text or (html_to_text(html) if html else "")
        for sentence in re.split(r"(?<=[.!?])\s+", text):
            city = _extract_city_from_sentence(sentence, expected_city)
            if city:
                evidence_type = "lead_sentence"
                excerpt = sentence.strip()
                break
    if not city:
        return []
    return [_build_geo_triple(subject, city, evidence_type, excerpt, source_url)]
