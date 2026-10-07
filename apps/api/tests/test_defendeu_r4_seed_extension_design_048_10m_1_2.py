"""Testes do seed extension R4 — design APLICADO com GO do Operador (2026-10-07).

Guardas: (1) o doc de design registra a aplicação; (2) o cluster aplicado
(`jairzinho_botafogo`) cumpre as regras estruturais (3 domínios/2 publishers/
não-Wiki); (3) os 5 candidatos sem 3ª fonte validada (D9) permanecem FORA.
"""
from __future__ import annotations

import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

DESIGN_PATH = API_ROOT / "reports" / "defendeu_r4_seed_extension_design_048_10m_1_2.md"
CONFIG_PATH = API_ROOT / "config" / "seed_clusters.yaml"


def _clusters():
    import yaml

    data = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    return {c["id"]: c for c in data["clusters"]}


def test_design_document_marks_applied_with_go():
    content = DESIGN_PATH.read_text(encoding="utf-8")
    assert "APLICADO" in content
    assert "GO do Operador" in content


def test_applied_cluster_meets_structural_rules():
    clusters = _clusters()
    cluster = clusters["jairzinho_botafogo"]
    domains = {s["domain"] for s in cluster["sources"]}
    publishers = {s["publisher"] for s in cluster["sources"]}
    non_wiki = {d for d in domains if "wikipedia" not in d}
    assert cluster["expected_predicate"] == "DEFENDEU"
    assert len(domains) >= 3, "quórum estrutural exige 3 domínios distintos"
    assert len(publishers) >= 2, "exige 2 publishers distintos"
    assert non_wiki, "exige ao menos 1 publisher fora da Wikimedia"


def test_pending_candidates_stay_out_until_third_source():
    """D9: sem 3ª fonte não-Wiki validada, os 5 candidatos NÃO entram no manifest."""
    clusters = _clusters()
    for cid in ("zito_santos", "carlosalbertotorres_santos", "socrates_corinthians",
                "romario_vasco", "rogerioceni_saopaulo"):
        assert cid not in clusters, f"{cid} entrou sem 3ª fonte validada (D9)"


def test_design_contains_risks_section():
    content = DESIGN_PATH.read_text(encoding="utf-8")
    for risk in ["junk:", "forbidden:", "homonímia:", "rate limit:"]:
        assert risk in content


def test_design_preconditions_require_explicit_go():
    content = DESIGN_PATH.read_text(encoding="utf-8")
    assert "GO explícito" in content or "GO explicito" in content
