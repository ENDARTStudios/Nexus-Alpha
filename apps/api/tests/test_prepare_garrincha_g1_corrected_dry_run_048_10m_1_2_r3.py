"""Testes offline do R3 Fase C — dry-run corrigido R3 (fixtures).

Regra fundamental: only_in_local_reports / blocked / prohibited NUNCA contam
como minerado. ready só true com probe confirmado. Nenhum teste faz HTTP ou
escreve em grafo.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.prepare_garrincha_g1_corrected_dry_run_048_10m_1_2_r3 import (  # noqa: E402
    SEED_RSSSF_URLS,
)


def _graph_ok() -> dict:
    return {
        "confirmed_domains": ["en.wikipedia.org", "pt.wikipedia.org"],
        "distinct_domain_count": 2,
        "canonical_fact_found": True,
        "same_triple_confirmation": True,
        "span_broken": False,
        "junk_object": False,
        "forbidden_object": False,
        "homonymy_risk": "low",
    }


def _probe_summary(confirmed_url: str | None) -> dict:
    import urllib.parse

    probes = []
    for u in SEED_RSSSF_URLS:
        hit = confirmed_url is not None and u == confirmed_url
        probes.append({
            "domain": urllib.parse.urlparse(u).netloc,
            "url": u,
            "http_status": 200 if hit or confirmed_url is None else 200,
            "mentions_garrincha": hit,
            "mentions_botafogo": True,
            "mentions_defendeu_context": hit,
        })
    return {"probes": probes}


def _build(confirmed_url: str | None) -> dict:
    from scripts.prepare_garrincha_g1_corrected_dry_run_048_10m_1_2_r2 import (
        build_corrected_dry_run,
    )
    return build_corrected_dry_run(_graph_ok(), [_probe_summary(confirmed_url)], SEED_RSSSF_URLS)


def test_r3_ready_true_com_jogclub_confirmado() -> None:
    out = _build("https://www.rsssfbrasil.com/sel/jogclub.htm")
    assert out["ready_for_future_g1"] is True
    assert out["domains_to_be_mined_in_future_g1"] == ["www.rsssfbrasil.com"]
    assert out["predicted_distinct_domains_after_g1"] == 3
    assert out["predicted_new_verified_if_g1_succeeds"] == 1
    assert out["predicted_records_total_if_g1_succeeds"] == 21


def test_r3_ready_false_sem_confirmacao() -> None:
    out = _build(None)
    assert out["ready_for_future_g1"] is False
    assert out["domains_to_be_mined_in_future_g1"] == []
    assert out["predicted_distinct_domains_after_g1"] == 2
    assert out["predicted_new_verified_if_g1_succeeds"] == 0
    assert out["predicted_records_total_if_g1_succeeds"] == 20
    # only_in_local_reports contém os domínios seed não confirmados
    assert "www.rsssfbrasil.com" in out["domains_only_in_local_reports"]
    assert "www.rsssf.org" in out["domains_only_in_local_reports"]


def test_r3_only_in_local_reports_nao_conta_como_minerado() -> None:
    out = _build(None)
    for domain in out["domains_only_in_local_reports"]:
        assert domain not in out["domains_to_be_mined_in_future_g1"]
    assert out["predicted_distinct_domains_after_g1"] == 2


def test_r3_domains_blocked_vazio_neste_cenario() -> None:
    out = _build(None)
    assert out["domains_blocked_or_unavailable"] == []


def test_r3_domains_prohibited_vazio_sem_fonte_proibida() -> None:
    out = _build(None)
    assert out["domains_prohibited"] == []
