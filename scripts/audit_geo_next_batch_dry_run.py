"""#052.4 — Dry-run OFFLINE do next batch GEO (#048.10K), sem rede e sem worker.

Le o atlas #048.10K e o next batch registry e resume a elegibilidade para #048.10L.
Gera ``reports/geo_next_batch_dry_run_052_4.json``.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ATLAS = ROOT / "reports" / "geo_expansion_atlas_048_10k.json"
REGISTRY = ROOT / "reports" / "geo_expected_facts_next_batch_048_10k.json"
OUT = ROOT / "reports" / "geo_next_batch_dry_run_052_4.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def main() -> int:
    atlas = _load(ATLAS)
    registry = _load(REGISTRY)
    summary = atlas.get("summary") or {}

    expected = registry.get("expected_facts") or []
    full = int(summary.get("full_collision_facts", 0))
    junk = int(summary.get("junk_objects_detected", 0))
    forbidden = int(summary.get("forbidden_objects_detected", 0))

    report = {
        "audit_id": "geo_next_batch_dry_run_052_4",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "offline": True,
        "source_atlas": str(ATLAS.relative_to(ROOT)),
        "source_registry": str(REGISTRY.relative_to(ROOT)),
        "next_batch_expected_facts": len(expected),
        "next_batch_full_collision_facts": full,
        "next_batch_junk_objects": junk,
        "next_batch_forbidden_objects": forbidden,
        "next_batch_predicted_new_verified": int(summary.get("predicted_new_verified_if_runtime_implemented", 0)),
        "next_batch_eligible_for_runtime": bool(full >= 4 and junk == 0 and forbidden == 0),
        "note": "Dry-run offline; o worker real depende do #048.10H e do Space no HEAD.",
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("WROTE", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
