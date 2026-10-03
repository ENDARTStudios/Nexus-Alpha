# 054.2.R1 — Plano de teste mínimo (para o task futuro de implementação)

## T1 — Sem zeros silenciosos quando driver não pronto
Dado driver não conectado (Neo4j mock que falha), `graph_snapshot()` retorna `ok: False`;
`/api/metrics` expõe `graph_ready: false` (opção R2) — nunca um payload que pareça baseline vazia.

## T2 — Contrato do estado de boot
Payload contém `graph_ready` (bool) sempre; durante cold boot: `graph_ready=false` +
contadores zerados + `hebbian_consistency_check=false`; pós-wake-up: `graph_ready=true` + baseline.

## T3 — Warm-up: 1ª chamada booting → 2ª baseline
Com Neo4j fake que falha as 2 primeiras queries e succeed na 3ª, o consumidor com
backoff (padrão do diagnose) retorna baseline na 3ª tentativa.

## T4 — Cliente (check_space_telemetry/diagnose script)
`classify_sample` distingue `cold_boot_zeros` de `degraded` de `healthy`;
`summarize_timeline` conclui `BOOT_RACE_CONFIRMED` só com cold→healthy;
não declara drift em cold boot transitório. (Já implementado neste ciclo — 11 testes.)

## T5 — Regressão
Nenhuma mudança de quórum; nenhuma escrita; nenhum ingest; métricas legadas
preservadas (payload aditivo).

## T6 — CI-safe (D11)
Nenhum import de dotenv/urllib/httpx antes de `main()` nos scripts de diagnóstico;
testes offline passam sem `.env` e sem Space online.
