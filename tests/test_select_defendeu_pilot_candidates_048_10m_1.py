"""Testes do seletor do piloto DEFENDEU (#048.10M.1 §12.1)."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "select_defendeu_pilot",
    Path("scripts/select_defendeu_pilot_candidates_048_10m_1.py"),
)
SELECT = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(SELECT)


def _candidate(cid: str, risk: str = "low", **overrides) -> dict:
    base = {
        "candidate_id": cid,
        "subject": f"JOGADOR {cid}",
        "subject_aliases": [f"Jog{cid[-3:]}"],
        "predicate": "DEFENDEU",
        "object": "BOTAFOGO DE FUTEBOL E REGATAS",
        "object_aliases": ["Botafogo"],
        "required_domains": ["pt.wikipedia.org", "en.wikipedia.org", "rsssf.org"],
        "evidence_status": "candidate_unverified",
        "already_verified": False,
        "risk_level": risk,
        "risks": [],
        "source_policy": "allowed",
        "requires_ontology_change": False,
        "notes": "exploratory_candidate",
    }
    base.update(overrides)
    return base


def test_high_risk_not_selected():
    atlas = {"candidates": [_candidate("defendeu_x_100", risk="high")]}
    result = SELECT.select_pilot(atlas)
    assert result["selected"] == []
    assert result["summary"]["high_risk_selected"] == 0


def test_ontology_change_excluded():
    atlas = {"candidates": [_candidate("defendeu_x_101", requires_ontology_change=True)]}
    result = SELECT.select_pilot(atlas)
    assert result["selected"] == []
    assert any("estrutural" in e["reason"] for e in result["excluded"])


def test_no_non_wikimedia_domain_excluded():
    atlas = {"candidates": [_candidate(
        "defendeu_x_102",
        required_domains=["pt.wikipedia.org", "en.wikipedia.org", "commons.wikimedia.org"],
    )]}
    result = SELECT.select_pilot(atlas)
    assert result["selected"] == []


def test_multiple_clubs_ambiguity_excluded():
    """Ronaldo/Denílson (D1+D3+múltiplos clubes) ficam fora por conservadorismo."""
    atlas = {"candidates": [_candidate("defendeu_ronaldoluisnazariodelima_009")]}
    result = SELECT.select_pilot(atlas)
    assert result["selected"] == []
    assert "múltiplos clubes" in result["excluded"][0]["reason"]


def test_player_name_ambiguity_excluded():
    atlas = {"candidates": [_candidate("defendeu_niltonreisdossantos_008")]}
    result = SELECT.select_pilot(atlas)
    assert result["selected"] == []
    assert "homonímia" in result["excluded"][0]["reason"]


def test_max_selection_is_10():
    candidates = [_candidate(f"defendeu_jog_{i:03d}", risk="low") for i in range(100, 115)]
    result = SELECT.select_pilot({"candidates": candidates})
    assert len(result["selected"]) == 10


def test_min_selection_is_6_for_ready():
    atlas = {"candidates": [_candidate(f"defendeu_jog_{i:03d}") for i in range(100, 105)]}
    result = SELECT.select_pilot(atlas)
    assert result["summary"]["ready_for_dry_run"] is False
    assert 0 < len(result["selected"]) < 6


def test_low_risk_prioritized_over_medium():
    candidates = [
        _candidate("defendeu_med_001", risk="medium"),
        _candidate("defendeu_low_001", risk="low"),
    ]
    result = SELECT.select_pilot({"candidates": candidates})
    assert result["selected"][0]["candidate_id"] == "defendeu_low_001"


def test_expected_facts_registry_shape():
    atlas = {"candidates": [_candidate("defendeu_jog_100")]}
    selection = SELECT.select_pilot(atlas)
    registry = SELECT.build_expected_facts(selection)
    assert registry["status"] == "planned_not_active"
    assert registry["expected_facts"][0]["fact"] == "JOGADOR defendeu_jog_100 --DEFENDEU--> BOTAFOGO DE FUTEBOL E REGATAS"
    assert registry["expected_facts"][0]["min_domain_count"] == 3
    assert "DISPUTOU" in registry["forbidden_predicates"]
    assert "CIDADE" in registry["forbidden_objects"]


def test_real_atlas_selects_seven():
    """Integração com o atlas real: 7 selecionados (Rivelino excluído por evidência)."""
    atlas = json.loads(SELECT.ATLAS_PATH.read_text(encoding="utf-8"))
    result = SELECT.select_pilot(atlas)
    assert result["selected_count"] == 7
    selected_ids = {s["candidate_id"] for s in result["selected"]}
    assert "defendeu_arthurantunescoimbra_004" not in selected_ids
    assert result["summary"]["ready_for_dry_run"] is True
