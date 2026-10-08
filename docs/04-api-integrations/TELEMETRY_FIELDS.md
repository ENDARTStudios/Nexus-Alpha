# O4 — Glossário canônico de campos de telemetria (`/api/metrics`)

Fonte de verdade: o dicionário `metric_glossary` **dentro** da própria resposta
de `/api/metrics` (contrato autodescritivo). Esta página documenta os campos
que mais confundem, em ordem de leitura.

| Campo | Significado exato | Não confundir com |
|---|---|---|
| `facts` | **legacy/compat**: conta nós `:Conceito` (mesmo valor de `concept_count`) | não é o número de fatos! |
| `concept_count` | nº de nós `:Conceito` | — |
| `fact_count` | nº de nós `:Fato` persistidos | `facts` (legacy) |
| `verified_facts` | nº de `:Fato` com `verificado = true` | sinônimo operacional de `verified_facts_domain_independent` |
| `verification.verified_facts_domain_independent` | fatos corroborados por ≥ quórum (3) de **domínios distintos** | `facts_with_multi_domain` (≥2 domínios, abaixo do quórum) |
| `extraction_quality.facts_with_multi_domain` | fatos com ≥2 domínios distintos (potenciais, pré-quórum) | verificados |
| `extraction_quality.potential_verified_before_quorum` | alias histórico de `cross_source` | — |
| `ingestion_accounting.run_scoped_gap` | gap contábil do ciclo: `distinct_canonical_keys − new_facts_created` (mesmo escopo) | `canonical_to_fact_gap` |
| `ingestion_accounting.canonical_to_fact_gap` | compara chaves canônicas do ciclo com `:Fato` do grafo INTEIRO — **escopos diferentes por construção**; negativo é esperado | use `run_scoped_gap`/`graph_scoped_gap` |
| `ingestion_accounting.graph_scoped_gap` | mesma métrica no escopo do grafo (0 = íntegro) | — |
| `cognitive_health.hebbian_consistency_check` | grafo respondendo e consistente no snapshot | não é "saúde semântica" |
| `graph_ready` (PR #1/R2) | `true` se o snapshot do grafo foi lido com sucesso no request | `status` ("online" \| "booting") |

**Regra de bolso para leitura rápida:** `concept_count` (volume de entidades) ·
`fact_count` (volume de fatos) · `verified_facts_domain_independent`
(quantos passaram o quórum 3) · `run_scoped_gap`/`graph_scoped_gap` (0 =
contabilidade íntegra).
