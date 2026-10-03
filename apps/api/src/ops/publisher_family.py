"""#053.2.1 — Classificacao de familias de publishers (puro, read-only, sem cognicao).

Usado pelo runtime (`app.py` /metrics) e pelos scripts de auditoria/gate, para evitar
divergencia. Nao faz rede, nao toca Neo4j/Qdrant, nao altera verificacao/quorum.
"""
from __future__ import annotations

import collections
from dataclasses import dataclass, field

FAMILY_WIKIMEDIA = "Wikimedia"
FAMILY_RSSSF = "RSSSF"
FAMILY_OPENSTREETMAP = "OpenStreetMap"
FAMILY_ALMANAQUE = "Almanaque"
FAMILY_UNKNOWN = "Unknown"

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
    FAMILY_RSSSF: "RSSSF_AND_RSSSF_BRASIL_SAME_FAMILY_SUSPECTED",
    FAMILY_WIKIMEDIA: "WIKIMEDIA_MULTIPLE_LANGUAGES_NOT_INDEPENDENT",
    FAMILY_OPENSTREETMAP: "OPENSTREETMAP_IS_GEOGRAPHIC_OPEN_DATA_NOT_NEWS_EDITORIAL",
}


@dataclass
class PublisherFamilySnapshot:
    publisher_family_count: int
    effective_publisher_count: int
    publisher_family_distribution: dict[str, int] = field(default_factory=dict)
    publisher_independence_warnings: list[str] = field(default_factory=list)
    raw_domain_counts: dict[str, int] = field(default_factory=dict)


def classify_publisher_family(domain: str, publisher: str | None = None) -> str:
    """Classifica por DOMINIO (nunca por mencao textual)."""
    d = (domain or "").strip().lower()
    if d in WIKIMEDIA_DOMAINS or d.endswith(".wikipedia.org"):
        return FAMILY_WIKIMEDIA
    if d in RSSSF_DOMAINS:
        return FAMILY_RSSSF
    if d in OPENSTREETMAP_DOMAINS:
        return FAMILY_OPENSTREETMAP
    if d in ALMANAQUE_DOMAINS:
        return FAMILY_ALMANAQUE
    return FAMILY_UNKNOWN


def build_publisher_family_snapshot(
    domain_counts: dict[str, int],
    *,
    include_unknown_in_distribution: bool = False,
) -> PublisherFamilySnapshot:
    """Agrega contagens de dominio por familia. Unknown nao conta como independencia."""
    families: collections.Counter = collections.Counter()
    raw: dict[str, int] = {}
    for domain, count in (domain_counts or {}).items():
        try:
            n = int(count)
        except (TypeError, ValueError):
            n = 0
        raw[str(domain)] = n
        fam = classify_publisher_family(domain)
        if fam == FAMILY_UNKNOWN:
            if include_unknown_in_distribution and n:
                families[fam] += n
            continue
        families[fam] += n
    known = {k: v for k, v in families.items() if k != FAMILY_UNKNOWN and v > 0}
    count = len(known)
    warnings = [FAMILY_WARNINGS[f] for f in sorted(known) if f in FAMILY_WARNINGS]
    return PublisherFamilySnapshot(
        publisher_family_count=count,
        effective_publisher_count=count,
        publisher_family_distribution=dict(sorted(families.items())),
        publisher_independence_warnings=warnings,
        raw_domain_counts=raw,
    )
