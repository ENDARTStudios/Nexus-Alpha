"""#053.2 — testes da telemetria de familias de publishers (offline)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scripts.evaluate_training_gate as gate  # noqa: E402
from scripts.publisher_family_telemetry import classify_publisher_family, summarize_families  # noqa: E402


def test_wikipedia_languages_collapse_to_wikimedia():
    assert classify_publisher_family("pt.wikipedia.org") == "Wikimedia"
    assert classify_publisher_family("en.wikipedia.org") == "Wikimedia"


def test_rsssf_and_rsssfbrasil_same_family():
    assert classify_publisher_family("rsssf.org") == "RSSSF"
    assert classify_publisher_family("rsssfbrasil.com") == "RSSSF"


def test_openstreetmap_family():
    assert classify_publisher_family("nominatim.openstreetmap.org") == "OpenStreetMap"


def test_three_families():
    fams = summarize_families([
        "pt.wikipedia.org", "en.wikipedia.org", "rsssf.org", "rsssfbrasil.com", "nominatim.openstreetmap.org",
    ])
    assert fams["publisher_family_count"] == 3
    assert fams["effective_publisher_count"] == 3
    assert set(fams["publisher_family_distribution"]) == {"Wikimedia", "RSSSF", "OpenStreetMap"}


def test_unknown_domain_not_independent_family():
    fams = summarize_families(["evil.example.com", "blogspot.com"])
    assert fams["publisher_family_count"] == 0


def test_warnings_present():
    fams = summarize_families(["pt.wikipedia.org", "rsssf.org", "nominatim.openstreetmap.org"])
    assert "RSSSF_AND_RSSSF_BRASIL_SAME_FAMILY_SUSPECTED" in fams["publisher_independence_warnings"]
    assert "WIKIMEDIA_MULTIPLE_LANGUAGES_NOT_INDEPENDENT" in fams["publisher_independence_warnings"]
    assert "OPENSTREETMAP_IS_GEOGRAPHIC_OPEN_DATA_NOT_NEWS_EDITORIAL" in fams["publisher_independence_warnings"]


def test_gate_publisher_family_maps_osm():
    assert gate._publisher_family("nominatim.openstreetmap.org") == "OpenStreetMap"
    assert gate._publisher_family("pt.wikipedia.org") == "Wikimedia"


def test_gate_family_warnings_helper():
    warnings = gate._family_warnings({"Wikimedia", "RSSSF", "OpenStreetMap"})
    assert len(warnings) == 3


def test_training_allowed_stays_false_in_gate_report():
    import json

    p = ROOT / "reports" / "training_gate_evaluation_060.json"
    if p.exists():
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data.get("training_allowed") is False
