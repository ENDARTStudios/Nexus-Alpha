"""#048.10M — Política de fontes de expansão (read-only, pura; testável).

Classifica domínios para expansão não-VENCEU: permitidos, advertidos e proibidos;
colapsa Wikipedia PT/EN em família Wikimedia; emite warning para RSSSF/RSSSF Brasil
(mesma família editorial suspeita). NÃO faz rede.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.ops.publisher_family import (  # noqa: E402
    FAMILY_RSSSF,
    FAMILY_UNKNOWN,
    FAMILY_WIKIMEDIA,
    classify_publisher_family,
)

ALLOWED_DOMAINS = {
    "pt.wikipedia.org", "en.wikipedia.org",
    "rsssf.org", "www.rsssf.org", "rsssfbrasil.com", "www.rsssfbrasil.com",
    "nominatim.openstreetmap.org",
}
WARNED_DOMAINS = {
    "commons.wikimedia.org", "wikidata.org", "news.wikimedia.org",
}
PROHIBITED_DOMAINS = {
    "transfermarkt.com", "transfermarkt.co.uk", "transfermarkt.pt",
    "soccerway.com", "www.soccerway.com", "worldfootball.net", "www.worldfootball.net",
    "fbref.com", "www.fbref.com", "almanaquedosclubes.com", "www.almanaquedosclubes.com",
    "instagram.com", "twitter.com", "x.com", "facebook.com", "reddit.com",
    "bet365.com", "betano.com",
}
QUORUM = 3


def source_policy(domain: str) -> str:
    d = (domain or "").strip().lower()
    if d in PROHIBITED_DOMAINS:
        return "prohibited"
    if d in ALLOWED_DOMAINS:
        return "allowed"
    if d in WARNED_DOMAINS:
        return "warned"
    return "unknown"


def assess_domains(domains: list[str]) -> dict:
    """Avalia um conjunto de domínios para quórum/independência (política #048.10M)."""
    clean = sorted({(d or "").strip().lower() for d in domains if d})
    prohibited = [d for d in clean if source_policy(d) == "prohibited"]
    families = sorted({classify_publisher_family(d) for d in clean} - {FAMILY_UNKNOWN, ""})
    non_wikimedia = [d for d in clean if classify_publisher_family(d) != FAMILY_WIKIMEDIA]
    rsssf_domains = [d for d in clean if classify_publisher_family(d) == FAMILY_RSSSF]
    rsssf_warning = len(rsssf_domains) >= 1  # RSSSF/RSSSF Brasil: mesma família editorial suspeita
    distinct_domains = len(clean)
    eligible = (
        not prohibited
        and distinct_domains >= QUORUM
        and bool(non_wikimedia)
    )
    return {
        "distinct_domains": distinct_domains,
        "domains": clean,
        "publisher_families": families,
        "has_non_wikimedia": bool(non_wikimedia),
        "rsssf_same_family_warning": bool(rsssf_warning),
        "prohibited_domains": prohibited,
        "eligible_for_future_worker": eligible,
        "policy": {d: source_policy(d) for d in clean},
    }


if __name__ == "__main__":  # pragma: no cover
    import json

    print(json.dumps({
        "allowed": sorted(ALLOWED_DOMAINS),
        "warned": sorted(WARNED_DOMAINS),
        "prohibited": sorted(PROHIBITED_DOMAINS),
    }, ensure_ascii=False, indent=2))
