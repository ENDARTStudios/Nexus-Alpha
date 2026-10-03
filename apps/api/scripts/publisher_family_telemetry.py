"""#053.2 — Telemetria de familias de publishers (delega ao helper de runtime).

Read-only, sem cognicao. Reexporta o helper `src.ops.publisher_family` para convergir
local e runtime. Mantem retrocompatibilidade das funcoes publicas.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.ops.publisher_family import (  # noqa: E402
    FAMILY_WARNINGS,
    classify_publisher_family,
    build_publisher_family_snapshot,
)

__all__ = [
    "FAMILY_WARNINGS",
    "classify_publisher_family",
    "build_publisher_family_snapshot",
    "summarize_families",
]


def summarize_families(domains: list[str]) -> dict:
    """Compat: agrega uma lista de dominios (1 cada) e devolve o snapshot como dict."""
    counts: dict[str, int] = {}
    for d in domains:
        counts[d] = counts.get(d, 0) + 1
    snap = build_publisher_family_snapshot(counts)
    return {
        "publisher_family_count": snap.publisher_family_count,
        "effective_publisher_count": snap.effective_publisher_count,
        "publisher_family_distribution": snap.publisher_family_distribution,
        "publisher_independence_warnings": snap.publisher_independence_warnings,
    }
