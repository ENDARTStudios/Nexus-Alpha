# #052.3.1 — graph_scoped_gap negativo (diagnóstico read-only)

**Data:** 2026-09-28 · **Status:** dívida observacional, **não bloqueante**

## Sintoma

```text
ingestion_accounting.graph_scoped_gap = -403   (pós-worker #048.10H)
ingestion_accounting.persisted_facts  = 403
ingestion_accounting.unaccounted_raw  = 0
verified_facts_domain_independent     = 11 (estável)
top_invalid_predicates                = []
fallback_promoted_to_graph            = 0
```

## Fórmula (código atual, `app.py`)

```text
graph_scoped_gap = graph_distinct_fact_hashes - persisted_facts
```

Com `graph_scoped_gap = -403` e `persisted_facts = 403`, conclui-se
`graph_distinct_fact_hashes = 0`.

## Hipóteses

1. `snapshot.get("distinct_fact_hashes", 0)` retorna **0** porque a chave não veio no payload do
   `graph_snapshot()` executado no Space (deploy/versão) — apesar de a query existir no código.
2. A query `count(DISTINCT fa.sujeito + '|' + fa.predicado + '|' + fa.objeto)` retorna 0 por
   propriedades ausentes/nulas em parte dos `:Fato`.
3. O campo foi renomeado/aninhado em outro nível (divergência entre `app.py` e o build live).

## Impacto

- **Nenhum** sobre verificação/quórum: `unaccounted_raw=0`, `top_invalid=[]`, `fallback=0`, `verified` estável.
- O campo **não** deve ser usado como gate de treino até ser corrigido.

## Recomendação

- Issue observacional separado (não misturar com o destravamento GEO).
- Corrigir a contabilidade de `distinct_fact_hashes` **sem** alterar quórum/verificação.
- Considerar clamp/abs apenas para exibição, se a semântica de gap negativo não fizer sentido.

> Diagnóstico read-only. Nenhuma alteração de código/validadores/quórum neste ciclo.
