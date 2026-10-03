# 054.2.R1 — Opções de readiness patch (NÃO IMPLEMENTADAS — apenas proposta)

## R1 — Endpoint `/api/ready` separado
- 200 só quando: driver conectado + query mínima OK + hebbian não-ambíguo.
- Vantagem: separa liveness (`/health`) de readiness. Risco: altera runtime/app; exige versionar contrato.
- **Quando escolher:** se Operador quiser gate formal para CI/monitoring.

## R2 — `/api/metrics` com estado explícito de boot (RECOMENDADA — aditiva)
- Quando `graph_snapshot()["ok"] = False`: adicionar `"graph_ready": false, "boot_state": "neo4j_waking"` ao payload (zeros continuam, mas sinalizados).
- Contrato aditivo — consumidores atuais (dashboards, scripts) que leem contadores não quebram; novos consumidores checam `graph_ready`.
- Risco: baixo (campo novo).

## R3 — Warm-up interno no startup
- Após `ensure_schema`, executar a query do snapshot com retry/backoff maior (ex.: 6×2s) antes de marcar pronto.
- Risco: atrasa boot se Neo4j indisponível de verdade; não remove o falso zero se o wake-up demorar > window.

## R4 — Cliente-side padronizado (`check_space_telemetry` + diagnose script) — JÁ EXISTE COMO PROVA
- Detectar zeros+hebbian=False+online → warm-up com backoff antes de declarar drift.
- Prova: este ciclo (R1) e os anteriores usaram exatamente esse padrão com sucesso.
- Risco: mascarar problema real se usado como única resposta — sempre registrar a ocorrência.

## R5 — Cache de última métrica saudável com `stale=true`
- Serve última baseline boa durante boot. Risco: pode enganar se `stale` não for explícito; adiciona estado em memória.
- **Não recomendada** para o tamanho do problema.

## Recomendação conservadora (para decisão futura, NÃO implementada neste ciclo)
1. **R2 imediato** quando autorizado (aditivo, baixo risco, resolve a ambiguidade).
2. **R4 já em vigor informalmente** (padrão warm-up dos ciclos) — formalizar em `check_space_telemetry.py` no mesmo task.
3. **R1/R3** apenas se o Operador quiser gate formal de readiness.
