# RUNBOOK_048_10L_4_GEO_NEXT_BATCH_WORKER_RETRY

## Pré-condições
1. `#048.10L.3` dry-run prevê 5/5 full collision e 0 junk (`reports/geo_next_batch_closure_dry_run_048_10l_3.json`, `gate_passed=true`).
2. `audit_geo_worker_dry_run` não está stale (`reports/geo_worker_dry_run_048_10l_3.json`, `gate_passed=true`).
3. `canonical_to_fact_gap` = explicado não bloqueante (`reports/canonical_to_fact_gap_diagnosis_048_10l_3.md`).
4. `python scripts/check_space_telemetry.py` OK.
5. `graph_scoped_gap = 0`.
6. `fact_accounting_status = ok`.
7. `publisher_family_count = 3`.
8. Snapshot AuraDB read-only verificado.
9. Baseline `/api/metrics` capturado.
10. Worker manual único (cron `disabled_manually` antes/depois; máx. 1 dispatch, 2 só com diagnóstico).
11. Pós-métricas.
12. Export fact-level:
    `python scripts/export_geo_fact_domains.py --expected reports/geo_expected_facts_048_10L.json --audit-id geo_fact_level_domains_048_10L_4 --output reports/geo_fact_level_domains_048_10L_4.json`
13. `python scripts/validate_geo_expected_facts.py --expected reports/geo_expected_facts_048_10L.json --fact-domains reports/geo_fact_level_domains_048_10L_4.json --post reports/post_reingest_048_10L_4.json --output reports/geo_expected_validation_048_10L_4.json`
14. Não treinar.
15. Não escalar next-next batch.

## Expectativa (do baseline 18 verified / 18 records)
```text
verified_facts_domain_independent: 18 -> 20
records_total:                      18 -> 20
unique_predicates:                   3
non_VENCEU_ratio:                   ~0.44 -> ~0.50
top_predicate_share:                ~0.56 -> ~0.50
publisher_family_count:              3
graph_scoped_gap:                    0
fact_accounting_status:              ok
```
(5 fatos do next batch no alvo; 3 já verificados em #048.10L.2 → +2 incrementais.)

## Bloqueios
Treino continua `false` se `records < 50` ou `environment_gate=false`.
Se aparecer junk/forbidden/regressão, congelar e gerar incidente (não auto-restore).
