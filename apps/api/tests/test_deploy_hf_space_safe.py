"""#052.5 — testes do deploy allowlisted do HF Space (sem rede)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.deploy_hf_space_safe import (  # noqa: E402
    build_manifest,
    is_allowed,
    is_excluded,
    scan_secrets,
)

SECRET = "hf_" + "A" * 30


def _make_tree(tmp: Path) -> Path:
    (tmp / "src" / "cognition").mkdir(parents=True)
    (tmp / "config").mkdir()
    (tmp / ".autonomous" / "deploy").mkdir(parents=True)
    (tmp / "reports").mkdir()
    (tmp / "node_modules").mkdir()
    (tmp / ".venv").mkdir()
    (tmp / "__pycache__").mkdir()
    (tmp / ".git").mkdir()
    (tmp / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp / "requirements.txt").write_text("fastapi\n", encoding="utf-8")
    (tmp / "requirements-hf.txt").write_text("fastapi\n", encoding="utf-8")
    (tmp / "src" / "cognition" / "geo_extractor.py").write_text("x = 1\n", encoding="utf-8")
    (tmp / "config" / "security_policies.json").write_text("{}\n", encoding="utf-8")
    (tmp / ".env").write_text("HF_TOKEN=secret\n", encoding="utf-8")
    (tmp / ".autonomous" / "deploy" / "manifest.json").write_text("{}\n", encoding="utf-8")
    (tmp / "reports" / "r.json").write_text("{}\n", encoding="utf-8")
    (tmp / "node_modules" / "x.js").write_text("x\n", encoding="utf-8")
    (tmp / ".venv" / "pyvenv.cfg").write_text("x\n", encoding="utf-8")
    (tmp / "__pycache__" / "a.pyc").write_text("x\n", encoding="utf-8")
    (tmp / ".git" / "config").write_text("x\n", encoding="utf-8")
    return tmp


def test_allowlist_includes_runtime(tmp_path):
    _make_tree(tmp_path)
    paths = {e["path"] for e in build_manifest(tmp_path)}
    assert "app.py" in paths
    assert "requirements.txt" in paths
    assert "requirements-hf.txt" in paths
    assert "src/cognition/geo_extractor.py" in paths
    assert "config/security_policies.json" in paths


def test_excludes_dangerous_paths(tmp_path):
    _make_tree(tmp_path)
    paths = {e["path"] for e in build_manifest(tmp_path)}
    for forbidden in (".env", "reports/r.json", "node_modules/x.js", ".venv/pyvenv.cfg", "__pycache__/a.pyc", ".git/config", ".autonomous/deploy/manifest.json"):
        assert forbidden not in paths, forbidden


def test_is_allowed_and_excluded():
    assert is_allowed("app.py")
    assert is_allowed("src/x.py")
    assert not is_allowed(".env")
    assert not is_allowed("reports/x.json")
    assert is_excluded("node_modules/x.js")
    assert is_excluded(".autonomous/deploy/manifest.json")


def test_manifest_has_path_size_sha256(tmp_path):
    _make_tree(tmp_path)
    entry = next(e for e in build_manifest(tmp_path) if e["path"] == "app.py")
    assert entry["size"] > 0
    assert len(entry["sha256"]) == 64


def test_secret_scan_detects_fake_token(tmp_path):
    _make_tree(tmp_path)
    (tmp_path / "app.py").write_text(f'TOKEN = "{SECRET}"\n', encoding="utf-8")
    findings = scan_secrets(tmp_path, build_manifest(tmp_path))
    assert any(f["path"] == "app.py" for f in findings)


def test_secret_scan_clean_tree(tmp_path):
    _make_tree(tmp_path)
    assert scan_secrets(tmp_path, build_manifest(tmp_path)) == []


def test_dry_run_does_not_require_huggingface_hub(tmp_path, monkeypatch):
    _make_tree(tmp_path)
    import scripts.deploy_hf_space_safe as mod

    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path / ".autonomous" / "deploy")
    code = mod.main(["--dry-run"])
    assert code == 0


def test_execute_without_space_id_fails(tmp_path, monkeypatch):
    _make_tree(tmp_path)
    import scripts.deploy_hf_space_safe as mod

    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path / ".autonomous" / "deploy")
    monkeypatch.delenv("HF_SPACE_ID", raising=False)
    monkeypatch.delenv("HF_SPACE_URL", raising=False)
    monkeypatch.delenv("NEXUS_SPACE_URL", raising=False)
    assert mod.main(["--execute"]) == 3
