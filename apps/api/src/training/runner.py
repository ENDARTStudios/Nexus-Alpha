"""Runner opt-in para treino via LlamaFactory.

Nunca importa torch ou llamafactory diretamente.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path


class TrainingDependencyMissingError(RuntimeError):
    """Erro amigável quando LlamaFactory não está disponível no ambiente."""


def llamafactory_available() -> bool:
    """Verifica se LlamaFactory está instalável/executável sem importar torch."""
    try:
        if importlib.util.find_spec("llamafactory") is not None:
            return True
    except (ImportError, ValueError):
        pass

    return shutil.which("llamafactory-cli") is not None


def run_train(
    config_path: str | Path,
    *,
    extra_args: list[str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess:
    """Executa `llamafactory-cli train <config>` ou `python -m llamafactory.cli train <config>`."""
    config = Path(config_path).expanduser().resolve()
    if not config.exists():
        raise FileNotFoundError(f"Arquivo de configuração não encontrado: {config}")

    if not llamafactory_available():
        raise TrainingDependencyMissingError(
            "LlamaFactory não está instalado neste ambiente.\n"
            "Instale em ambiente opt-in com Python 3.11–3.13 e GPU, por exemplo no Kaggle:\n"
            "  pip install -r requirements-llamafactory.txt\n"
            "Depois execute novamente:\n"
            "  python scripts/train_lora.py train"
        )

    if importlib.util.find_spec("llamafactory") is not None:
        cmd = [sys.executable, "-m", "llamafactory.cli", "train", str(config)]
    else:
        cli = shutil.which("llamafactory-cli")
        if cli is None:
            raise TrainingDependencyMissingError(
                "Comando 'llamafactory-cli' não encontrado no PATH."
            )
        cmd = [cli, "train", str(config)]

    if extra_args:
        cmd.extend(extra_args)

    return subprocess.run(cmd, check=check, text=True)
