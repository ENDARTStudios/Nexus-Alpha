"""#054.2.R3 — regressão do bug de produção do ``--wait-ready``.

O loop ``--wait-ready`` da R2 chamava ``_fetch_metrics_payload``, que nunca foi
definida no wrapper (NameError em produção; T1-T6 cobriam só funções puras).
Este teste trava o gap: a função existe, nunca levanta e degrada para
INDETERMINATE quando não há URL/credenciais no ambiente.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.check_space_telemetry import _fetch_metrics_payload, classify_readiness


def test_fetch_payload_without_env_never_raises(monkeypatch):
    for var in ("HF_SPACE_URL", "NEXUS_SPACE_URL"):
        monkeypatch.delenv(var, raising=False)
    # isola o .env local (o dotenv lazy da função repõe as vars deletadas)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: None)
    assert _fetch_metrics_payload() == {}


def test_empty_payload_classifies_indeterminate():
    assert classify_readiness({}) == "INDETERMINATE"
    assert classify_readiness(None) == "INDETERMINATE"
