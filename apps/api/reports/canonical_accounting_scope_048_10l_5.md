# canonical_to_fact_gap scope reconciliation (#048.10L.5)

## Fórmula atual (legado, preservada)

`app.py` → `IngestAccounting.snapshot()`:

```python
canonical_to_fact_gap = distinct_canonical_keys - persisted_facts
```

## Escopos

- `distinct_canonical_keys`: **RUN-SCOPED** (contador do processo; zera a cada restart).
- `persisted_facts`: **WHOLE-GRAPH** (`count(:Fato)`).

São escopos diferentes → o gap (frequentemente negativo) é **esperado por construção**.

## Por que é negativo

Após um restart do Space, `distinct_canonical_keys=0` e `persisted_facts=412` → `-412`.
Durante um run com ingestão, `distinct` sobe, mas o gap legado **nunca** mede a mesma coisa.
A métrica honesta same-scope é `run_scoped_gap` (= `distinct - run_persisted_facts_created`).

## Correção (#048.10L.5, aditiva)

Novos campos em `ingestion_accounting` (`/api/metrics`, read-only):

```text
canonical_to_fact_gap                  (legado, mantido)
canonical_to_fact_gap_status           ok | scope_mismatch_non_blocking | duplicate_fact_hashes | query_error
canonical_to_fact_gap_interpretation   canonical_occurrences_scope_minus_persisted_fact_nodes_scope
canonical_to_fact_gap_same_scope       run_scoped_gap (mesmo escopo run)
canonical_occurrences_count            distinct_canonical_keys (run)
persisted_fact_nodes_count             :Fato node count (grafo)
```

`metric_glossary` atualizado com as mesmas notas.

## Impacto

```text
verified:        nenhum (20)
quorum:          nenhum (3)
training gate:   nenhum (não usa canonical_to_fact_gap)
contaminação:    NÃO comprovada (graph_scoped_gap=0, fact_accounting_status=ok)
escrita:         NÃO exigida (correção apenas de telemetria)
```

Status: **explicado_nao_bloqueante** (vivo: `scope_mismatch_non_blocking`).
