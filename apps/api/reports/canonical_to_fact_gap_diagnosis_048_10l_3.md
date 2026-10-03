# canonical_to_fact_gap diagnosis (#048.10L.3)

## Sintoma

```text
canonical_to_fact_gap = -93            (pós #048.10L.2)
persisted_facts        = 413
distinct_canonical_keys= 320 (run-scoped, in-process)
graph_scoped_gap       = 0             (fact_accounting_status = ok)
```

## Fórmula atual

`app.py` → `IngestAccounting.snapshot()`:

```python
canonical_to_fact_gap = self.distinct_canonical_keys - persisted_facts
```

Onde:
- `distinct_canonical_keys` é **run-scoped** (contador do processo do Space; reinicia a cada restart);
- `persisted_facts` é **whole-graph** (`count(:Fato)`).

## Classificação

```text
SCOPE_MISMATCH  (por construção; NÃO é defeito de dados)
```

Não é `FORMULA_ISSUE` (a fórmula faz o que declara), nem `DATA_QUALITY_ISSUE`
(`graph_scoped_gap=0` e `fact_accounting_status=ok`).

## Evidência

- `tests/test_ingest_accounting.py::test_metrics_exposes_ingestion_accounting` documenta e **afirma**
  `canonical_to_fact_gap == -4` (persisted=4, run distinct=0) → negativo é o **comportamento esperado**.
- `tests/test_app_metrics.py::test_metrics_scoped_gaps_exposed` exige `run_scoped_gap`/`graph_scoped_gap`.
- A métrica honesta de consistência run-scoped é `run_scoped_gap` (=0); a whole-graph é `graph_scoped_gap` (=0).

## Impacto

```text
bloqueante?          NÃO
afeta verified?      NÃO
afeta quórum?        NÃO
afeta treino gate?   NÃO
exige escrita?       NÃO (nenhum backfill necessário)
```

## Recomendação

- **Não** alterar a fórmula (há testes que a documentam); a correção foi **documental**:
  entrada `canonical_to_fact_gap` adicionada ao `metric_glossary` do `/api/metrics` esclarecendo o
  scope mismatch e apontando `graph_scoped_gap` como métrica de consistência.
- Uso canônico continua: `graph_scoped_gap` (0) + `fact_accounting_status` (ok) para consistência;
  `canonical_to_fact_gap` tratado como **não bloqueante**.

Status para o gate de prontidão: **explicado_nao_bloqueante**.
