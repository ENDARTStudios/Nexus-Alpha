"""#048.10G — preflight read-only: o Space está no build com a telemetria esperada?

Impede que um worker futuro rode sobre telemetria stale. NÃO é executado como worker
por si só; apenas valida um payload de ``/api/metrics``.

Uso:
    python scripts/check_space_telemetry.py            # lê HF_SPACE_URL/NEXUS_SPACE_URL
Classificação de retorno: OK | BLOCKED_SPACE_STALE_TELEMETRY
"""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

USER_AGENT = "Nexus-Alpha/1.0 (preflight telemetry check)"


def check_space_telemetry(payload: Any) -> dict:
    if not isinstance(payload, dict):
        return {"ok": False, "missing": ["<payload>"], "classification": "BLOCKED_SPACE_STALE_TELEMETRY"}

    missing: list[str] = []
    for key in ("concept_count", "fact_count"):
        if key not in payload:
            missing.append(key)

    accounting = payload.get("ingestion_accounting") or {}
    for key in ("run_scoped_gap", "graph_scoped_gap"):
        if key not in accounting:
            missing.append(f"ingestion_accounting.{key}")

    if (payload.get("verification") or {}).get("quorum") != 3:
        missing.append("verification.quorum!=3")
    if (payload.get("fallback_health") or {}).get("fallback_promoted_to_graph") != 0:
        missing.append("fallback_health.fallback_promoted_to_graph!=0")
    if (payload.get("extraction_quality") or {}).get("top_invalid_predicates") != []:
        missing.append("extraction_quality.top_invalid_predicates!=[]")

    ok = not missing
    return {"ok": ok, "missing": missing, "classification": "OK" if ok else "BLOCKED_SPACE_STALE_TELEMETRY"}


def fetch_metrics(url: str, token: str | None, nexus_token: str | None) -> dict:
    headers = {"User-Agent": USER_AGENT}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if nexus_token:
        headers["X-Nexus-Token"] = nexus_token
    request = urllib.request.Request(url.rstrip("/") + "/api/metrics", headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 (URL do Operador)
        return json.loads(response.read().decode("utf-8", errors="replace"))


def main() -> int:
    base = os.environ.get("HF_SPACE_URL") or os.environ.get("NEXUS_SPACE_URL")
    if not base:
        print(json.dumps({"ok": False, "missing": ["HF_SPACE_URL"], "classification": "BLOCKED_SPACE_STALE_TELEMETRY"}))
        return 0
    try:
        payload = fetch_metrics(base, os.environ.get("HF_TOKEN"), os.environ.get("NEXUS_API_TOKEN"))
    except Exception as exc:
        print(json.dumps({"ok": False, "missing": [type(exc).__name__], "classification": "BLOCKED_SPACE_STALE_TELEMETRY"}))
        return 0
    result = check_space_telemetry(payload)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
