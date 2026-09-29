"""#053.2 — Telemetria de familias de publishers (read-only, sem cognicao).

Classifica dominios em familias editoriais/geograficas e emite warnings de
independencia. NAO altera verificacao, quorum, ingest ou canonicalizacao.
"""
from __future__ import annotations

import collections

WIKIMEDIA_DOMAINS = {
    "pt.wikipedia.org", "en.wikipedia.org", "es.wikipedia.org", "fr.wikipedia.org",
    "de.wikipedia.org", "it.wikipedia.org", "wikipedia.org", "wikimedia.org",
}
RSSSF_DOMAINS = {"rsssf.org", "www.rsssf.org", "rsssfbrasil.com", "www.rsssfbrasil.com"}
OPENSTREETMAP_DOMAINS = {
    "openstreetmap.org", "www.openstreetmap.org", "nominatim.openstreetmap.org",
    "overpass-api.de", "overpass.kumi.systems",
}
ALMANAQUE_DOMAINS = {"almanaquedosclubes.com", "www.almanaquedosclubes.com"}

FAMILY_WARNINGS = {
    "RSSSF": "RSSSF_AND_RSSSF_BRASIL_SAME_FAMILY_SUSPECTED",
    "Wikimedia": "WIKIMEDIA_MULTIPLE_LANGUAGES_NOT_INDEPENDENT",
    "OpenStreetMap": "OPENSTREETMAP_IS_GEOGRAPHIC_OPEN_DATA_NOT_NEWS_EDITORIAL",
}


def classify_publisher_family(domain: str, publisher: str | None = None) -> str:
    d = (domain or "").strip().lower()
    if d in WIKIMEDIA_DOMAINS or d.endswith(".wikipedia.org"):
        return "Wikimedia"
    if d in RSSSF_DOMAINS:
        return "RSSSF"
    if d in OPENSTREETMAP_DOMAINS:
        return "OpenStreetMap"
    if d in ALMANAQUE_DOMAINS:
        return "Almanaque"
    return "Unknown"


def summarize_families(domains: list[str]) -> dict:
    """Contagem/distribuicao de familias e warnings. Unknown nao conta como familia independente."""
    counts: collections.Counter = collections.Counter()
    for dom in domains:
        fam = classify_publisher_family(dom)
        if fam != "Unknown":
            counts[fam] += 1
    families = sorted(counts)
    return {
        "publisher_family_count": len(families),
        "effective_publisher_count": len(families),
        "publisher_family_distribution": dict(counts),
        "publisher_independence_warnings": [FAMILY_WARNINGS[f] for f in families if f in FAMILY_WARNINGS],
    }
