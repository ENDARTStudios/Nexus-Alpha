"""Nexus-Alpha — Deploy do núcleo para o Hugging Face Space (Docker).

Sincroniza o código atual (app.py + src/ + config/ + requirements) para o
repositório do Space, mapeando os arquivos específicos do Space:

* ``README_HF.md``  -> ``README.md``  (frontmatter ``sdk: docker``)
* ``Dockerfile.hf`` -> ``Dockerfile`` (build do Space)

Requer variáveis de ambiente:

* ``HF_TOKEN``     — token de escrita do Hugging Face.
* ``HF_SPACE_URL`` — ex.: https://huggingface.co/spaces/<user>/<space>
  (ou ``HF_SPACE_ID`` no formato ``<user>/<space>``).

Uso (PowerShell):
    $env:HF_TOKEN="hf_..."; $env:HF_SPACE_URL="https://huggingface.co/spaces/<user>/<space>"
    python scripts/deploy_hf_space.py
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ALLOW_PATTERNS = [
    "app.py",
    "src/**",
    "config/**",
    "requirements.txt",
    "requirements-hf.txt",
]
IGNORE_PATTERNS = [
    "**/__pycache__/**",
    "**/*.pyc",
    "data/**",
    ".env",
]


def space_id_from_env() -> str:
    explicit = (os.environ.get("HF_SPACE_ID") or "").strip()
    if explicit:
        return explicit
    url = (os.environ.get("HF_SPACE_URL") or "").strip()
    match = re.search(r"huggingface\.co/spaces/([^/]+/[^/\s]+)", url)
    if match:
        return match.group(1).strip("/")
    raise SystemExit(
        "Defina HF_SPACE_ID (<user>/<space>) ou HF_SPACE_URL "
        "(https://huggingface.co/spaces/<user>/<space>)."
    )


def main() -> int:
    token = (os.environ.get("HF_TOKEN") or "").strip() or None
    try:
        from huggingface_hub import HfApi
    except ImportError:
        raise SystemExit("Instale a dependência: pip install huggingface_hub")

    repo_id = space_id_from_env()
    api = HfApi(token=token)
    try:
        identity = api.whoami().get("name")
    except Exception as exc:
        raise SystemExit(
            "Sem autenticação no Hugging Face. Defina HF_TOKEN ou faça login "
            f"(`hf auth login`). Detalhe: {exc}"
        )
    print(f"Autenticado como: {identity}")
    print(f"Enviando núcleo para o Space: {repo_id}")

    api.upload_folder(
        repo_id=repo_id,
        repo_type="space",
        folder_path=str(ROOT),
        allow_patterns=ALLOW_PATTERNS,
        ignore_patterns=IGNORE_PATTERNS,
        commit_message="Deploy: sync Nexus-Alpha core (v1.6)",
    )
    api.upload_file(
        path_or_fileobj=str(ROOT / "README_HF.md"),
        path_in_repo="README.md",
        repo_id=repo_id,
        repo_type="space",
        commit_message="Deploy: README do Space (frontmatter docker)",
    )
    api.upload_file(
        path_or_fileobj=str(ROOT / "Dockerfile.hf"),
        path_in_repo="Dockerfile",
        repo_id=repo_id,
        repo_type="space",
        commit_message="Deploy: Dockerfile do Space (runtime lite)",
    )
    print("OK — Space atualizado. Aguarde o rebuild e valide GET /health (deve retornar 200).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
