"""#048.10H.1 — Telemetria do Space: gate reutilizável (read-only).

Define o contrato de telemetria obrigatória e o preflight que bloqueia o worker
quando o Space está stale/divergente. Nunca escreve em Neo4j/Qdrant.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any

USER_AGENT = "Nexus-Alpha/1.0 (preflight telemetry check)"
EXPECTED_QUORUM = 3
ONLINE_STATUSES = {"online", "ok", "success"}

SAFE_OBSERVED_KEYS = (
    "status",
    "concept_count",
    "fact_count",
    "verified_facts_domain_independent",
)


@dataclass
class TelemetryCheckResult:
    ok: bool
    reason: str | None = None
    missing_fields: list[str] = field(default_factory=list)
    observed: dict[str, Any] = field(default_factory=dict)
    http_status: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _observed(payload: dict) -> dict[str, Any]:
    acc = payload.get("ingestion_accounting") or {}
    ver = payload.get("verification") or {}
    fb = payload.get("fallback_health") or {}
    eq = payload.get("extraction_quality") or {}
    return {
        "status": payload.get("status"),
        "concept_count": payload.get("concept_count"),
        "fact_count": payload.get("fact_count"),
        "verified_facts_domain_independent": ver.get("verified_facts_domain_independent"),
        "quorum": ver.get("quorum"),
        "run_scoped_gap": acc.get("run_scoped_gap"),
        "graph_scoped_gap": acc.get("graph_scoped_gap"),
        "unaccounted_raw": acc.get("unaccounted_raw"),
        "duplicate_cross_domain": acc.get("duplicate_cross_domain"),
        "fallback_promoted_to_graph": fb.get("fallback_promoted_to_graph"),
        "top_invalid_predicates": eq.get("top_invalid_predicates"),
    }


def evaluate_payload(payload: Any, http_status: int | None = None) -> TelemetryCheckResult:
    """Gate puro sobre um payload de ``/api/metrics``. Não faz rede."""
    if not isinstance(payload, dict):
        return TelemetryCheckResult(False, "BLOCKED_SPACE_STALE_TELEMETRY", ["<payload>"], {}, http_status)

    missing: list[str] = []
    if not isinstance(payload.get("concept_count"), int):
        missing.append("concept_count")
    if not isinstance(payload.get("fact_count"), int):
        missing.append("fact_count")

    accounting = payload.get("ingestion_accounting")
    if not isinstance(accounting, dict):
        missing.append("ingestion_accounting")
        accounting = {}
    for key in ("run_scoped_gap", "graph_scoped_gap", "unaccounted_raw"):
        if key not in accounting:
            missing.append(f"ingestion_accounting.{key}")

    verification = payload.get("verification")
    if not isinstance(verification, dict) or "quorum" not in verification:
        missing.append("verification.quorum")
    fallback = payload.get("fallback_health")
    if not isinstance(fallback, dict) or "fallback_promoted_to_graph" not in fallback:
        missing.append("fallback_health.fallback_promoted_to_graph")
    quality = payload.get("extraction_quality")
    if not isinstance(quality, dict) or "top_invalid_predicates" not in quality:
        missing.append("extraction_quality.top_invalid_predicates")

    status = payload.get("status")
    if status is not None and str(status).lower() not in ONLINE_STATUSES:
        missing.append("status!=online")

    observed = _observed(payload)
    if missing:
        return TelemetryCheckResult(False, "BLOCKED_SPACE_STALE_TELEMETRY", missing, observed, http_status)
    if verification.get("quorum") != EXPECTED_QUORUM:
        return TelemetryCheckResult(False, "BLOCKED_QUORUM_MISMATCH", ["verification.quorum!=3"], observed, http_status)
    if fallback.get("fallback_promoted_to_graph") != 0:
        return TelemetryCheckResult(
            False, "BLOCKED_FALLBACK_PROMOTED", ["fallback_health.fallback_promoted_to_graph!=0"], observed, http_status
        )
    if quality.get("top_invalid_predicates") != []:
        return TelemetryCheckResult(
            False, "BLOCKED_INVALID_PREDICATES", ["extraction_quality.top_invalid_predicates!=[]"], observed, http_status
        )
    if accounting.get("unaccounted_raw") != 0:
        return TelemetryCheckResult(
            False, "BLOCKED_UNACCOUNTED_RAW", ["ingestion_accounting.unaccounted_raw!=0"], observed, http_status
        )
    return TelemetryCheckResult(True, None, [], observed, http_status)


def _env_allow_unverified() -> bool:
    return os.environ.get("NEXUS_ALLOW_UNVERIFIED_LOCAL", "").strip().lower() in {"1", "true", "yes", "on"}


def _fetch_metrics(url: str, hf_token: str, nexus_token: str, timeout: int) -> tuple[int | None, dict | None]:
    headers = {"User-Agent": USER_AGENT, "Authorization": f"Bearer {hf_token}", "X-Nexus-Token": nexus_token}
    request = urllib.request.Request(url.rstrip("/") + "/api/metrics", headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (URL do Operador)
            body = response.read().decode("utf-8", errors="replace")
            return response.status, json.loads(body)
    except Exception:
        return None, None


def check_space_telemetry(
    space_url: str | None = None,
    hf_token: str | None = None,
    nexus_token: str | None = None,
    timeout: int = 30,
    retries: int = 3,
    delay: int = 5,
    allow_unverified_local: bool = False,
) -> TelemetryCheckResult:
    """Preflight com no máximo ``retries`` tentativas. Sem burst, sem retry de UA."""
    if allow_unverified_local or _env_allow_unverified():
        return TelemetryCheckResult(True, "ALLOW_UNVERIFIED_LOCAL", [], {}, None)

    url = space_url or os.environ.get("HF_SPACE_URL") or os.environ.get("NEXUS_SPACE_URL")
    token = hf_token if hf_token is not None else os.environ.get("HF_TOKEN")
    nexus = nexus_token if nexus_token is not None else os.environ.get("NEXUS_API_TOKEN")

    if not url:
        return TelemetryCheckResult(False, "MISSING_SPACE_URL", ["HF_SPACE_URL"], {}, None)
    if not token or not nexus:
        return TelemetryCheckResult(False, "MISSING_SPACE_CREDENTIALS", ["HF_TOKEN", "NEXUS_API_TOKEN"], {}, None)

    attempts = max(1, int(retries))
    last = TelemetryCheckResult(False, "BLOCKED_SPACE_STALE_TELEMETRY", ["<unreachable>"], {}, None)
    for attempt in range(1, attempts + 1):
        status, payload = _fetch_metrics(url, token, nexus, timeout)
        if payload is not None:
            result = evaluate_payload(payload, status)
            if result.ok:
                return result
            last = result
        if attempt < attempts:
            time.sleep(delay)
    return last
