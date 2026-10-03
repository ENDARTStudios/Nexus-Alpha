"""Testes do seed extension design R4 — validação de que o design NÃO aplica mudanças."""
from __future__ import annotations

from pathlib import Path

DESIGN_PATH = Path("reports/defendeu_r4_seed_extension_design_048_10m_1_2.md")
CONFIG_PATH = Path("config/seed_clusters.yaml")


def test_design_document_exists_and_marks_not_applied():
    content = DESIGN_PATH.read_text(encoding="utf-8")
    assert "NÃO APLICADO" in content or "NÃO aplicado" in content
    assert "DESIGN ONLY" in content


def test_config_seed_clusters_untouched_by_design():
    """O design não pode ter alterado config/seed_clusters.yaml (compara com HEAD)."""
    import subprocess
    diff = subprocess.run(
        ["git", "diff", "HEAD", "--", "config/seed_clusters.yaml"],
        capture_output=True, text=True,
    )
    assert diff.stdout.strip() == "", "seed_clusters.yaml foi alterado pelo design!"
    assert diff.returncode in (0, 1)


def test_design_contains_risks_section():
    content = DESIGN_PATH.read_text(encoding="utf-8")
    for risk in ["junk:", "forbidden:", "homonímia:", "rate limit:"]:
        assert risk in content


def test_design_preconditions_require_explicit_go():
    content = DESIGN_PATH.read_text(encoding="utf-8")
    assert "GO explícito" in content or "GO explicito" in content


def test_design_does_not_rename_or_remove_existing_clusters():
    content = DESIGN_PATH.read_text(encoding="utf-8")
    assert "remover cluster" not in content.lower()
    assert "deletar" not in content.lower()
