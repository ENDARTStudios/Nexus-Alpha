"""Testes do seed extension design R4 — validação de que o design NÃO aplica mudanças."""
from __future__ import annotations

from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
DESIGN_PATH = API_ROOT / "reports" / "defendeu_r4_seed_extension_design_048_10m_1_2.md"
CONFIG_PATH = API_ROOT / "config" / "seed_clusters.yaml"


def test_design_document_exists_and_marks_not_applied():
    content = DESIGN_PATH.read_text(encoding="utf-8")
    assert "NÃO APLICADO" in content or "NÃO aplicado" in content
    assert "DESIGN ONLY" in content


def test_config_seed_clusters_untouched_by_design():
    """O design não pode ter alterado config/seed_clusters.yaml (conteúdo == HEAD)."""
    import subprocess
    root = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True
    ).stdout.strip()
    rel = CONFIG_PATH.relative_to(Path(root)).as_posix()
    current = CONFIG_PATH.read_bytes()
    head = subprocess.run(
        ["git", "show", f"HEAD:{rel}"],
        cwd=root, capture_output=True,
    )
    assert head.returncode == 0, f"seed_clusters.yaml ausente no HEAD ({rel})"
    current_lf = current.replace(b"\r\n", b"\n")
    head_lf = head.stdout.replace(b"\r\n", b"\n")
    assert current_lf == head_lf, "seed_clusters.yaml alterado pelo design!"


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
