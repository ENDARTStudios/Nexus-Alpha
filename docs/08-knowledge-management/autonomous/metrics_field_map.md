# metrics_field_map (reconciliação #059E)

current source: `metrics_vercel_degraded.json`  (status=online)
baseline source: `post_reingest_048_10C.json`  (build_space_commit=732ff3e (git 0b5bc32), worker_run_id=36354572850)

| campo lógico | caminho JSON atual (/api/metrics) | valor atual | caminho baseline | valor baseline |
|---|---|---|---|---|
| facts (top-level) | `facts` | 1894 | `graph.facts` | 335 |
| concepts (Conceito) | `facts` | 1894 | `graph.label_counts.Conceito` | 1894 |
| persisted_facts (:Fato) | `ingestion_accounting.persisted_facts` | 335 | `ingestion_accounting.persisted_facts` | 335 |
| verified_facts_domain_independent | `verification.verified_facts_domain_independent` | 11 | `verification.verified_facts_domain_independent` | 11 |
| facts_with_multi_domain (>=2 dom) | `verification.facts_with_multi_domain` | 12 | `verification.facts_with_multi_domain` | 12 |
| facts_with_three_or_more_domains | `(ausente)` | N/A | `graph.facts_with_three_or_more_domains` | 11 |
| max_domain_confirmations | `verification.max_domain_confirmations` | 3 | `verification.max_domain_confirmations` | 3 |
| duplicate_cross_domain (ingest runtime) | `ingestion_accounting.duplicate_cross_domain` | 23 | `ingestion_accounting.duplicate_cross_domain` | 23 |
| duplicate_cross_domain (graph) | `(ausente)` | N/A | `graph.duplicate_cross_domain` | 12 |
| run_scoped_gap | `ingestion_accounting.run_scoped_gap` | None | `ingestion_accounting.run_scoped_gap` | None |
| graph_scoped_gap | `ingestion_accounting.graph_scoped_gap` | None | `ingestion_accounting.graph_scoped_gap` | None |
| distinct_canonical_keys | `ingestion_accounting.distinct_canonical_keys` | 314 | `ingestion_accounting.distinct_canonical_keys` | 314 |
| unaccounted_raw | `ingestion_accounting.unaccounted_raw` | 0 | `ingestion_accounting.unaccounted_raw` | 0 |
| canonical_to_fact_gap | `ingestion_accounting.canonical_to_fact_gap` | -21 | `ingestion_accounting.canonical_to_fact_gap` | -21 |
| fallback_promoted_to_graph | `fallback_health.fallback_promoted_to_graph` | 0 | `fallback_health.fallback_promoted_to_graph` | None |
| masked_extraction_failures | `fallback_health.masked_extraction_failures` | 10 | `fallback_health.masked_extraction_failures` | None |
| top_invalid_predicates | `extraction_quality.top_invalid_predicates` | [] | `extraction_quality.top_invalid_predicates` | [] |
| raw_triples | `extraction_quality.raw_triples` | 7157 | `extraction_quality.raw_triples` | 7157 |
| canonical_triples | `extraction_quality.canonical_triples` | 2603 | `extraction_quality.canonical_triples` | 2603 |
| last_ingest_at | `ingestion_accounting.last_ingest_at` | 2026-09-27T22:18:27.922814+00:00 | `ingestion_accounting.last_ingest_at` | 2026-09-27T22:18:27.922814+00:00 |

## Convergência
- `facts` top-level == `Conceito` count: 1894 == 1894 -> True
- `persisted_facts` / `:Fato`: 335 == 335 -> True
- `extraction_quality` idêntico: False
- `run_scoped_gap` presente no atual: False
- `graph_scoped_gap` presente no atual: False
