"""Testes dos clusters de seeds curados (#048) — estruturais, sem rede."""
from __future__ import annotations

from pathlib import Path

from src.miner.seed_loader import (
    FORBIDDEN_DOMAINS,
    SECRET_MARKERS,
    cluster_to_seeds,
    load_seed_clusters,
    manifest_health,
    validate_seed_clusters,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "config" / "seed_clusters.yaml"


def _data():
    return load_seed_clusters(MANIFEST)


def test_shipped_manifest_is_structurally_valid():
    assert validate_seed_clusters(_data()) == []


def test_shipped_manifest_health():
    health = manifest_health(_data())
    assert health["configured"] >= 3
    assert health["domains_expected"] >= 3
    assert health["distinct_publishers_expected"] >= 2
    assert health["urls_injected"] >= 9


def test_every_cluster_has_three_domains_two_publishers_and_non_wikipedia():
    for cluster in _data()["clusters"]:
        domains = {s["domain"] for s in cluster["sources"]}
        publishers = {s["publisher"] for s in cluster["sources"]}
        assert len(domains) >= 3, cluster["id"]
        assert len(publishers) >= 2, cluster["id"]
        assert any("wikipedia" not in p.lower() for p in publishers), cluster["id"]


def test_urls_are_https_unique_and_well_formed():
    data = _data()
    urls = cluster_to_seeds(data)
    assert len(urls) == len(set(urls))
    for url in urls:
        assert url.startswith("https://")
        host = url.split("/")[2]
        assert not any(host == f or host.endswith("." + f) for f in FORBIDDEN_DOMAINS)


def test_manifest_text_has_no_secret_markers():
    text = MANIFEST.read_text(encoding="utf-8").lower()
    for marker in SECRET_MARKERS:
        assert marker not in text, marker


def test_garrincha_botafogo_has_productive_en_source():
    """#048.4 — cluster Botafogo cobre EN canônica produtiva (validada offline)."""
    cluster = next(
        (c for c in _data()["clusters"] if c["id"] == "garrincha_botafogo"),
        None,
    )
    assert cluster is not None
    urls = [s["url"] for s in cluster["sources"]]
    assert "https://en.wikipedia.org/wiki/Botafogo_de_Futebol_e_Regatas" in urls
    en = next(s for s in cluster["sources"] if s["domain"] == "en.wikipedia.org" and "Botafogo" in s["url"])
    assert en["domain"] == "en.wikipedia.org"
    assert en["publisher"] == "Wikimedia"
    domains = {s["domain"] for s in cluster["sources"]}
    publishers = {s["publisher"] for s in cluster["sources"]}
    assert len(domains) >= 3
    assert len(publishers) >= 2
    assert any("wikipedia" not in p.lower() for p in publishers)
    assert len(urls) == len(set(urls))


def test_no_seed_references_stale_botafogo_404_url():
    """#048.3/#048.4 — URL EN 404 histórica não pode voltar ao manifesto."""
    text = MANIFEST.read_text(encoding="utf-8")
    assert "Botafogo_F.C._%28Rio_de_Janeiro%29" not in text
    assert "Botafogo_F.C._(Rio_de_Janeiro)" not in text


HONOURS_CLUSTERS = {
    "botafogo_libertadores": "https://www.rsssf.org/sacups/copalib.html",
    "santos_libertadores": "https://www.rsssf.org/sacups/copalib.html",
    "botafogo_brasileirao": "https://www.rsssf.org/tablesb/brazchamp.html",
}


def test_rsssf_honours_clusters_present_and_valid():
    """#048.6 batch 3 — clusters de honras com RSSSF elegível (dry-run #058.12)."""
    data = _data()
    by_id = {c["id"]: c for c in data["clusters"]}
    for cluster_id, rsssf_url in HONOURS_CLUSTERS.items():
        assert cluster_id in by_id, f"cluster ausente: {cluster_id}"
        cluster = by_id[cluster_id]
        urls = [s["url"] for s in cluster["sources"]]
        assert rsssf_url in urls, f"RSSSF ausente em {cluster_id}"
        domains = {s["domain"] for s in cluster["sources"]}
        publishers = {s["publisher"] for s in cluster["sources"]}
        assert len(domains) >= 3, cluster_id
        assert len(publishers) >= 2, cluster_id
        assert "RSSSF" in publishers, cluster_id
        assert any("wikipedia" not in p.lower() for p in publishers), cluster_id
        rsssf_sources = [s for s in cluster["sources"] if s["domain"] == "rsssf.org"]
        assert rsssf_sources and all(s["url"].startswith("https://") for s in rsssf_sources)


def test_rsssf_publisher_counts_as_independent():
    """RSSSF é publisher independente (não-Wikimedia) para quórum editorial."""
    data = _data()
    publishers = {
        str(s.get("publisher"))
        for c in data["clusters"] for s in (c.get("sources") or [])
    }
    assert "RSSSF" in publishers
    assert "wikipedia" not in "rsssf"
    assert "wikimedia" not in "rsssf"


def test_santos_brasileirao_cluster_absent_without_evidence():
    """#048.6 batch 3 — dry-run mostrou 0 hits p/ santos_brasileirao: sem seed."""
    by_id = {c["id"]: c["id"] for c in _data()["clusters"]}
    assert "santos_brasileirao" not in by_id


def _base_cluster(**over):
    cluster = {
        "id": "c1", "topic": "t",
        "sources": [
            {"url": "https://pt.wikipedia.org/wiki/A", "domain": "pt.wikipedia.org", "publisher": "Wikimedia"},
            {"url": "https://en.wikipedia.org/wiki/A", "domain": "en.wikipedia.org", "publisher": "Wikimedia"},
            {"url": "https://example.org/a", "domain": "example.org", "publisher": "Example"},
        ],
    }
    cluster.update(over)
    return cluster


def test_validator_rejects_too_few_domains():
    data = {"clusters": [_base_cluster(sources=[
        {"url": "https://a.com/1", "domain": "a.com", "publisher": "A"},
        {"url": "https://a.com/2", "domain": "a.com", "publisher": "A"},
    ])]}
    errors = validate_seed_clusters(data)
    assert any("domínios distintos" in e or "sources" in e for e in errors)


def test_validator_rejects_wikipedia_only():
    data = {"clusters": [_base_cluster(sources=[
        {"url": "https://pt.wikipedia.org/wiki/A", "domain": "pt.wikipedia.org", "publisher": "Wikimedia"},
        {"url": "https://en.wikipedia.org/wiki/A", "domain": "en.wikipedia.org", "publisher": "Wikimedia"},
        {"url": "https://es.wikipedia.org/wiki/A", "domain": "es.wikipedia.org", "publisher": "Wikimedia"},
    ])]}
    assert any("fora de wikipedia" in e for e in validate_seed_clusters(data))


def test_validator_rejects_forbidden_and_http_and_duplicate():
    data = {"clusters": [_base_cluster(sources=[
        {"url": "http://facebook.com/x", "domain": "facebook.com", "publisher": "Meta"},
        {"url": "https://example.org/a", "domain": "example.org", "publisher": "Example"},
        {"url": "https://example.org/a", "domain": "example.org", "publisher": "Example"},
    ])]}
    errors = validate_seed_clusters(data)
    assert any("não-HTTPS" in e for e in errors)
    assert any("proibido" in e for e in errors)
    assert any("duplicada" in e for e in errors)


MULTI_CLUB_HONOURS = {
    "flamengo_honours": ["https://pt.wikipedia.org/wiki/Clube_de_Regatas_do_Flamengo",
                         "https://en.wikipedia.org/wiki/CR_Flamengo",
                         "https://www.rsssf.org/sacups/copalib.html"],
    "palmeiras_honours": ["https://pt.wikipedia.org/wiki/Sociedade_Esportiva_Palmeiras",
                          "https://en.wikipedia.org/wiki/SE_Palmeiras",
                          "https://www.rsssf.org/sacups/copalib.html",
                          "https://www.rsssf.org/tablesb/brazchamp.html"],
    "sao_paulo_honours": ["https://pt.wikipedia.org/wiki/S%C3%A3o_Paulo_Futebol_Clube",
                          "https://en.wikipedia.org/wiki/S%C3%A3o_Paulo_FC",
                          "https://www.rsssf.org/sacups/copalib.html",
                          "https://www.rsssf.org/tablesb/brazchamp.html"],
    "gremio_honours": ["https://pt.wikipedia.org/wiki/Gr%C3%AAmio_Foot-Ball_Porto_Alegrense",
                       "https://en.wikipedia.org/wiki/Gr%C3%AAmio_FBPA",
                       "https://www.rsssf.org/sacups/copalib.html"],
    "internacional_honours": ["https://pt.wikipedia.org/wiki/Sport_Club_Internacional",
                              "https://en.wikipedia.org/wiki/SC_Internacional",
                              "https://www.rsssf.org/sacups/copalib.html"],
}


def test_multi_club_honours_clusters_present_and_valid():
    """#048.9 — 5 clusters de clubes com pt/en wiki + RSSSF (>=3 domínios)."""
    by_id = {c["id"]: c for c in _data()["clusters"]}
    for cid, urls in MULTI_CLUB_HONOURS.items():
        assert cid in by_id, cid
        cluster = by_id[cid]
        cluster_urls = [s["url"] for s in cluster["sources"]]
        for u in urls:
            assert u in cluster_urls, f"{cid}: {u}"
        domains = {s["domain"] for s in cluster["sources"]}
        publishers = {s["publisher"] for s in cluster["sources"]}
        assert len(domains) >= 3, cid
        assert len(publishers) >= 2, cid
        assert "RSSSF" in publishers, cid
        assert any("wikipedia" not in p.lower() for p in publishers), cid


def test_pele_santos_third_source_defendeu():
    """#059C — cluster pele_santos inclui a terceira fonte independente (RSSSF Brasil)."""
    cluster = next(c for c in _data()["clusters"] if c["id"] == "pele_santos")
    urls = [s["url"] for s in cluster["sources"]]
    assert "https://www.rsssfbrasil.com/sel/jogclub.htm" in urls
    domains = {s["domain"] for s in cluster["sources"]}
    assert "rsssfbrasil.com" in domains
    assert len(domains) >= 3
    rsssf = next(s for s in cluster["sources"] if s["domain"] == "rsssfbrasil.com")
    assert rsssf["url"].startswith("https://")
    assert rsssf["publisher"] == "RSSSF Brasil"


GEO_CLUSTERS = (
    "allianz_parque_localization",
    "morumbi_localization",
    "pacaembu_localization",
    "neo_quimica_arena_localization",
)


def test_geo_localization_clusters_present_and_valid():
    """#048.10G — clusters GEO com OSM/Nominatim como terceira família independente."""
    by_id = {c["id"]: c for c in _data()["clusters"]}
    for cid in GEO_CLUSTERS:
        assert cid in by_id, f"cluster GEO ausente: {cid}"
        cluster = by_id[cid]
        assert cluster.get("expected_predicate") == "LOCALIZADO_EM", cid
        domains = {s["domain"] for s in cluster["sources"]}
        publishers = {s["publisher"] for s in cluster["sources"]}
        assert len(domains) >= 3, cid
        assert "nominatim.openstreetmap.org" in domains, cid
        assert "OpenStreetMap" in publishers, cid
        assert len(publishers) >= 2, cid
        nominatim = next(s for s in cluster["sources"] if s["domain"] == "nominatim.openstreetmap.org")
        assert "format=json" in nominatim["url"], cid
        assert "addressdetails=1" in nominatim["url"], cid


def test_openstreetmap_not_treated_as_wikimedia():
    """OSM é família editorial independente; não conta como Wikimedia."""
    from src.miner.seed_loader import _is_wikipedia

    assert not _is_wikipedia("OpenStreetMap")
