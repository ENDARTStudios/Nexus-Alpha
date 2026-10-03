# #052.3.1 — Fact accounting correction

**Status:** `SUCCESS_052_3_1_GRAPH_ACCOUNTING_READY`
**Worker executado:** NÃO · **Backfill:** NÃO · **Deploy do Space:** **OK** · **Treino:** bloqueado · **#048.10L:** congelado

## Sintoma anterior

```text
graph_scoped_gap = -404
persisted_facts = 404
distinct_fact_hashes ausente/0
```

## Causa raiz

`app.py::IngestAccounting.snapshot` calculava `graph_scoped_gap = graph_distinct_fact_hashes - persisted_facts`
com `graph_distinct_fact_hashes = snapshot.get("distinct_fact_hashes", 0)`. Porém **`graph_connector.graph_snapshot()`
não incluía a chave `distinct_fact_hashes` no dict de retorno** (a query até selecionava, mas o retorno omitia)
→ `.get(..., 0)` devolvia **0** → gap falsamente `-404`. Causa: **C1 (campo não populado no snapshot)**.

## Correção

- Helper puro `src/ops/fact_accounting.py` (`compute_fact_accounting`) — sem rede/Neo4j/Qdrant/escrita.
- `graph_connector.get_fact_accounting_counts()` — leitura **MATCH/RETURN** sobre `:Fato` usando `f.chave`
  (a propriedade real do MERGE) com fallback `id(f)` **apenas para contagem**.
- Nova fórmula: **`graph_scoped_gap = distinct_fact_node_keys - persisted_facts`**.
- Novos campos (aditivos) em `ingestion_accounting`: `distinct_non_null_fact_hashes`, `missing_fact_hash_count`,
  `distinct_fact_node_keys`, `duplicate_fact_hash_group_count`, `fact_accounting_status`.
- `metric_glossary` atualizado (aditivo). Todos os campos legados preservados.

## Resultado local / vivo

```text
persisted_facts = 404
distinct_non_null_fact_hashes = 404
missing_fact_hash_count = 0
distinct_fact_node_keys = 404
duplicate_fact_hash_group_count = 0
fact_accounting_status = ok
graph_scoped_gap = 0
run_scoped_gap = 0
unaccounted_raw = 0
verification.quorum = 3
verified_facts_domain_independent = 15
fact_count = 404
concept_count = 2009
publisher_family_count = 3
top_invalid_predicates = []
fallback_promoted_to_graph = 0
```

Fonte: `reports/metrics_post_052_3_1.json` (Space `sha 79413cf2…`, antes `8ff50d4d…`).

## Impacto cognitivo

Nenhum: `verified_facts_domain_independent` (15), `quorum` (3), `fact_count` (404), `concept_count` (2009),
`publisher_family_count` (3), `run_scoped_gap` (0), `unaccounted_raw` (0), `top_invalid_predicates` ([]) e
`fallback_promoted_to_graph` (0) **inalterados**.

## Dívidas

- Nenhuma nova: `missing_fact_hash_count = 0` e `duplicate_fact_hash_group_count = 0` → contabilidade consistente.
- **#048.10L** permanece **congelado** até dry-run próprio do next batch.

## Segurança

Nenhum worker; nenhuma escrita em Neo4j/Qdrant/ingest; **nenhum backfill**; nenhuma seed; quórum 3;
sem force-push; anti-leak clean. `.autonomous/**`, venv de deploy e métricas brutas **não** commitados.
