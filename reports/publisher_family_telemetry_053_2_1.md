# #053.2.1 — Live publisher-family telemetry

**Status:** `SUCCESS_053_2_1_LIVE_PUBLISHER_FAMILY_READY`
**Worker executado:** NÃO · **Deploy do Space:** **OK** · **Treino:** bloqueado · **#048.10L:** congelado

## Contrato

- **Wikimedia:** `*.wikipedia.org` (pt/en/outros) → mesma família.
- **RSSSF:** `rsssf.org`/`rsssfbrasil.com` → mesma família, com warning.
- **OpenStreetMap:** `nominatim.openstreetmap.org`/`overpass*`/`openstreetmap.org` → família geográfica/open data.
- **Unknown:** não conta como família independente; **Almanaque** só com licença (não usado).
- Classificação é **por domínio**, nunca por menção textual.

## Helper compartilhado

- `src/ops/publisher_family.py` (runtime, puro): `classify_publisher_family`, `build_publisher_family_snapshot`.
- `scripts/publisher_family_telemetry.py` **delega** ao helper (convergência local/runtime).

## Resultado local

```text
publisher_family_count = 3
effective_publisher_count = 3
distribution = { Wikimedia: 30, OpenStreetMap: 4, RSSSF: 11 }
warnings = [WIKIMEDIA_MULTIPLE_LANGUAGES_NOT_INDEPENDENT,
            RSSSF_AND_RSSSF_BRASIL_SAME_FAMILY_SUSPECTED,
            OPENSTREETMAP_IS_GEOGRAPHIC_OPEN_DATA_NOT_NEWS_EDITORIAL]
```

## Resultado vivo (`/api/metrics`)

- **deploy tentado:** SIM (upload allowlisted via `scripts/deploy_hf_space_safe.py --execute`)
- **build:** `RUNNING` (novo `sha=8ff50d4d…`, antes `3aa1ad22…`)
- **publisher_family_count:** **3** · **effective_publisher_count:** **3**
- **distribution:** `{ OpenStreetMap: 4, RSSSF: 11, Wikimedia: 31 }`
- **warnings:** presentes (3)
- **quorum:** 3 · **verified_facts_domain_independent:** 15 · **fact_count:** 404 · **concept_count:** 2009
- **run_scoped_gap:** 0 · **graph_scoped_gap:** -404 (dívida #052.3.1) · **unaccounted_raw:** 0
- **top_invalid_predicates:** [] · **fallback_promoted_to_graph:** 0

Fonte: `reports/metrics_post_053_2_1.json`.

## Impacto no gate (read-only)

```text
publisher_family_count = 3
effective_publisher_count = 3
diversity_gate = false (ainda por records/top_predicate/object)
publisher_independence_gate = true
training_recommended = false
training_allowed = false
```

## Contrato preservado

`facts` (legado), `concept_count`, `fact_count`, `verified_facts`, `quorum`,
`verified_facts_domain_independent`, `facts_with_multi_domain`, `run_scoped_gap`,
`graph_scoped_gap`, `unaccounted_raw`, `top_invalid_predicates`, `fallback_promoted_to_graph`
**inalterados**. `metric_glossary` ganhou 4 notas novas (aditivas).

## Dívidas

- **#052.3.1** — `graph_scoped_gap = -404` (telemetria contábil), **separada**.
- **#048.10L** — congelado até telemetria estável + dry-run do next batch.

## Segurança

Nenhum worker; nenhuma escrita em Neo4j/Qdrant/ingest; nenhuma seed; quórum 3; sem force-push;
anti-leak clean. `.autonomous/**`, venv de deploy e métricas brutas **não** commitados.
