"""#048.10M — testes da política de fontes de expansão (pura, sem rede)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_expansion_source_policy_048_10m import (  # noqa: E402
    PROHIBITED_DOMAINS,
    assess_domains,
    source_policy,
)

WIKI_PT_EN = ["pt.wikipedia.org", "en.wikipedia.org"]
TRIPLE_OK = ["pt.wikipedia.org", "en.wikipedia.org", "rsssf.org"]


def test_prohibited_sources_are_classified_prohibited():
    for d in ("transfermarkt.com", "soccerway.com", "almanaquedosclubes.com"):
        assert source_policy(d) == "prohibited"
        assert d in PROHIBITED_DOMAINS


def test_eligible_when_three_distinct_with_non_wikimedia():
    a = assess_domains(TRIPLE_OK)
    assert a["distinct_domains"] == 3
    assert a["has_non_wikimedia"] is True
    assert a["eligible_for_future_worker"] is True
    assert a["publisher_families"][:2] != []


def test_wikipedia_pt_en_collapse_to_wikimedia_family():
    a = assess_domains(WIKI_PT_EN)
    # dois domínios, mas apenas uma família (Wikimedia) -> não conta independência
    assert a["distinct_domains"] == 2
    assert a["publisher_families"] == ["Wikimedia"]
    assert a["has_non_wikimedia"] is False
    assert a["eligible_for_future_worker"] is False


def test_rsssf_same_family_warning():
    a = assess_domains(["rsssf.org", "rsssfbrasil.com"])
    assert a["rsssf_same_family_warning"] is True
    assert a["eligible_for_future_worker"] is False  # só RSSSF, sem non-wikimedia


def test_missing_third_domain_not_eligible():
    a = assess_domains(["pt.wikipedia.org", "rsssf.org"])
    assert a["distinct_domains"] == 2
    assert a["eligible_for_future_worker"] is False


def test_prohibited_domain_blocks_eligibility():
    a = assess_domains(TRIPLE_OK + ["transfermarkt.com"])
    assert "transfermarkt.com" in a["prohibited_domains"]
    assert a["eligible_for_future_worker"] is False
