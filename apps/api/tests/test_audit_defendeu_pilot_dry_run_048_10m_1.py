"""Testes do dry-run offline do piloto DEFENDEU (#048.10M.1 §12.2)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "audit_defendeu_dry_run",
    Path(__file__).resolve().parents[1] / "scripts" / "audit_defendeu_pilot_dry_run_048_10m_1.py",
)
DRY = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(DRY)


def _selection(count: int = 7) -> dict:
    selected = [
        {
            "candidate_id": f"defendeu_jog_{i:03d}",
            "subject": f"JOGADOR {i}",
            "subject_aliases": [],
            "predicate": "DEFENDEU",
            "object": "BOTAFOGO DE FUTEBOL E REGATAS",
            "object_aliases": ["Botafogo"],
            "risk": "low",
            "risks": [],
            "required_domains": ["pt.wikipedia.org", "en.wikipedia.org", "rsssf.org"],
            "source_policy": "allowed",
            "requires_ontology_change": False,
        }
        for i in range(count)
    ]
    return {"selected": selected, "excluded": [], "summary": {}}


def test_dry_run_is_offline(tmp_path, monkeypatch):
    """Sem diretório de probes: roda offline (LOCAL_EXISTING_EVIDENCE)."""
    monkeypatch.setattr(DRY, "PROBES_DIR", tmp_path / "no_probes")
    metrics, _ = DRY.dry_run(_selection(7))
    assert metrics["evidence_local_existing"] == 7
    assert metrics["evidence_real_page_readonly"] == 0
    assert metrics["evidence_synthetic_only"] == 0


def test_dry_run_never_writes_graph_or_ingests(tmp_path, monkeypatch):
    """Dry-run só escreve os relatórios declarados (sem rede, sem banco)."""
    monkeypatch.setattr(DRY, "PROBES_DIR", tmp_path / "no_probes")
    _, registry = DRY.dry_run(_selection(7))
    assert registry["status"] == "planned_not_active"
    # O script não importa cliente HTTP nem conectores de banco/worker.
    source = Path(DRY.__file__).read_text(encoding="utf-8")
    assert "urllib" not in source
    assert "httpx" not in source
    assert "graph_connector" not in source
    assert "worker_cycle" not in source


def test_synthetic_only_does_not_count_full_collision(tmp_path, monkeypatch):
    """Probe insuficiente (<3 domínios) degrada para LOCAL, nunca sintético; um
    candidato sem evidência alguma não é contado pelo seletor — full collision
    só conta evidência LOCAL_EXISTING ou REAL_PAGE_READONLY."""
    monkeypatch.setattr(DRY, "PROBES_DIR", tmp_path / "no_probes")
    metrics, _ = DRY.dry_run(_selection(7))
    assert metrics["evidence_synthetic_only"] == 0
    assert metrics["predicted_full_collision_facts"] == 7


def test_real_page_readonly_counts(tmp_path, monkeypatch):
    probe = {
        "candidate_id": "defendeu_jog_000",
        "evidence_strength": "REAL_PAGE_READONLY",
        "confirmed_domains": ["pt.wikipedia.org", "en.wikipedia.org", "rsssf.org"],
    }
    (tmp_path / "probes").mkdir()
    (tmp_path / "probes" / "defendeu_jog_000.json").write_text(
        __import__("json").dumps(probe), encoding="utf-8"
    )
    monkeypatch.setattr(DRY, "PROBES_DIR", tmp_path / "probes")
    metrics, registry = DRY.dry_run(_selection(7))
    assert metrics["evidence_real_page_readonly"] == 1
    assert metrics["domain_coverage_rsssf"] == 1
    assert registry["expected_facts"][0]["evidence_strength"] == "REAL_PAGE_READONLY"


def test_junk_object_rejected():
    assert DRY.reject_forbidden_object("CIDADE DE SANTOS") is True
    assert DRY.reject_forbidden_object("ESTADIO URBANO CALDEIRA") is True
    assert DRY.reject_forbidden_object("BAIRRO DA VILA BELMIRO") is True
    assert DRY.reject_forbidden_object("PAIS BRASIL") is True
    assert DRY.reject_forbidden_object("ESTADO DE SAO PAULO") is True
    assert DRY.reject_forbidden_object("CLAUSULA DE CONTRATO ATE 1978") is True
    assert DRY.reject_forbidden_object("GENERICO CLUBE DO CORACAO") is True
    assert DRY.reject_forbidden_object("COORDENADA 23R 46S") is True


def test_club_object_passes_filter():
    assert DRY.reject_forbidden_object("BOTAFOGO DE FUTEBOL E REGATAS") is False
    assert DRY.reject_forbidden_object("SANTOS FUTEBOL CLUBE") is False
    assert DRY.reject_forbidden_object("SÃO PAULO FUTEBOL CLUBE") is False


def test_verified_regression_detected():
    assert DRY.detect_verified_regression(20, 19) is True
    assert DRY.detect_verified_regression(20, 20) is False


def test_ready_for_worker_requires_full_gate(tmp_path, monkeypatch):
    monkeypatch.setattr(DRY, "PROBES_DIR", tmp_path / "no_probes")
    ok, _ = DRY.dry_run(_selection(7))
    assert ok["ready_for_worker"] is True
    # 5 candidatos < mínimo 6 → gate falha.
    short, _ = DRY.dry_run(_selection(5))
    assert short["ready_for_worker"] is False
    assert short["blocking_reason"] is not None


def test_predicted_totals_with_baseline():
    metrics, _ = DRY.dry_run(_selection(7))
    assert metrics["predicted_new_verified"] == 7
    assert metrics["predicted_records_total"] == 27
    assert metrics["baseline_verified"] == 20
