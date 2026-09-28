# RUNBOOK_048_10H_GEO_WORKER

Pré-requisitos e passos para o **worker incremental GEO** (#048.10H). **Não executar neste ciclo.**

## Pré-condições

1. **Operador** faz upload/redeploy do HF Space para o commit `bdc9452` ou posterior
   (não apenas restart — ver `reports/BLOCKED_048_10G_SPACE_REDEPLOY.md`).
2. Validar `/api/metrics` com:
   - `concept_count` presente
   - `fact_count` presente
   - `ingestion_accounting.run_scoped_gap` presente
   - `ingestion_accounting.graph_scoped_gap` presente
   - `verification.quorum = 3`
   - `fallback_promoted_to_graph = 0`
   - `top_invalid_predicates = []`
3. Rodar o preflight: `python scripts/check_space_telemetry.py` → deve retornar `classification = OK`.
   Caso contrário: `BLOCKED_SPACE_STALE_TELEMETRY` (não rodar worker).

## Execução (somente após pré-condições)

4. Executar **snapshot da AuraDB** (backup read-only).
5. Capturar **baseline** (`/api/metrics`).
6. Disparar **worker manual único** (1 ciclo) — via `workflow_dispatch` do cron ou execução controlada.
7. Capturar **pós-run** (`/api/metrics`).
8. Rodar **auditorias read-only** (`audit_cross_source`, `audit_fact_duplicates`, etc.).

## Critérios de sucesso esperados

| Métrica | Antes | Esperado |
|---|---:|---:|
| verified_facts_domain_independent | 11 | >= 15 |
| records_total | 11 | >= 15 |
| unique_predicates | 2 | 3 |
| non_VENCEU_ratio | 0.09 | >= 0.30 |
| publisher_family_count | 2 | 3 (se OSM reconhecido) |

## Gates

- `top_invalid_predicates = []`
- `fallback_promoted_to_graph = 0`
- `unaccounted_raw = 0`
- `quorum = 3` (inalterado)
- `pt_narrative_regression = false`, `en_narrative_regression = false`

## Proibições

- **Não** executar treino (treino continua fechado; `records_total < 50`, `top_predicate_share > 0.50`).
- **Não** baixar quórum nem relaxar validator.
- **Não** rodar worker se o preflight não retornar `OK`.
- **Não** usar Transfermarkt/Soccerway; **não** usar API do Almanaque sem licença.

## Gate duro de telemetria (#048.10H.1)

A partir do #048.10H.1, o `worker_cycle.py` **se autobloqueia** antes de qualquer
fetch/miner/ingest se a telemetria do Space estiver stale/divergente:

- `concept_count` ausente;
- `fact_count` ausente;
- `ingestion_accounting.run_scoped_gap` ausente;
- `ingestion_accounting.graph_scoped_gap` ausente;
- `verification.quorum != 3`;
- `fallback_promoted_to_graph != 0`;
- `top_invalid_predicates` não vazio;
- `ingestion_accounting.unaccounted_raw != 0`.

O bloqueio ocorre **antes** de qualquer fetch/miner/ingest. **Nenhuma** escrita em Neo4j/Qdrant é tentada.
Mensagem: `BLOCKED_*` + `missing_fields` + `reason` + `No writes were attempted.` (exit non-zero).

Escape apenas offline/local: `--allow-unverified-local` (ou `NEXUS_ALLOW_UNVERIFIED_LOCAL=true`).
**Nunca** usar em produção.

## Validação pós-run

Após o worker, rodar:

```bash
python scripts/validate_geo_expected_facts.py \
  --baseline reports/baseline_pre_048_10H.json \
  --post reports/post_reingest_048_10H.json \
  --geo-report reports/geo_post_048_10H.json \
  --expected reports/geo_expected_facts_048_10H.json \
  --output reports/geo_expected_validation_048_10H.json
```

Critério de sucesso:

- `expected_facts_verified = 4`
- `junk_objects_detected = 0`
- `regression_existing_verified = false`
- `top_invalid_predicates = []`
- `fallback_promoted_to_graph = 0`
- `unaccounted_raw = 0`
