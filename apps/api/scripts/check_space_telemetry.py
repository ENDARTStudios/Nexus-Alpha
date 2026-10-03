"""#048.10G/#048.10H.1 — CLI do preflight de telemetria do Space.

A lógica reutilizável vive em ``src/ops/space_telemetry.py`` (gate duro do worker).
Este script é apenas o wrapper de linha de comando.

Uso:
    python scripts/check_space_telemetry.py
    python scripts/check_space_telemetry.py --allow-unverified-local

Classificação: OK | BLOCKED_SPACE_STALE_TELEMETRY | BLOCKED_QUORUM_MISMATCH |
    BLOCKED_FALLBACK_PROMOTED | BLOCKED_INVALID_PREDICATES | BLOCKED_UNACCOUNTED_RAW |
    MISSING_SPACE_CREDENTIALS | MISSING_SPACE_URL
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.ops.space_telemetry import (  # noqa: E402
    check_space_telemetry,
    evaluate_payload,
)

__all__ = ["check_space_telemetry", "evaluate_payload", "main"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Preflight de telemetria do HF Space (read-only).")
    parser.add_argument("--allow-unverified-local", action="store_true", help="pula o gate (NÃO usar em produção)")
    args = parser.parse_args(argv)

    result = check_space_telemetry(allow_unverified_local=args.allow_unverified_local)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
