# RUNBOOK — #048.10L.2 GEO next batch worker (5 estádios)

**Pré-condição:** `reports/geo_next_batch_implementation_dry_run_048_10L.json` com
`gate_passed=true` (`classification=SUCCESS_048_10L_NEXT_BATCH_READY_FOR_WORKER`).

Lote (pt + en + Nominatim/ODbL, `LOCALIZADO_EM`, quórum 3):

```text
ESTÁDIO OLÍMPICO NILTON SANTOS --LOCALIZADO_EM--> RIO DE JANEIRO
MARACANÃ --LOCALIZADO_EM--> RIO DE JANEIRO
BEIRA-RIO --LOCALIZADO_EM--> PORTO ALEGRE
MINEIRÃO --LOCALIZADO_EM--> BELO HORIZONTE
ARENA FONTE NOVA --LOCALIZADO_EM--> SALVADOR
```

## 0. Pré-flight (read-only, sem worker)
1. `python scripts/check_space_telemetry.py` → telemetria viva não stale.
2. `gh workflow view "Nexus-Alpha Autonomous Worker Cron"` → `disabled_manually`.
3. Snapshot Neo4j read-only (nodes/rels/Fato) → baseline.
4. Cron desabilitado antes/depois; **máximo 1 dispatch** (2 só com diagnóstico).

## 1. Worker
1. `gh workflow enable "Nexus-Alpha Autonomous Worker Cron"`.
2. `gh workflow run "Nexus-Alpha Autonomous Worker Cron"`.
3. `gh workflow disable "Nexus-Alpha Autonomous Worker Cron"`.
4. Aguardar run `success`; registrar `run_id`.

## 2. Pós (read-only)
1. `/api/metrics` vivo: `verified`, `fact_count`, `concept_count`, `quorum`,
   `publisher_family_count`, `graph_scoped_gap`, `fact_accounting_status`.
2. `python scripts/export_geo_fact_domains.py` (Neo4j read-only) → evidência fact-level.
3. Validar:
   `python scripts/validate_geo_expected_facts.py --expected reports/geo_expected_facts_048_10L.json --post <metrics_post.json> --fact-domains <fact_domains.json> --output reports/geo_next_batch_validation_048_10L_2.json`.
4. Esperado: 5/5 fatos com `pt + en + nominatim`; `verified 15 -> 20`; `graph_scoped_gap=0`;
   `top_invalid_predicates=[]`; `fallback_promoted_to_graph=0`; zero junk.

## 3. Classificação
- `SUCCESS_048_10L_2_GEO_NEXT_BATCH_5_OF_5` se 5/5 fortes, zero regressão/junk, `graph_scoped_gap=0`.
- `PARTIAL_048_10L_2_NEXT_BATCH` se <5/5 (taxonomia de falha em
  `reports/geo_real_page_failure_analysis_048_10L_2.md`).

## 4. Não fazer
- Não alterar quórum (3); não treinar; não fazer force-push; não escalar novo lote
  (#048.10M) antes de fechar 5/5; não generalizar a exceção homônima além de
  `SAO PAULO`/`RIO DE JANEIRO` (source-scoped).
