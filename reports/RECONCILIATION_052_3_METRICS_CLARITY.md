# #052.3 — Metrics clarity and telemetry restoration

## Status

`PARTIAL_052_3_CODE_READY_SPACE_STALE`

## HEAD

- inicial: `3ddadac`
- final: `9e495db` (código) + commit de docs deste relatório

## Commits

- `9e495db` — `fix(observability): clarify concept/fact counts and expose scoped gaps in metrics`
- (docs) — `docs(observability): record #052.3 metrics clarity and telemetry restoration`

## CI

- `validate-project` (Nexus-Alpha Quality & Security Gate) — ver seção "Commit/push status".

## Space redeploy

- attempted: **true** (diagnóstico)
- method: **not possible** — `huggingface_hub` ausente, `hf`/`huggingface-cli` ausentes;
  nenhum workflow faz deploy do Space. Não foram instaladas dependências.
- result: runbook gerado em `reports/BLOCKED_052_3_SPACE_REDEPLOY.md`.

## Payload before (`metrics_before.json`)

- `status`: online
- `facts` (legado): 1894
- `concept_count`: **absent**
- `fact_count`: **absent**
- `ingestion_accounting.run_scoped_gap`: **absent**
- `ingestion_accounting.graph_scoped_gap`: **absent**
- `ingestion_accounting.duplicate_cross_domain`: 23
- `verification.verified_facts_domain_independent`: 11
- `verification.facts_with_multi_domain`: 12
- `extraction_quality.top_invalid_predicates`: []
- `fallback_health.fallback_promoted_to_graph`: 0
- `ingestion_accounting.unaccounted_raw`: 0

## Payload after

- **Pendente de redeploy do Space** (não foi possível executar localmente).
- Esperado após redeploy: `concept_count=1894`, `fact_count=335`, `run_scoped_gap` presente,
  `graph_scoped_gap` presente, demais valores inalterados.

## Mudança de código (escopo mínimo)

`app.py` (`/api/metrics`):
- manteve `facts` (legado/compatibilidade);
- adicionou `concept_count` (`snapshot["concepts"]`);
- adicionou `fact_count` (`snapshot["facts"]`, i.e. `:Fato`/`persisted_facts`);
- adicionou `metric_glossary` (rótulos).
- **Não** alterou verificação, quórum, ingest ou extração. `run_scoped_gap`/`graph_scoped_gap` já eram
  emitidos por `_ingest_accounting.snapshot()` — a ausência no payload é build stale, não regressão.

`tests/test_app_metrics.py` (novo): 5 testes — legado preservado, `concept_count`/`fact_count`,
`run_scoped_gap`/`graph_scoped_gap`, contrato de verificação/qualidade, glossary e anti-leak.

## Testes / lint

- `pytest tests/test_app_metrics.py` → **5 passed**
- `pytest -q` (suíte completa) → **495 passed, 39 skipped**
- `ruff check app.py tests/test_app_metrics.py` → **All checks passed**
- `ruff check .` → 70 achados **pré-existentes** (não bloqueante; não rodado no CI) — nenhum novo introduzido.

## Classification

`PARTIAL_052_3_CODE_READY_SPACE_STALE` (Cenário B).

## Next step

Retomar **#059E/#048.10F** somente após o redeploy do Space confirmado (telemetria estável).
Até lá, usar `reports/RECONCILIATION_059E_METRICS_JUMP.md` como leitura não ambígua das métricas.
