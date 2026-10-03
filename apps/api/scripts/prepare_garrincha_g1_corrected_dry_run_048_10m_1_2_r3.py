"""Fase C do #048.10M.1.2.R3 — dry-run corrigido R3 (read_only_planning).

Reutiliza a lógica pura ``build_corrected_dry_run`` do R2 (mesma semântica D5)
sobre o estado do grafo R3 e o probe cirúrgico R3.

Regras fundamentais do task:
- domains_only_in_local_reports nunca conta como minerado;
- domains_blocked_or_unavailable nunca conta como minerado;
- domains_prohibited nunca conta como minerado;
- somente domains_to_be_mined_in_future_g1 confirmado por probe gera previsão.

Saída: reports/garrincha_g1_corrected_dry_run_048_10m_1_2_r3.json
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.prepare_garrincha_g1_corrected_dry_run_048_10m_1_2_r2 import (  # noqa: E402
    build_corrected_dry_run,
)

GRAPH_STATE_PATH = Path("reports/garrincha_g1_graph_state_048_10m_1_2_r3.json")
PROBE_PATH = Path("reports/garrincha_g1_surgical_probe_048_10m_1_2_r3.json")
OUT_PATH = Path("reports/garrincha_g1_corrected_dry_run_048_10m_1_2_r3.json")

SEED_RSSSF_URLS = [
    "https://www.rsssfbrasil.com/sel/jogclub.htm",
    "https://www.rsssf.org/tablesb/brazchamp.html",
    "https://www.rsssf.org/sacups/copalib.html",
]


def main() -> int:
    graph_state = json.loads(GRAPH_STATE_PATH.read_text(encoding="utf-8"))
    probe = json.loads(PROBE_PATH.read_text(encoding="utf-8"))

    # converte results do probe cirúrgico R3 para o formato de summary do R2
    probe_summary = {
        "probes": [
            {
                "domain": r.get("domain"),
                "url": r.get("url"),
                "http_status": r.get("http_status"),
                "mentions_garrincha": r.get("mentions_garrincha", False),
                "mentions_botafogo": r.get("mentions_botafogo", False),
                "mentions_defendeu_context": r.get("mentions_defendeu_context", False),
            }
            for r in probe.get("results", [])
        ]
    }

    out = build_corrected_dry_run(
        {
            "confirmed_domains": graph_state.get("confirmed_domains", []),
            "distinct_domain_count": graph_state.get("distinct_domain_count", 0),
            "canonical_fact_found": graph_state.get("canonical_fact_found", False),
            "same_triple_confirmation": graph_state.get("same_triple_confirmation", False),
            "span_broken": graph_state.get("span_broken", False),
            "junk_object": graph_state.get("junk_object", False),
            "forbidden_object": graph_state.get("forbidden_object", False),
            "homonymy_risk": graph_state.get("homonymy_risk", "low"),
        },
        [probe_summary],
        SEED_RSSSF_URLS,
    )
    out["audit_id"] = "garrincha_g1_corrected_dry_run_048_10m_1_2_r3"
    out["generated_at"] = datetime.now(timezone.utc).isoformat()
    out["mode"] = "read_only_planning"
    out["probe_r3_confirmed_non_wikimedia_domain"] = probe.get("confirmed_non_wikimedia_domain")
    out["probe_r3_urls_status"] = [
        {"url": r["url"], "http_status": r["http_status"]} for r in probe.get("results", [])
    ]
    # semântica R3: os 3 caminhos estavam CORRETOS e vivos (200 OK) — as páginas
    # simplesmente não mencionam Garrincha/Manuel Francisco. O bloqueio não é
    # de caminho (como no R2) nem de política: é ausência do jogador nas fontes
    # tabulares permitidas atualmente alcançáveis.
    if not out["ready_for_future_g1"]:
        out["blocking_reason"] = (
            "nenhum dos 3 caminhos corretos (jogclub/brazchamp/copalib — todos 200 OK) "
            "menciona Garrincha/Manuel Francisco dos Santos: o jogador está ausente das "
            "fontes tabulares permitidas atualmente alcançáveis; extensão governada de "
            "seeds (D8) ou outra fonte permitida seria necessária — decisão do Operador"
        )
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"ok → {OUT_PATH} · ready_for_future_g1={out['ready_for_future_g1']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
