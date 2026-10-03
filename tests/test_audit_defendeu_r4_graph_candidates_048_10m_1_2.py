"""Testes do audit R4 dos candidatos DEFENDEU (#048.10M.1.2.R4) — offline."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "audit_r4",
    Path("scripts/audit_defendeu_r4_graph_candidates_048_10m_1_2.py"),
)
R4 = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(R4)


def test_script_uses_only_match_return(tmp_path):
    source = Path(R4.__file__).read_text(encoding="utf-8")
    forbidden = ["CREATE ", "MERGE ", "DELETE ", "SET ", "REMOVE ", "api/ingest", "worker_cycle"]
    upper = source.upper()
    for token in forbidden:
        assert token not in upper, f"escrita/ingest proibida no audit script: {token}"
    assert "MATCH" in source and "RETURN" in source


def test_probe_history_has_no_new_http_promises():
    for cid, history in R4.PROBE_HISTORY.items():
        assert isinstance(history, list)


def test_seed_coverage_covers_all_seven():
    for cid in [
        "defendeu_manuelfranciscodossantos_001", "defendeu_jairzinho_002",
        "defendeu_zito_003", "defendeu_socratesbrasileirosampai_005",
        "defendeu_romariodesouzafaria_006", "defendeu_carlosalbertotorres_007",
        "defendeu_rogerioceni_012",
    ]:
        assert cid in R4.SEED_COVERAGE


def test_canon_folds_accents_and_case():
    assert R4.canon("Garrincha") == "GARRINCHA"
    assert R4.canon("Sócrates Brasileiro") == "SOCRATES BRASILEIRO"
    assert R4.canon("  botafogo  ") == "BOTAFOGO"


def test_variants_include_aliases():
    entry = {"subject": "Manuel Francisco dos Santos", "subject_aliases": ["Garrincha"]}
    variants = R4.variants(entry, "subject")
    assert "MANUEL FRANCISCO DOS SANTOS" in variants
    assert "GARRINCHA" in variants


def test_committed_report_structure_and_no_drift_signals():
    report = json.loads(
        Path("reports/defendeu_r4_graph_candidates_048_10m_1_2.json").read_text(encoding="utf-8")
    )
    assert report["mode"] == "read_only_match_return"
    assert report["http_requests"] == 0
    assert report["candidates_total"] == 7
    by_id = {c["candidate_id"]: c for c in report["candidates"]}
    # Garrincha deve bater com R3 (2/3, sem drift)
    g = by_id["defendeu_manuelfranciscodossantos_001"]
    assert g["canonical_fact_present"] is True
    assert g["verified"] is False
    assert g["distinct_domain_count"] == 2
    assert set(g["confirmed_domains"]) == {"pt.wikipedia.org", "en.wikipedia.org"}
    assert g["span_broken"] is False and g["junk_object"] is False and g["forbidden_object"] is False
    # Nenhum candidato verificado ainda (worker não fechou quórum)
    assert all(c["verified"] is False for c in report["candidates"])


def test_garrincha_recommended_action_is_freeze():
    report = json.loads(
        Path("reports/defendeu_r4_graph_candidates_048_10m_1_2.json").read_text(encoding="utf-8")
    )
    g = next(c for c in report["candidates"] if c["candidate_id"] == "defendeu_manuelfranciscodossantos_001")
    assert g["recommended_next_action"].startswith("FREEZE")
