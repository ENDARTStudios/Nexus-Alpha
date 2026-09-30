# RUNBOOK_048_10M_2_FUTURE_BATCH

## Objetivo
Extensão do lote DEFENDEU (8-12 candidatos) **ou** abertura de família futura — apenas planejamento.

## Pré-condições
1. #048.10M.1 fechado sem junk/regressão.
2. `verified >= 26`; `graph_scoped_gap=0`; `fact_accounting_status=ok`; `publisher_family_count=3`.
3. Atlas estendido com novos candidatos low/medium risk.
4. Dry-run offline próprio 3-domínios.
5. Todos os gates do RUNBOOK_048_10M.1.

## Famílias futuras
- **DISPUTOU / POSSUIR**: exigem issue separado (`extractor` frame + endurecer `span_validator`/
  `predicate_mapper`). **Não** executar sem mudança ontológica aprovada.

> Não executar neste task. Não treinar.
