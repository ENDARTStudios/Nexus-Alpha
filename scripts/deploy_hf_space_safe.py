"""#052.5 — Deploy allowlisted do HF Space (dry-run por padrão, scan anti-leak).

O repo do Space é um snapshot de deploy (histórico próprio); o caminho correto é
UPLOAD de um subconjunto runtime, não `git push`. Este helper:

* monta um manifest (path/size/sha256) de uma allowlist estrita;
* varre segredos suspeitos antes de subir;
* só faz upload com `--execute`;
* nunca imprime/embute token; não toca em Neo4j/Qdrant; não roda worker.

Uso:
    python scripts/deploy_hf_space_safe.py --dry-run
    python scripts/deploy_hf_space_safe.py --execute
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from fnmatch import fnmatch
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / ".autonomous" / "deploy"

# Allowlist runtime (espelha Dockerfile.hf: app.py + src/ + config/ + requirements).
ALLOW_PATTERNS = [
    "app.py",
    "requirements.txt",
    "requirements-hf.txt",
    "src/**",
    "config/**",
]
# Arquivos extras mapeados no repo do Space (origem -> destino).
EXTRA_FILES = {"README_HF.md": "README.md", "Dockerfile.hf": "Dockerfile"}

EXCLUDE_PATTERNS = [
    ".env", ".env.*", ".autonomous/**", "reports/**", ".venv/**", "node_modules/**",
    "__pycache__/**", "**/__pycache__/**", "*.pyc", ".git/**", "*.log", "*.sqlite",
    "database/**", "space_backup/**", "deploy_venv/**", ".pytest_cache/**", "*.bak",
]

SECRET_PATTERNS = {
    "hf_token": re.compile(r"hf_[A-Za-z0-9]{20,}"),
    "neo4j_uri_with_password": re.compile(r"neo4j\+?s?://[^\s\"']+:[^\s\"'@]+@"),
    "qdrant_api_key": re.compile(r"QDRANT_API_KEY\s*=\s*\S{8,}"),
    "password_assignment": re.compile(r"(?i)password\s*=\s*[\"'][^\"']{6,}[\"']"),
    "bearer_token": re.compile(r"(?i)bearer\s+[A-Za-z0-9._-]{20,}"),
    "x_nexus_token": re.compile(r"X-Nexus-Token\s*[:=]\s*\S{8,}"),
}

TEXT_SUFFIXES = {".py", ".txt", ".json", ".yaml", ".yml", ".md", ".cfg", ".ini", ".toml", ".sh"}
MAX_SCAN_BYTES = 512_000


def _rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def is_excluded(relpath: str) -> bool:
    return any(fnmatch(relpath, pat) for pat in EXCLUDE_PATTERNS)


def is_allowed(relpath: str) -> bool:
    if is_excluded(relpath):
        return False
    return any(fnmatch(relpath, pat) or relpath == pat.rstrip("/") for pat in ALLOW_PATTERNS)


def build_manifest(root: Path) -> list[dict]:
    entries: list[dict] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = _rel(path, root)
        if not is_allowed(rel):
            continue
        data = path.read_bytes()
        entries.append({
            "path": rel,
            "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    return entries


def scan_secrets(root: Path, entries: list[dict]) -> list[dict]:
    findings: list[dict] = []
    for entry in entries:
        path = root / entry["path"]
        if path.suffix.lower() not in TEXT_SUFFIXES or entry["size"] > MAX_SCAN_BYTES:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for name, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                findings.append({"path": entry["path"], "pattern": name})
    return findings


def derive_space_id() -> str | None:
    explicit = (os.environ.get("HF_SPACE_ID") or "").strip()
    if explicit:
        return explicit
    url = (os.environ.get("HF_SPACE_URL") or os.environ.get("NEXUS_SPACE_URL") or "").strip()
    m = re.search(r"huggingface\.co/spaces/([^/]+/[^/\s]+)", url)
    if m:
        return m.group(1).strip("/")
    m = re.match(r"https?://([^.]+)\.hf\.space", url)
    if m and "-" in m.group(1):
        ns, name = m.group(1).split("-", 1)
        return f"{ns}/{name}"
    return None


def _write(name: str, payload: dict) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / name
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deploy allowlisted do HF Space (dry-run por padrão).")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="somente manifest + scan (default)")
    mode.add_argument("--execute", action="store_true", help="executa o upload allowlisted")
    args = parser.parse_args(argv)

    manifest = build_manifest(ROOT)
    findings = scan_secrets(ROOT, manifest)
    total_bytes = sum(e["size"] for e in manifest)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "execute" if args.execute else "dry-run",
        "files": manifest,
        "files_count": len(manifest),
        "total_bytes": total_bytes,
        "secret_findings": findings,
        "secret_scan_ok": not findings,
        "space_id_derived": bool(derive_space_id()),
        "token_present": bool(os.environ.get("HF_TOKEN")),
    }
    _write("manifest.json", {"files": manifest, "files_count": len(manifest), "total_bytes": total_bytes})

    if findings:
        report["status"] = "SECRET_SCAN_FAILED"
        _write("dry_run_report.json", report)
        print(json.dumps({"status": "SECRET_SCAN_FAILED", "secret_findings": findings}, ensure_ascii=False, indent=2))
        return 2

    if not args.execute:
        report["status"] = "DRY_RUN_OK"
        _write("dry_run_report.json", report)
        print(json.dumps({
            "status": "DRY_RUN_OK",
            "files_count": len(manifest),
            "total_bytes": total_bytes,
            "space_id_derived": report["space_id_derived"],
            "token_present": report["token_present"],
        }, ensure_ascii=False, indent=2))
        return 0

    space_id = derive_space_id()
    if not space_id:
        print(json.dumps({"status": "MISSING_SPACE_ID"}))
        return 3
    if not os.environ.get("HF_TOKEN"):
        print(json.dumps({"status": "MISSING_HF_TOKEN"}))
        return 3
    try:
        from huggingface_hub import HfApi
    except Exception:
        print(json.dumps({"status": "HUGGINGFACE_HUB_IMPORT_FAILED"}))
        return 3

    api = HfApi(token=os.environ["HF_TOKEN"])
    try:
        api.upload_folder(
            repo_id=space_id,
            repo_type="space",
            folder_path=str(ROOT),
            allow_patterns=ALLOW_PATTERNS,
            ignore_patterns=EXCLUDE_PATTERNS,
        )
        for src, dst in EXTRA_FILES.items():
            local = ROOT / src
            if local.exists():
                api.upload_file(path_or_fileobj=str(local), path_in_repo=dst, repo_id=space_id, repo_type="space")
    except Exception as exc:
        report["status"] = "UPLOAD_FAILED"
        report["error_type"] = type(exc).__name__
        _write("upload_report.json", report)
        print(json.dumps({"status": "UPLOAD_FAILED", "error_type": type(exc).__name__}, ensure_ascii=False))
        return 4

    report["status"] = "UPLOAD_OK"
    report["space_id"] = space_id
    _write("upload_report.json", report)
    print(json.dumps({"status": "UPLOAD_OK", "space_id": space_id, "files_count": len(manifest)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
