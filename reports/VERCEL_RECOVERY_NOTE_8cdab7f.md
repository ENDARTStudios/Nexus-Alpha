# VERCEL_RECOVERY_NOTE_8cdab7f

**Data:** 2026-09-28
**Repo:** `ENDARTStudios/Nexus-Alpha`

## Recuperação da Vercel

Durante o ciclo de diagnóstico, o commit status da Vercel apresentou falha por rate limit no plano Hobby:

- context: `Vercel`
- state: `failure`
- description: `Deployment rate limited — retry in 24 hours.`
- commit diagnosticado: `d362dcd`
- created_at: `2026-09-28T00:50:07Z`

Posteriormente, no commit `8cdab7f`, o status da Vercel mudou para `success`:

- context: `Vercel`
- state: `success`
- description: `Deployment has completed`
- created_at: `2026-09-28T16:46:13Z`

## Decisão mantida

- `VERCEL_RECOVERED_NON_REQUIRED`.
- A Vercel permanece **non-required** (branch `main` sem proteção; o status `Vercel` não bloqueia merge/push).
- O núcleo do Nexus-Alpha continua validado por CI required (`validate-project`), testes locais, HF Space e auditorias read-only.
- Deploy público da Vercel **não** é gate para tarefas cognitivas enquanto o Operador não decidir o contrário.
