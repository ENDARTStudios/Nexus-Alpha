"""#048.10G — testes da allowlist de segurança para Nominatim/OSM. Sem rede."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "config" / "security_policies.json"


def _policy() -> dict:
    return json.loads(POLICY.read_text(encoding="utf-8"))


def test_nominatim_trusted_domain_allowlisted():
    policy = _policy()
    trusted = policy.get("trusted_domains") or {}
    assert "nominatim.openstreetmap.org" in trusted
    entry = trusted["nominatim.openstreetmap.org"]
    assert entry["publisher"] == "OpenStreetMap"
    assert entry["publisher_family"] == "OpenStreetMap"
    assert entry["license"] == "ODbL"
    assert "application/json" in entry["allowed_content_types"]
    assert int(entry["rate_limit_rps"]) == 1


def test_no_wildcards_in_trusted_domains():
    trusted = _policy().get("trusted_domains") or {}
    for key in trusted:
        assert "*" not in key, key


def test_openstreetmap_is_independent_family():
    families = _policy().get("publisher_families") or {}
    assert "OpenStreetMap" in families
    assert "Wikimedia" in families["OpenStreetMap"]["independent_from"]
    assert "RSSSF" in families["OpenStreetMap"]["independent_from"]


def test_quorum_unchanged():
    assert _policy()["triangulation"]["quorum"] == 3


def test_forbidden_domains_absent():
    text = POLICY.read_text(encoding="utf-8").lower()
    for forbidden in ("transfermarkt", "soccerway", "facebook.com", "bet365", "almanaquedosclubes"):
        assert forbidden not in text, forbidden
