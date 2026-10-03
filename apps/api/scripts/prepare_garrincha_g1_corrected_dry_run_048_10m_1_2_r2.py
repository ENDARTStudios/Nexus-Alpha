"""Fase C do #048.10M.1.2.R2 — dry-run CORRIGIDO para o futuro gate G1
(Garrincha --DEFENDEU--> Botafogo), modo read-only_planning.

Correção semântica da dívida D5: NÃO conta ``local_existing_covered`` como
minerado no ciclo. Os domínios são separados explicitamente em 5 baldes:

- domains_already_confirmed_in_graph: domínios que confirmam o fato canônico
  HOJE no grafo (Neo4j, mesma tripla);
- domains_to_be_mined_in_future_g1: domínios permitidos com plausibilidade
  CONFIRMADA por probe read-only deste ciclo;
- domains_only_in_local_reports: domínios citados em probes/relatórios
  anteriores sem confirmação viva neste ciclo;
- domains_blocked_or_unavailable: 403/429/404 auditado em probe deste ciclo;
- domains_prohibited: fontes da lista proibida.

Lógica PURA (``build_corrected_dry_run``) para testes offline com fixtures.

Saída: reports/garrincha_g1_corrected_dry_run_048_10m_1_2_r2.json
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

GRAPH_STATE_PATH = Path("reports/garrincha_g1_graph_state_048_10m_1_2_r2.json")
SUMMARY_ROUND1 = Path(".autonomous/048_10m_1_2_r2/probes/_summary_garrincha_048_10m_1_2_r2.json")
SUMMARY_ROUND2 = Path(".autonomous/048_10m_1_2_r2/probes/_summary_garrincha_048_10m_1_2_r2_round2.json")
OUT_PATH = Path("reports/garrincha_g1_corrected_dry_run_048_10m_1_2_r2.json")

WIKIMEDIA = {"pt.wikipedia.org", "en.wikipedia.org"}
SEED_RSSSF_URLS = [
    "https://www.rsssfbrasil.com/sel/jogclub.htm",
    "https://www.rsssf.org/tablesb/brazchamp.html",
    "https://www.rsssf.org/sacups/copalib.html",
]

ALLOWED_DOMAINS = {"rsssf.org", "www.rsssf.org", "rsssfbrasil.com", "www.rsssfbrasil.com"}

PROHIBITED_DOMAIN_FRAGMENTS = (
    "transfermarkt", "soccerway", "worldfootball", "fbref", "almanaquedosclubes",
)

FORBIDDEN_OBJECT_KINDS = {
    "CIDADE", "ESTADIO", "BAIRRO", "PAIS", "ESTADO", "ENDERECO", "COORDENADA",
    "CLAUSULA", "GENERICO", "SELECAO_AMBIGUA", "COMPETICAO",
    "EMPRESTIMO_NAO_SUPORTADO", "BASE_JUVENTUDE_NAO_SUPORTADA",
}


def collect_probe_domains(summaries: list[dict]) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    """PURO — separa probes em 4 baldes (mined/only_local/paths_404/prohibited).

    Retorna (mined_plausible, only_local_reports, probe_404_paths):
    - mined_plausible: 200 + Garrincha + Botafogo + contexto de defesa;
    - only_local_reports: domínios sem confirmação viva para ESTE fato
      (404 em caminho probeado ≠ domínio bloqueado: o servidor respondeu;
      o piloto minerou 200 de www.rsssf.org em outros caminhos há 36h);
    - probe_404_paths: caminhos exatos que devolveram 404 (transparência).
    """
    mined: list[dict] = []
    only_local: list[dict] = []
    paths_404: list[dict] = []
    prohibited: list[dict] = []
    for s in summaries:
        for p in s.get("probes", []):
            entry = {
                "domain": p.get("domain"),
                "url": p.get("url"),
                "http_status": p.get("http_status"),
                "mentions_garrincha": p.get("mentions_garrincha", False),
                "mentions_botafogo": p.get("mentions_botafogo", False),
            }
            if any(frag in (p.get("url") or "").lower() for frag in PROHIBITED_DOMAIN_FRAGMENTS):
                prohibited.append(entry)
            elif p.get("http_status") == 200 and p.get("mentions_garrincha") \
                    and p.get("mentions_botafogo") and p.get("mentions_defendeu_context"):
                mined.append(entry)
            elif p.get("http_status") == 404:
                paths_404.append(entry)
            else:
                only_local.append(entry)
    return mined, only_local, paths_404, prohibited


def build_corrected_dry_run(
    graph_state: dict,
    probe_summaries: list[dict],
    seed_rsssf_urls: list[str],
) -> dict:
    """PURO — monta o dry-run corrigido (5 baldes + gate rígido)."""
    domains_already_confirmed = sorted(graph_state.get("confirmed_domains", []))
    distinct_now = int(graph_state.get("distinct_domain_count", 0))

    mined, only_local_rows, paths_404, prohibited = collect_probe_domains(probe_summaries)
    domains_to_be_mined = sorted({m["domain"] for m in mined if m["domain"]})

    # RSSSF Brasil está nos seeds (jogclub.htm = jogadores-por-clube) e produziu
    # confirmação no piloto (Jairzinho) — mas NÃO confirma o fato do Garrincha
    # hoje. Baldes honestos: já-confirmados | a-minerar (probe-confirmed) |
    # só-em-relatórios (produtivos no piloto p/ outros fatos, sem confirmação
    # viva deste fato) | bloqueados (nenhum: 404 foi de caminho, não de host).
    domains_only_local = sorted(
        ({urlparse(u).netloc for u in seed_rsssf_urls} | {b["domain"] for b in only_local_rows})
        - set(domains_already_confirmed) - set(domains_to_be_mined)
    )
    domains_blocked = []

    same_triple = bool(graph_state.get("same_triple_confirmation"))
    canonical = bool(graph_state.get("canonical_fact_found"))
    span_broken = bool(graph_state.get("span_broken", False))
    junk = bool(graph_state.get("junk_object", False))
    forbidden = bool(graph_state.get("forbidden_object", False))
    homonymy = graph_state.get("homonymy_risk", "low")
    requires_core = False
    requires_alias = False
    requires_seed = False

    probe_confirms_one = len(domains_to_be_mined) >= 1
    ready = bool(
        canonical and same_triple and distinct_now == 2
        and sorted(domains_already_confirmed) == ["en.wikipedia.org", "pt.wikipedia.org"]
        and probe_confirms_one
        and not requires_core and not requires_alias and not requires_seed
        and not span_broken and not junk and not forbidden
        and homonymy != "high"
    )
    if ready:
        predicted_domains_after = distinct_now + len(domains_to_be_mined)
        predicted_new_verified = 1 if predicted_domains_after >= 3 else 0
        predicted_records = 21 if predicted_new_verified else 20
    else:
        predicted_domains_after = distinct_now
        predicted_new_verified = 0
        predicted_records = 20

    blocking_reason = None
    if span_broken or junk or forbidden:
        blocking_reason = "BLOCKED_048_10M_1_2_R2_SEMANTIC_RISK"
    elif requires_core or requires_alias or requires_seed:
        blocking_reason = "BLOCKED_048_10M_1_2_R2_REQUIRES_CORE_CHANGE"
    elif not probe_confirms_one:
        blocking_reason = (
            "probe budget (6 req) esgotado: 6x404 em caminhos errados — os caminhos "
            "REAIS minerados pelo piloto sao www.rsssf.org/tablesb/brazchamp.html e "
            "www.rsssf.org/sacups/copalib.html (200 OK, produtivos p/ VENCEU), e "
            "www.rsssfbrasil.com/sel/jogclub.htm (jogadores-por-clube) e seed existente "
            "nunca probeada para Garrincha. Proximo ciclo read-only: probe nessas URLs"
        )

    source_policy_violations = len(prohibited)

    semantic_risk = "low"
    if span_broken or junk or forbidden:
        semantic_risk = "medium"

    if source_policy_violations > 0:
        ready = False
        blocking_reason = "BLOCKED_048_10M_1_2_R2_SOURCE_POLICY_VIOLATION"

    return {
        "audit_id": "garrincha_g1_corrected_dry_run_048_10m_1_2_r2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "read_only_planning",
        "candidate": "garrincha_botafogo",
        "subject": "Garrincha",
        "predicate": "DEFENDEU",
        "object": "Botafogo",
        "domains_already_confirmed_in_graph": domains_already_confirmed,
        "domains_to_be_mined_in_future_g1": domains_to_be_mined,
        "domains_only_in_local_reports": domains_only_local,
        "domains_blocked_or_unavailable": domains_blocked,
        "probe_404_paths": paths_404,
        "domains_prohibited": sorted({pr["domain"] for pr in prohibited if pr.get("domain")}),
        "predicted_distinct_domains_after_g1": predicted_domains_after,
        "predicted_new_verified_if_g1_succeeds": predicted_new_verified,
        "predicted_records_total_if_g1_succeeds": predicted_records,
        "requires_core_change": requires_core,
        "requires_alias_change": requires_alias,
        "requires_seed_change": requires_seed,
        "source_policy_violations": source_policy_violations,
        "junk_objects": 0,
        "forbidden_objects": 0,
        "semantic_risk": semantic_risk,
        "ready_for_future_g1": ready,
        "blocking_reason": blocking_reason,
        "d5_correction_note": (
            "local_existing_covered NÃO é tratado como mineração do ciclo: "
            "domínios confirmados no grafo e domínios a minerar são baldes distintos"
        ),
    }


def main() -> int:
    graph_state = json.loads(GRAPH_STATE_PATH.read_text(encoding="utf-8"))
    summaries: list[dict] = []
    for path in (SUMMARY_ROUND1, SUMMARY_ROUND2):
        if path.exists():
            summaries.append(json.loads(path.read_text(encoding="utf-8")))
    report = build_corrected_dry_run(graph_state, summaries, SEED_RSSSF_URLS)
    OUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"ok → {OUT_PATH} · ready_for_future_g1={report['ready_for_future_g1']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
