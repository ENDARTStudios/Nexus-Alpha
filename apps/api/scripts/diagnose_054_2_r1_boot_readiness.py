"""Diagnóstico read-only do boot-race do Space (#054.2.R1).

Amostra ``/api/metrics`` do próprio Space (orçamento ≤ 12 req, ≤ 4/min, sem
burst) e classifica cada amostra para evidenciar o boot-race:

- ``cold_boot_zeros``: status online + contadores zerados + hebbian=False
  (grafo inalcançável/pausado — o Space atende antes do Neo4j estar pronto);
- ``healthy``: baseline íntegra;
- ``degraded``: demais combinações.

Funções puras (``classify_sample``, ``summarize_timeline``) são offline-testáveis;
``main()`` é o único caminho com HTTP e carrega env de forma lazy (D11).
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

MAX_REQUESTS_TOTAL = 12
MAX_REQUESTS_PER_MINUTE = 4
TIMEOUT_SECONDS = 30
DELAY_BETWEEN_REQUESTS_SECONDS = 15
MAX_RETRIES = 0


def classify_sample(payload: dict) -> str:
    """Classifica uma amostra de /api/metrics (função pura)."""
    if payload.get("status") != "online":
        return "unknown"
    _ia = payload.get("ingestion_accounting") or {}
    v = payload.get("verification") or {}
    ch = payload.get("cognitive_health") or {}
    verified = v.get("verified_facts_domain_independent")
    fact_count = payload.get("fact_count")
    concept_count = payload.get("concept_count")
    hebbian = ch.get("hebbian_consistency_check")
    zeroed = (verified == 0 and fact_count == 0 and concept_count == 0) or (
        verified is None and fact_count is None and concept_count is None
    )
    if zeroed and hebbian is False:
        return "cold_boot_zeros"
    # Baseline aceita (pós-worker #048.10M.1.2): verified=20, fact=598, concept=2136.
    # Piso >= aceita crescimento estrutural (não-regressão), sem exigir igualdade exata.
    if (
        isinstance(verified, int) and verified >= 20
        and isinstance(fact_count, int) and fact_count >= 598
        and isinstance(concept_count, int) and concept_count >= 2023
        and hebbian is True
    ):
        return "healthy"
    return "degraded"


def summarize_timeline(samples: list[dict]) -> dict:
    """Resume a timeline de amostras (função pura)."""
    classifications = [s.get("interpretation") for s in samples]
    had_cold = "cold_boot_zeros" in classifications
    had_healthy = "healthy" in classifications
    if had_cold and had_healthy:
        stable_after = None
        for idx, s in enumerate(samples, start=1):
            if s.get("interpretation") == "healthy":
                stable_after = idx
                break
        conclusion = "BOOT_RACE_CONFIRMED"
    elif had_cold:
        conclusion = "INCONCLUSIVE"
        stable_after = None
    elif had_healthy:
        conclusion = "NOT_REPRODUCED"
        stable_after = 1
    else:
        conclusion = "INCONCLUSIVE"
        stable_after = None
    return {
        "samples": len(samples),
        "had_cold_boot_zeros": had_cold,
        "had_healthy": had_healthy,
        "stable_after_attempt": stable_after,
        "conclusion": conclusion,
    }


def build_timeline_entry(attempt: int, payload: dict, fetched_at: str) -> dict:
    """Monta a entrada de timeline a partir de um payload (função pura)."""
    ia = payload.get("ingestion_accounting") or {}
    v = payload.get("verification") or {}
    ch = payload.get("cognitive_health") or {}
    return {
        "attempt": attempt,
        "timestamp": fetched_at,
        "http_status": 200,
        "status": payload.get("status"),
        "verified_facts_domain_independent": v.get("verified_facts_domain_independent"),
        "fact_count": payload.get("fact_count"),
        "concept_count": payload.get("concept_count"),
        "quorum": v.get("quorum"),
        "graph_scoped_gap": ia.get("graph_scoped_gap"),
        "fact_accounting_status": ia.get("fact_accounting_status"),
        "hebbian_consistency_check": ch.get("hebbian_consistency_check"),
        "interpretation": classify_sample(payload),
    }


def main() -> int:
    import urllib.request

    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    space_url = os.environ.get("HF_SPACE_URL") or os.environ.get("NEXUS_SPACE_URL") or ""
    hf_token = os.environ.get("HF_TOKEN", "")
    nexus_token = os.environ.get("NEXUS_API_TOKEN", "")
    if not space_url:
        print("HF_SPACE_URL/NEXUS_SPACE_URL ausentes — nada a fazer.", file=sys.stderr)
        return 2

    out_path = Path(".autonomous/054_2_r1/metrics_timeline.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    samples: list[dict] = []
    for attempt in range(1, MAX_REQUESTS_TOTAL + 1):
        fetched_at = datetime.now(timezone.utc).isoformat()
        request = urllib.request.Request(
            f"{space_url}/api/metrics",
            headers={
                "Authorization": f"Bearer {hf_token}",
                "X-Nexus-Token": nexus_token,
            },
        )
        payload: dict = {}
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                _http_status = response.status
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # leitura apenas; falha vira amostra inconclusiva
            samples.append({
                "attempt": attempt,
                "timestamp": fetched_at,
                "http_status": None,
                "error": type(exc).__name__,
                "interpretation": "unknown",
            })
        else:
            samples.append(build_timeline_entry(attempt, payload, fetched_at))
        if attempt < MAX_REQUESTS_TOTAL:
            time.sleep(DELAY_BETWEEN_REQUESTS_SECONDS)

    summary = summarize_timeline(
        [s for s in samples if s.get("interpretation") != "unknown"] or samples
    )
    out = {
        "audit_id": "054_2_r1_metrics_timeline",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "read_only",
        "requests_used": len(samples),
        "max_requests_total": MAX_REQUESTS_TOTAL,
        "samples": samples,
        "stable_after_attempts": summary.get("stable_after_attempt"),
        "conclusion": summary.get("conclusion"),
    }
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"conclusion": out["conclusion"], "samples": out["requests_used"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
