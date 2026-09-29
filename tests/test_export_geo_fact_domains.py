"""#048.10H.4 — testes do export fact-level GEO (puro, sem rede)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.export_geo_fact_domains import build_fact_domains  # noqa: E402

EXPECTED = {
    "expected_facts": [
        {"fact": "ALLIANZ PARQUE --LOCALIZADO_EM--> SÃO PAULO", "subject": "ALLIANZ PARQUE", "predicate": "LOCALIZADO_EM", "object": "SÃO PAULO"},
        {"fact": "MORUMBI --LOCALIZADO_EM--> SÃO PAULO", "subject": "MORUMBI", "predicate": "LOCALIZADO_EM", "object": "SÃO PAULO"},
    ]
}
DOMAINS = ["pt.wikipedia.org", "en.wikipedia.org", "nominatim.openstreetmap.org"]


def test_build_fact_domains_strong():
    rows = [
        {"subject": "ALLIANZ PARQUE", "predicate": "LOCALIZADO_EM", "object": "SÃO PAULO", "verified": True, "domains": DOMAINS},
        {"subject": "MORUMBI", "predicate": "LOCALIZADO_EM", "object": "SÃO PAULO", "verified": True, "domains": DOMAINS},
    ]
    report = build_fact_domains(rows, EXPECTED)
    assert report["evidence_strength"] == "strong"
    assert report["summary"]["facts_with_three_domains"] == 2
    assert all(f["domain_count"] == 3 for f in report["facts"])


def test_build_fact_domains_partial():
    rows = [
        {"subject": "ALLIANZ PARQUE", "predicate": "LOCALIZADO_EM", "object": "SÃO PAULO", "verified": False, "domains": ["pt.wikipedia.org", "en.wikipedia.org"]},
    ]
    report = build_fact_domains(rows, EXPECTED)
    assert report["evidence_strength"] == "inferred"
    assert report["summary"]["facts_with_three_domains"] == 0


def test_build_fact_domains_insufficient_without_rows():
    report = build_fact_domains([], EXPECTED)
    assert report["evidence_strength"] == "insufficient"
