# 054.2.R2 implementation report

## Resumo
Patch aditivo implementado: graph_ready/boot_reason/booting em /api/metrics +
backoff formalizado no cliente (--wait-ready). Sem merge, sem deploy.

## Mudanças
- apps/api/app.py: status "booting" vs "online"; graph_ready bool; boot_reason.
- apps/api/scripts/check_space_telemetry.py: WAIT_MAX_ATTEMPTS=8, delays 5-30s,
  classify_readiness (COLD_BOOT/DRIFT_REAL/READY/INDETERMINATE), --wait-ready.
- Nenhum campo existente removido. Nenhuma cognição/seed/alias/workflow alterados.

## Testes
- tests/test_readiness_graph_ready_054_2_r2.py: T1-T6 (4 endpoint + client).
- Suíte: 813 passed / 20 skipped / 0 failed (antes do patch: 813 com fakes antigos).

## Deploy
- NÃO executado. PR draft aberta para review do Operador.
