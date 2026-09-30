# RUNBOOK_048_10M_1_DEFENDEU_BATCH

## Objetivo
Executar futuramente o primeiro lote DEFENDEU piloto — **apenas após aprovação do Operador**.

## Pré-condições
1. Atlas #048.10M identificou ≥6 candidatos low-risk (atual: 7 low / 5 medium).
2. Expected facts registry criado em `reports/` (novo).
3. Dry-run offline prevê `full_collision` para todos os candidatos elegíveis.
4. Zero junk/forbidden no dry-run.
5. Nenhuma seed ativa alterada ainda (neste lote, seeds só via config curada e revisada).
6. `check_space_telemetry` OK.
7. `graph_scoped_gap = 0`.
8. `fact_accounting_status = ok`.
9. `publisher_family_count = 3`.
10. Snapshot AuraDB.
11. Baseline `/api/metrics`.
12. Worker manual único (cron `disabled_manually` antes/depois; máx. 1 dispatch, 2 só com diagnóstico).
13. Export fact-level strong.
14. Validate expected facts.
15. **Não treinar.**

## Proibições
- não alterar `predicate_mapper`/`span_validator`/`canonicalizer`/`extractor`;
- não usar Transfermarkt/Soccerway/Almanaque sem licença;
- não bypass bot protection;
- não escalar #048.10M.2 se junk ou regressão.

> Não executar neste task.
