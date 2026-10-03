# RUNBOOK_048_10H_3_GEO_RETRY

Pré-requisitos e passos do **retry do worker GEO incremental** (#048.10H.3). **Não executar neste ciclo.**

## Pré-condições

1. `python scripts/check_space_telemetry.py` → `ok=true`.
2. Dry-run **#048.10H.2.1** aprovado: `reports/geo_wiki_parser_dry_run_048_10h_2_1.json`
   (`osm=4`, `wiki_pt=4`, `wiki_en=4`, `full_collision=4`, `junk=0`, `gate_passed=true`).
3. Snapshot AuraDB read-only (`scripts/aura_snapshot.py`).
4. Baseline (`/api/metrics`).

## Execução

5. Worker manual único (1 `workflow_dispatch`) — com o hard telemetry gate ativo.
6. Pós-métricas (`/api/metrics`).
7. `python scripts/validate_geo_expected_facts.py --baseline ... --post ... --geo-report ... --expected reports/geo_expected_facts_048_10H.json --output ...`.
8. Auditorias read-only.

## Critérios de sucesso

```text
verified_facts_domain_independent: 11 -> >= 15
records_total: 11 -> >= 15
unique_predicates: 2 -> 3
non_VENCEU_ratio: 0.09 -> >= 0.30
publisher_family_count: 2 -> 3
validate_geo_expected_facts: expected_facts_verified = 4/4
junk_objects = 0 · regression = false · top_invalid_predicates = []
```

## Proibições

- Não treinar (records < 50, top_predicate_share > 0.50).
- Não escalar **#048.10L** antes do sucesso do lote atual.
- Não baixar quórum; não relaxar validator; não force-push.
- Não usar Transfermarkt/Soccerway; não usar Almanaque sem licença.
