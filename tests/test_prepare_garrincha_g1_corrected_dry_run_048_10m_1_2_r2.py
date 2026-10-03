"""Testes offline do R2 Fase C — dry-run corrigido (semântica D5, fixtures).

Garante: local_existing_covered NÃO é contado como minerado; baldes separados;
gate rígido; fonte proibida/junk/span bloqueiam. Nenhum teste escreve em
Neo4j/Qdrant, nenhum chama /api/ingest, nenhum roda worker.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.prepare_garrincha_g1_corrected_dry_run_048_10m_1_2_r2 import (  # noqa: E402
    build_corrected_dry_run,
    collect_probe_domains,
)

GRAPH_OK = {
    "canonical_fact_found": True,
    "same_triple_confirmation": True,
    "confirmed_domains": ["en.wikipedia.org", "pt.wikipedia.org"],
    "distinct_domain_count": 2,
    "span_broken": False,
    "junk_object": False,
    "forbidden_object": False,
    "homonymy_risk": "low",
}

SEEDS = [
    "https://www.rsssfbrasil.com/sel/jogclub.htm",
    "https://www.rsssf.org/tablesb/brazchamp.html",
    "https://www.rsssf.org/sacups/copalib.html",
]


def summary(*urls: str) -> dict:
    return {
        "probes": [
            {"domain": __import__("urllib.parse", fromlist=["urlparse"]).urlparse(u).netloc,
             "url": u, "http_status": 200,
             "mentions_garrincha": True, "mentions_botafogo": True,
             "mentions_defendeu_context": True}
            for u in urls
        ]
    }


def probe_404(url: str) -> dict:
    import urllib.parse
    return {
        "probes": [{
            "domain": urllib.parse.urlparse(url).netloc,
            "url": url, "http_status": 404,
            "mentions_garrincha": False, "mentions_botafogo": False,
        }]
    }


def test_probe_confirmado_vai_para_a_miner() -> None:
    mined, only_local, p404, prohibited = collect_probe_domains([summary("https://www.rsssf.org/tablesb/brazchamp.html")])
    assert len(mined) == 1
    assert p404 == []
    assert only_local == []


def test_probe_404_vira_path_transparente_nao_bloqueado() -> None:
    mined, only_local, p404, prohibited = collect_probe_domains([probe_404("https://www.rsssf.org/tablesb/botafogo.html")])
    assert mined == []
    assert p404[0]["http_status"] == 404
    # 404 em caminho errado NÃO é domínio bloqueado (servidor respondeu)


def test_dry_run_ready_com_probe_confirmado() -> None:
    out = build_corrected_dry_run(GRAPH_OK, [summary("https://www.rsssf.org/tablesb/brazchamp.html")], SEEDS)
    assert out["ready_for_future_g1"] is True
    assert out["domains_already_confirmed_in_graph"] == ["en.wikipedia.org", "pt.wikipedia.org"]
    assert out["domains_to_be_mined_in_future_g1"] == ["www.rsssf.org"]
    assert out["domains_only_in_local_reports"] == ["www.rsssfbrasil.com"]
    assert out["predicted_distinct_domains_after_g1"] == 3
    assert out["predicted_new_verified_if_g1_succeeds"] == 1
    assert out["predicted_records_total_if_g1_succeeds"] == 21
    assert out["requires_core_change"] is False
    assert out["requires_alias_change"] is False
    assert out["requires_seed_change"] is False


def test_dry_run_sem_probe_confirmed_vira_ready_false() -> None:
    out = build_corrected_dry_run(GRAPH_OK, [probe_404("https://www.rsssf.org/tablesb/botafogo.html")], SEEDS)
    assert out["ready_for_future_g1"] is False
    assert out["domains_to_be_mined_in_future_g1"] == []
    assert out["predicted_new_verified_if_g1_succeeds"] == 0
    assert out["predicted_records_total_if_g1_succeeds"] == 20
    assert "brazchamp" in (out["blocking_reason"] or "") or "probe" in (out["blocking_reason"] or "")


def test_d5_local_existing_nao_e_minerado() -> None:
    """Sem nenhum probe: local_existing (domínios confirmados no grafo) NÃO vira
    domains_to_be_mined — a correção D5 exata que o task exige."""
    out = build_corrected_dry_run(GRAPH_OK, [], SEEDS)
    assert out["domains_to_be_mined_in_future_g1"] == []
    assert out["domains_already_confirmed_in_graph"] == ["en.wikipedia.org", "pt.wikipedia.org"]
    assert out["ready_for_future_g1"] is False


def test_fonte_proibida_nunca_vira_mined() -> None:
    bad = {"probes": [{
        "domain": "transfermarkt.com", "url": "https://www.transfermarkt.com/x",
        "http_status": 200, "mentions_garrincha": True,
        "mentions_botafogo": True, "mentions_defendeu_context": True,
    }]}
    mined, only_local, p404, prohibited = collect_probe_domains([bad])
    assert mined == []  # o coletor nunca aceita domínio fora do allowlist
    assert len(prohibited) == 1
    assert prohibited[0]["domain"] == "transfermarkt.com"


def test_span_quebrado_bloqueia_ready() -> None:
    graph = {**GRAPH_OK, "span_broken": True}
    out = build_corrected_dry_run(graph, [summary("https://www.rsssf.org/tablesb/brazchamp.html")], SEEDS)
    assert out["ready_for_future_g1"] is False
    assert out["blocking_reason"] == "BLOCKED_048_10M_1_2_R2_SEMANTIC_RISK"
