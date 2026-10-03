"""Testes offline do diagnóstico de boot-readiness (#054.2.R1) — sem HTTP, sem .env."""
from __future__ import annotations

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "diagnose_boot_readiness",
    Path(__file__).resolve().parents[1] / "scripts" / "diagnose_054_2_r1_boot_readiness.py",
)
DIAG = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(DIAG)


def _sample(status="online", verified=20, fact=598, concept=2136, hebbian=True):
    return {
        "status": status,
        "fact_count": fact,
        "concept_count": concept,
        "verification": {"verified_facts_domain_independent": verified, "quorum": 3},
        "cognitive_health": {"hebbian_consistency_check": hebbian},
    }


def test_classify_healthy_baseline():
    assert DIAG.classify_sample(_sample()) == "healthy"


def test_classify_cold_boot_zeros():
    cold = _sample(verified=0, fact=0, concept=0, hebbian=False)
    assert DIAG.classify_sample(cold) == "cold_boot_zeros"


def test_classify_null_payload_as_cold_boot():
    """Payload sem contadores (None) + hebbian=False = cold boot (falso zero)."""
    cold = _sample(verified=None, fact=None, concept=None, hebbian=False)
    assert DIAG.classify_sample(cold) == "cold_boot_zeros"


def test_classify_offline_status_is_unknown():
    assert DIAG.classify_sample({"status": "offline"}) == "unknown"


def test_classify_degraded_is_not_cold_nor_healthy():
    degraded = _sample(verified=20, fact=598, concept=2136, hebbian=False)
    assert DIAG.classify_sample(degraded) == "degraded"


def test_budget_limits_are_the_packet_budget():
    assert DIAG.MAX_REQUESTS_TOTAL == 12
    assert DIAG.MAX_REQUESTS_PER_MINUTE == 4
    assert DIAG.DELAY_BETWEEN_REQUESTS_SECONDS == 15
    assert DIAG.MAX_RETRIES == 0


def test_no_dotenv_or_http_import_before_main():
    """D11: nenhum import de dotenv/HTTP antes de main() (lazy apenas)."""
    source = Path(DIAG.__file__).read_text(encoding="utf-8")
    body = source.split("def main()", 1)[0]
    assert "import dotenv" not in body
    assert "import urllib" not in body
    assert "import httpx" not in body


def test_summarize_confirms_boot_race():
    samples = [
        {"interpretation": "cold_boot_zeros"},
        {"interpretation": "cold_boot_zeros"},
        {"interpretation": "healthy"},
    ]
    summary = DIAG.summarize_timeline(samples)
    assert summary["conclusion"] == "BOOT_RACE_CONFIRMED"
    assert summary["stable_after_attempt"] == 3


def test_summarize_not_reproduced_when_all_healthy():
    samples = [{"interpretation": "healthy"}] * 4
    summary = DIAG.summarize_timeline(samples)
    assert summary["conclusion"] == "NOT_REPRODUCED"


def test_summarize_inconclusive_when_only_cold():
    samples = [{"interpretation": "cold_boot_zeros"}] * 3
    summary = DIAG.summarize_timeline(samples)
    assert summary["conclusion"] == "INCONCLUSIVE"


def test_timeline_entry_shape():
    payload = _sample()
    entry = DIAG.build_timeline_entry(1, payload, "2026-10-03T00:00:00Z")
    assert entry["attempt"] == 1
    assert entry["interpretation"] == "healthy"
    assert entry["quorum"] == 3
