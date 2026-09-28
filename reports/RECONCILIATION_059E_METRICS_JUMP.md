# RECONCILIATION_059E_METRICS_JUMP

**Data:** 2026-09-28
**Repo:** `ENDARTStudios/Nexus-Alpha`
**HEAD:** `8cdab7f`
**Tipo:** reconciliação **read-only** (nenhum worker, nenhuma seed, nenhum treino, nenhum restore)
**Classificação:** `RECONCILED_BENIGN_METRIC_DEFINITION`

## Alerta reconciliado

Foi reportado: `facts 335 -> 1894`, `duplicate_cross_domain 12 -> 23`, `verified_facts_domain_independent 11 -> 11`,
e ausência de `run_scoped_gap` / `graph_scoped_gap`.

## Veredito

**Não houve salto real de dados.** Os números vieram de **campos diferentes** do mesmo payload, e o grafo está
**inalterado** desde o último ingest (`last_ingest_at = 2026-09-27T22:18:27Z`).

### `facts 335 -> 1894` = campo errado (H1)

`app.py` (`/api/metrics`, linha 379) mapeia **`"facts": snapshot["concepts"]`**, e `graph_snapshot()` define
`concepts = MATCH (c:Conceito) RETURN count(c)`. Já o `:Fato` é `persisted_facts` (`snapshot["facts"]`).

- `facts` (top-level) = **1894** = nós **`Conceito`**.
- `persisted_facts` / `:Fato` = **335**.

Ambos coexistem no próprio baseline `reports/post_reingest_048_10C.json`:
`graph.label_counts = { Episodio: 2260, Conceito: 1894, Fato: 335, FonteWeb: 49 }`.
→ `METRIC_DEFINITION_BROAD_NODE_COUNT` (rótulo `facts` ambíguo; não é `:Fato`).

### `duplicate_cross_domain 12 -> 23` = campo errado (H1)

- `12` = `verification.facts_with_multi_domain` (`snapshot["cross_source"]` = fatos com **>= 2 domínios**) e
  `graph.duplicate_cross_domain` no baseline.
- `23` = `ingestion_accounting.duplicate_cross_domain` (contador **de runtime** de ocorrências cross-domain do ingest).

Os dois valores aparecem **no mesmo baseline** (`post_reingest_048_10C.json`: linha 27 `12`, linha 139 `23`).
→ campo errado, não crescimento.

### `run_scoped_gap` / `graph_scoped_gap` ausentes = Space em build antigo (H4, não é regressão de código)

- O código em `main` **tem** os campos: `app.py::IngestAccounting.snapshot()` (linhas 249-280) e
  `src/database/graph_connector.py` (`distinct_fact_hashes`, etc.).
- Commit `503e6a3` — `feat(core): split accounting run-scoped vs graph-total (#052.2)` (2026-09-27 00:18).
- O Space em execução foi construído em `732ff3e (git 0b5bc32)` — 2026-09-24 — que é **ancestral** de `503e6a3`
  (`merge-base --is-ancestor 0b5bc32 503e6a3` = 0; o inverso = 1).
- Logo o **Space nunca foi redeployado após #052.2** → telemetria ausente.
→ `FIELDS_ABSENT_DUE_STALE_SPACE_BUILD` (ver também `FIELDS_PRESENT_BUT_NESTED_DIFFERENTLY` para `facts`).

### H2 (cron automático) = FALSO

- `ai-cron.yml` está `disabled_manually` (`gh workflow list --all`).
- **Todos** os runs do worker têm `event = workflow_dispatch`; **nenhum** `schedule`.
- Último run: `36354572850` @ `2026-09-27T22:14:13Z`, **antes** de `d362dcd` (`2026-09-28T00:50:07Z`).
- O baseline registra `workflow_after: disabled_manually`.
- `last_ingest_at` **idêntico** ao baseline (`2026-09-27T22:18:27Z`) ⇒ **nenhuma ingestão após o baseline**.
→ `CRON_DISABLED_NO_RUNS` (sem runs após o baseline).

### H3 (contaminação) = NÃO SUSTENTADA

- `top_invalid_predicates = []`
- `fallback_promoted_to_graph = 0`
- `masked_extraction_failures = 10` (inalterado)
- `unaccounted_raw = 0`
- `verified_facts_domain_independent = 11` (estável)
- `extraction_quality` **idêntico** ao baseline (`raw_triples=7157`, `canonical_triples=2603`, `rejected_noise=4110`, mesma `top_unmapped_predicates`).

## Comparação campo-a-campo

Ver `.autonomous/reconciliation/metrics_field_map.md`.

| campo lógico | /api/metrics atual | baseline post_reingest_048_10C |
|---|---|---|
| `facts` (top-level) | 1894 (`Conceito`) | 335 (`Fato` — nome ambíguo no relatório) |
| `Conceito` | 1894 | 1894 |
| `persisted_facts` / `:Fato` | 335 | 335 |
| `verified_facts_domain_independent` | 11 | 11 |
| `facts_with_multi_domain` | 12 | 12 |
| `facts_with_three_or_more_domains` | (não exposto) | 11 |
| `max_domain_confirmations` | 3 | 3 |
| `duplicate_cross_domain` (ingest) | 23 | 23 |
| `duplicate_cross_domain` (graph) | (não exposto) | 12 |
| `distinct_canonical_keys` | 314 | 314 |
| `canonical_to_fact_gap` | -21 | -21 |
| `unaccounted_raw` | 0 | 0 |
| `fallback_promoted_to_graph` | 0 | 0 |
| `top_invalid_predicates` | [] | [] |
| `last_ingest_at` | 2026-09-27T22:18:27Z | 2026-09-27T22:18:27Z |

## Space

- `/api/metrics` respondeu **200 `status: online`** no início do ciclo e apresentou **502 intermitente** depois
  (gateway/cold-start); `GET /health` → 404 (rota inexistente).
- **Build stale** (`0b5bc32`, 2026-09-24): não inclui #052.2.

## Ação recomendada (não executada nesta task)

1. Redeployar o HF Space a partir do HEAD atual (`8cdab7f` ou posterior) para restaurar a telemetria
   run-scoped/graph-scoped — **somente após confirmar HEAD** (é um efeito de build, não de dados).
2. Opcional: registrar issue documental **#052.3 — telemetria run-scoped/graph-scoped no `/api/metrics`** e
   renomear o campo ambíguo `facts` → `concepts` (ou expor `:Fato` como `fact_count`) na próxima janela.
3. Seguir com o backlog cognitivo; **nenhum** bloqueio de dados.

## Confirmações

- Nenhum worker executado · Nenhuma seed alterada · Nenhum treino · Nenhum restore/reset · Workflows intactos
  · Quórum = 3 · Fallback **não** promovido ao grafo.
