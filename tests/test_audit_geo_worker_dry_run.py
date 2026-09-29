"""#048.10L.3 — testes da auditoria do caminho GEO do worker (contrato 3-vias). Sem rede."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scripts.audit_geo_worker_dry_run as audit  # noqa: E402
import scripts.worker_cycle as worker  # noqa: E402

NOMINATIM = "https://nominatim.openstreetmap.org/search?format=json&addressdetails=1&limit=1&q=Allianz%20Parque"
WIKI = "https://pt.wikipedia.org/wiki/Allianz_Parque"
HTML = "https://pt.wikipedia.org/wiki/Santos_FC"


def test_split_geo_urls_returns_three_way():
    nominatim, geo_wiki, html = worker._split_geo_urls([NOMINATIM, WIKI, HTML])
    assert nominatim == [NOMINATIM]
    assert geo_wiki == [WIKI]
    assert html == [HTML]


def test_split_geo_urls_without_wiki_or_nominatim():
    nominatim, geo_wiki, html = worker._split_geo_urls([HTML])
    assert nominatim == [] and geo_wiki == [] and html == [HTML]


def test_worker_audit_report_gate_and_not_stale():
    report = audit.build_report()
    assert report["gate_passed"] is True
    assert report["audit_stale"] is False
    assert report["classification"] == "SUCCESS_048_10L_3_WORKER_PATH_READY"
    assert report["full_collision_facts_predicted"] == len(audit.STADIUMS)
    assert report["wiki_geo_triples_canonical"] == len(audit.WIKI)
    assert report["offline"] is True


def test_worker_audit_negatives_rejected():
    report = audit.build_report()
    assert report["neighborhood_objects_rejected"] is True
    assert report["cross_city_rejected"] is True
    assert report["non_venue_type_rejected"] is True
