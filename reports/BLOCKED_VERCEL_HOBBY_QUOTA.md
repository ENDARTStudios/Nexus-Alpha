# BLOCKED_VERCEL_HOBBY_QUOTA

**Data:** 2026-09-28
**Repo:** `ENDARTStudios/Nexus-Alpha`
**HEAD (main):** `d362dcd`
**Classificação:** `SUCCESS_VERCEL_DEGRADED_MODE` (Vercel **non-required**)

## Sintoma

- Deploy/preview/production da Vercel falhou ou está indisponível para o projeto `nexus-alpha`.
- Causa provável: plano Hobby / quota de deployments / limite diário.

## Impacto

- URL pública da Vercel não atualizada.
- Aceite visual dependente exclusivamente da Vercel fica suspenso.
- Núcleo cognitivo **NÃO** bloqueado (HF Space + CI `required` saudáveis).

## Evidência (sanitizada, sem segredos)

- **Projeto Vercel:** `nexus-alpha` (scope `end-art-studios`).
- **Commit status `Vercel` no `main` HEAD `d362dcd`:**
  - `state`: `failure`
  - `description`: `Deployment rate limited — retry in 24 hours.`
  - `created_at`: `2026-09-28T00:50:07Z`
  - `required?`: **NAO** — branch `main` **sem proteção** (`GET /repos/ENDARTStudios/Nexus-Alpha/branches/main/protection` → HTTP 404 `Branch not protected`).
- **Check-runs (main):** `validate-project=success` — workflow `Nexus-Alpha Quality & Security Gate`.
- **Workflows do repo:** `ai-cron.yml`, `ai-validation.yml`, `db-backup.yml` — **nenhum** faz deploy Vercel.
- **HF Space** (`/api/metrics`) → HTTP 200, `status: online`:
  - `facts` = 1894
  - `verified_facts_domain_independent` = 11
  - `duplicate_cross_domain` = 23
  - `unaccounted_raw` = 0
  - `fallback_promoted_to_graph` = 0
  - `top_invalid_predicates` = []
  - `verification.quorum` = 3
  - `duplicate_canonical_occurrences` = 2733 · `canonical_to_fact_gap` = -21
  - Nota: `GET /health` → HTTP 404 (rota inexistente no Space); saúde confirmada via `/api/metrics`.
  - Campos `run_scoped_gap` / `graph_scoped_gap` **não** existem no payload atual do `/api/metrics`.
- **Testes locais:** `pytest -q` → `490 passed, 39 skipped` (~40s).
- **Lint estático local:** `ruff check .` → **70 achados pré-existentes** (E402/F401/F841/E702) em `scripts/`, `.autonomous/`, `dashboard/`, `src/`, `tests/`; **não** é executado pelo CI e **não** bloqueia.
- **Frontend local:** `npm run build` (Next.js 14.2.35) → **OK** (4 páginas + proxy dinâmico).
  - `npm run lint` / `npm run test` → scripts inexistentes (`exit 1`).

## Decisão operacional

- Continuar backlog cognitivo em **modo Vercel-degradada**.
- **Não** pagar upgrade.
- **Não** alterar workflows.
- **Não** forçar deploy.
- **Não** usar a Vercel como gate para tarefas de `miner`/`cognition`/`worker`/`audit`.

## Ação do Operador, se quiser restaurar a Vercel

1. Abrir o painel da Vercel.
2. Verificar quota/plano/mensagem exata de erro.
3. Decidir entre:
   - aguardar o reset de quota;
   - reduzir deploys/preview;
   - migrar o frontend para outro hosting estático gratuito;
   - upgrade pago (**apenas** por decisão humana).
4. Se necessário ajustar `required checks`, fazer isso fora do Doer, sem alterar código de produção para mascarar a falha.
