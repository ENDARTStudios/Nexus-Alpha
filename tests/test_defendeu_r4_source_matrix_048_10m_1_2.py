"""Testes da source matrix R4 (#048.10M.1.2.R4) — offline, sem HTTP."""
from __future__ import annotations

import json
from pathlib import Path


def _matrix() -> dict:
    return json.loads(
        Path("reports/defendeu_r4_source_matrix_048_10m_1_2.json").read_text(encoding="utf-8")
    )


def test_matrix_separates_buckets():
    m = _matrix()
    for key in [
        "domains_already_confirmed_in_graph",
        "domains_probe_200_no_mention",
        "domains_probe_404",
        "domains_only_in_local_reports",
        "domains_blocked_or_unavailable",
        "domains_prohibited",
    ]:
        assert key in m


def test_no_http_requests_in_matrix():
    assert _matrix()["http_requests"] == 0


def test_prohibited_sources_listed_and_empty_usage():
    m = _matrix()
    assert "Transfermarkt" in m["prohibited_sources"][0]
    for cid_domains in m["domains_already_confirmed_in_graph"].values():
        for domain in cid_domains:
            assert domain not in ("transfermarkt.com", "soccerway.com")


def test_rsssf_200_pages_do_not_count_as_confirmed():
    """Páginas 200-OK sem menção NÃO são evidência (lição R3/D9)."""
    m = _matrix()
    no_mention = m["domains_probe_200_no_mention"]["defendeu_manuelfranciscodossantos_001"]
    confirmed = m["domains_already_confirmed_in_graph"]["defendeu_manuelfranciscodossantos_001"]
    for entry in no_mention:
        for domain in confirmed:
            assert entry.split("/")[0] not in domain or domain not in entry


def test_only_local_reports_domains_are_quarantined():
    m = _matrix()
    assert set(m["domains_only_in_local_reports"]) == {"www.rsssf.org", "www.rsssfbrasil.com"}


def test_future_probes_have_governed_origin():
    m = _matrix()
    for cid, entries in m["future_probe_candidates_with_origin"].items():
        for entry in entries:
            assert "origin" in entry and entry["origin"]
            assert entry["origin"] != "suposição"
