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


# #054.2.R2/R4 — backoff formalizado (determinístico, documentado).
WAIT_MAX_ATTEMPTS = 8
WAIT_DELAYS_SECONDS = (5, 10, 15, 20, 25, 30, 30, 30)


def classify_readiness(payload: dict) -> str:
    """R4/#054.2.R2 — classifica um payload de /api/metrics (função pura).

    COLD_BOOT: graph_ready ausente/False ou status "booting" — retry com backoff,
        nunca declarar drift cognitivo durante cold boot confirmado.
    DRIFT_REAL: graph_ready True (grafo respondendo) + verified == 0 — não é cold
        boot; escalar.
    READY: baseline íntegra (status online, verified > 0 — cobre também payloads
        legados sem graph_ready).
    INDETERMINATE: payload ilegível.
    """
    if not isinstance(payload, dict):
        return "INDETERMINATE"
    graph_ready = payload.get("graph_ready")
    if graph_ready is False or payload.get("status") == "booting":
        return "COLD_BOOT"
    verified = (payload.get("verification") or {}).get("verified_facts_domain_independent")
    if graph_ready is True:
        return "DRIFT_REAL" if verified == 0 else "READY"
    if payload.get("status") == "online":
        return "READY" if isinstance(verified, int) and verified > 0 else "INDETERMINATE"
    return "INDETERMINATE"


def wait_backoff_delays(max_attempts: int = WAIT_MAX_ATTEMPTS) -> tuple[int, ...]:
    """Sequência determinística de delays (segundos), cortada a max_attempts."""
    return WAIT_DELAYS_SECONDS[:max_attempts]


def _fetch_metrics_payload() -> dict:
    """Fetch bruto de /api/metrics para o loop ``--wait-ready``.

    Reusa ``_fetch_metrics`` de ``src.ops.space_telemetry`` (mesma URL/headers do
    gate). dotenv lazy (D11); sem URL no ambiente retorna ``{}``, que classifica
    como INDETERMINATE — nunca levanta.
    """
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
        load_dotenv(ROOT / ".env.local")
    except ImportError:
        pass
    import os

    from src.ops.space_telemetry import _fetch_metrics

    url = os.environ.get("HF_SPACE_URL") or os.environ.get("NEXUS_SPACE_URL")
    if not url:
        return {}
    _status, payload = _fetch_metrics(
        url,
        os.environ.get("HF_TOKEN", ""),
        os.environ.get("NEXUS_API_TOKEN", ""),
        30,
    )
    return payload or {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Preflight de telemetria do HF Space (read-only).")
    parser.add_argument("--allow-unverified-local", action="store_true", help="pula o gate (NÃO usar em produção)")
    parser.add_argument(
        "--wait-ready",
        action="store_true",
        help="#054.2.R2/R4 — sondar com backoff antes de declarar drift (cold boot do AuraDB não é drift)",
    )
    args = parser.parse_args(argv)

    if args.wait_ready:
        # #054.2.R2/R4 — sondas de cold boot: zeros + hebbian=False + online durante
        # o wake-up do AuraDB NÃO são drift; backoff determinístico antes de declarar.
        import time as _time

        for attempt, delay in enumerate(wait_backoff_delays(), start=1):
            payload = _fetch_metrics_payload()
            verdict = classify_readiness(payload)
            print(
                json.dumps(
                    {"attempt": attempt, "verdict": verdict, "delay_next_s": delay},
                    ensure_ascii=False,
                )
            )
            if verdict in ("READY", "DRIFT_REAL"):
                break
            if attempt < len(wait_backoff_delays()):
                _time.sleep(delay)
        return 0 if verdict == "READY" else 1

    result = check_space_telemetry(allow_unverified_local=args.allow_unverified_local)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
