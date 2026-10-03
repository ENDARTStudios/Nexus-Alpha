"""Nexus-Alpha — Wrapper de auditoria de segurança com Strix (opcional).

O Strix é um agente autônomo de pentest. Ele exige Docker em execução e uma
chave de LLM, então este wrapper é não-bloqueante: se os pré-requisitos não
estiverem presentes, ele imprime as instruções de setup e sai com código 0.

Uso:
    python scripts/security_audit.py [alvo]

``alvo`` pode ser um caminho local (padrão: raiz do projeto) ou uma URL.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TARGET = str(ROOT)

LLM_ENV_VARS = ("STRIX_LLM", "LLM_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY")


def _docker_running() -> bool:
    docker = shutil.which("docker")
    if not docker:
        return False
    try:
        result = subprocess.run(
            [docker, "info"], capture_output=True, timeout=20, text=True
        )
        return result.returncode == 0
    except Exception:
        return False


def _setup_instructions() -> str:
    return (
        "Strix indisponível. Para habilitar a auditoria autônoma:\n"
        "  1. Instale:      pip install strix-agent\n"
        "  2. Suba o Docker Desktop e confirme com `docker info`.\n"
        "  3. Exporte uma chave de LLM, ex.:\n"
        "       $env:STRIX_LLM='openai/gpt-4o-mini'; $env:LLM_API_KEY='<sua-chave>'\n"
        "  4. Rode novamente: python scripts/security_audit.py [alvo]\n"
        "Alternativa (skills para agentes): npx skills add usestrix/strix"
    )


def main() -> int:
    strix = shutil.which("strix")
    if strix is None:
        print(_setup_instructions())
        return 0

    if not _docker_running():
        print("Docker não está em execução — o Strix precisa de um sandbox Docker.")
        print(_setup_instructions())
        return 0

    if not any(os.environ.get(var) for var in LLM_ENV_VARS):
        print("Nenhuma chave de LLM detectada em %s." % ", ".join(LLM_ENV_VARS))
        print(_setup_instructions())
        return 0

    target = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TARGET
    print(f"Iniciando auditoria Strix contra: {target}")
    completed = subprocess.run([strix, "--target", target])
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
