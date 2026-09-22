#!/usr/bin/env python
"""CLI opt-in para preparar dataset/config e delegar treino ao LlamaFactory.

Este script não instala nem importa LlamaFactory/torch automaticamente.
"""

from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.training.config import (  # noqa: E402
    DEFAULT_BASE_MODEL,
    DEFAULT_DATASET_DIR,
    DEFAULT_DATASET_NAME,
    write_sft_config,
)
from src.training.dataset import write_dataset  # noqa: E402
from src.training.runner import TrainingDependencyMissingError, run_train  # noqa: E402


def _load_env() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
    except Exception:
        # Opt-in: se dotenv não estiver disponível, segue com variáveis já presentes.
        pass


def _load_facts_file(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Arquivo de fatos não encontrado: {path}")

    text = path.read_text(encoding="utf-8")

    if path.suffix.lower() == ".jsonl":
        facts = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        data = json.loads(text)
        if isinstance(data, dict):
            facts = data.get("facts", data.get("items", []))
        else:
            facts = data

    if not isinstance(facts, list):
        raise ValueError(
            "O arquivo de fatos deve conter uma lista JSON ou um objeto com chave 'facts'."
        )

    return [item for item in facts if isinstance(item, dict)]


async def _maybe_call(obj: Any, name: str) -> None:
    method = getattr(obj, name, None)
    if method is None:
        return

    result = method()
    if inspect.isawaitable(result):
        await result


async def _load_verified_facts_from_graph(limit: int) -> list[dict[str, Any]]:
    connector = None

    try:
        from src.database.graph_connector import GraphConnector

        connector = GraphConnector()

        await _maybe_call(connector, "connect")

        if not hasattr(connector, "export_verified_facts"):
            print(
                "[nexus-training] GraphConnector.export_verified_facts não está disponível. "
                "Aplique o patch em src/database/graph_connector.py.",
                file=sys.stderr,
            )
            return []

        facts = await connector.export_verified_facts(limit=limit)
        return facts or []

    except Exception as exc:
        print(
            f"[nexus-training] Falha ao exportar fatos verificados do grafo: {exc}",
            file=sys.stderr,
        )
        return []

    finally:
        if connector is not None:
            try:
                await _maybe_call(connector, "close")
            except Exception:
                pass


def cmd_export(args: argparse.Namespace) -> int:
    out_dir = Path(args.out_dir)

    if args.source == "file":
        if not args.file:
            print(
                "[nexus-training] --file é obrigatório quando --source=file.",
                file=sys.stderr,
            )
            return 2
        try:
            facts = _load_facts_file(Path(args.file))
        except Exception as exc:
            print(f"[nexus-training] Erro ao ler arquivo de fatos: {exc}", file=sys.stderr)
            return 2
    else:
        facts = asyncio.run(_load_verified_facts_from_graph(args.limit))

    if args.limit and len(facts) > args.limit:
        facts = facts[: args.limit]

    result = write_dataset(
        out_dir,
        facts,
        dataset_name=args.dataset_name,
    )

    if result["records"] == 0:
        print(
            "[nexus-training] Aviso: nenhum fato válido foi exportado. "
            "O dataset ficará vazio. Não baixe o quórum para inflar dados.",
            file=sys.stderr,
        )

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_config(args: argparse.Namespace) -> int:
    path = write_sft_config(
        args.output,
        base_model=args.base_model,
        dataset_name=args.dataset_name,
        dataset_dir=args.dataset_dir,
    )
    print(str(path))
    return 0


def cmd_train(args: argparse.Namespace) -> int:
    try:
        completed = run_train(args.config)
        return int(completed.returncode)
    except TrainingDependencyMissingError as exc:
        print(f"[nexus-training] {exc}", file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        print(f"[nexus-training] {exc}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        print(
            f"[nexus-training] Treino falhou com código {exc.returncode}.",
            file=sys.stderr,
        )
        return int(exc.returncode or 1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ferramentas opt-in de fine-tuning LlamaFactory para Nexus-Alpha."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    export = sub.add_parser(
        "export", help="Exporta fatos verificados para dataset Alpaca/JSONL."
    )
    export.add_argument("--source", choices=("graph", "file"), default="graph")
    export.add_argument(
        "--file",
        help="Caminho de arquivo JSON/JSONL com fatos, quando --source=file.",
    )
    export.add_argument("--out-dir", default="data/sft", help="Diretório de saída do dataset.")
    export.add_argument("--dataset-name", default=DEFAULT_DATASET_NAME)
    export.add_argument("--limit", type=int, default=100)
    export.set_defaults(func=cmd_export)

    config = sub.add_parser("config", help="Gera configuração LoRA/SFT YAML.")
    config.add_argument("--output", default="config/llamafactory/sft_lora.yaml")
    config.add_argument("--base-model", default=DEFAULT_BASE_MODEL)
    config.add_argument("--dataset-name", default=DEFAULT_DATASET_NAME)
    config.add_argument("--dataset-dir", default=DEFAULT_DATASET_DIR)
    config.set_defaults(func=cmd_config)

    train = sub.add_parser("train", help="Delega treino ao LlamaFactory, se instalado.")
    train.add_argument("--config", default="config/llamafactory/sft_lora.yaml")
    train.set_defaults(func=cmd_train)

    return parser


def main(argv: list[str] | None = None) -> int:
    _load_env()
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
