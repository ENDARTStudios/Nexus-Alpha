# #054.1 — Rate limiter hardening

**Data:** 2026-09-30 · **Classificação:** `SUCCESS_054_1_RATE_LIMITER_HARDENING_DEPLOYED`

## Gap anterior
- chat já tinha 5/min por IP (sliding window); 429 **sem** `Retry-After`.
- `/api/ingest` autenticado sem limite por identidade.
- `/api/extract` e `/api/simulate` sem limite nenhum.
- Limiter sem bound de memória (`clear_stale_keys` nunca era chamado).

## Mudanças
- **Limites por identidade:** chaves opacas `ip:<host>` / `token:<sha256-prefixo>`
  (`fingerprint_secret()`); `check() → RateLimitDecision(allowed, retry_after_seconds)`.
- **Retry-After:** todo 429 carrega o header (ceil do oldest na janela, mín. 1s).
- **Fingerprint de token:** ingest/extract autenticado usam sha256 truncado —
  token cru nunca vira chave nem entra em log (testado com caplog).
- **Memória bounded:** `max_keys=10_000` por limiter; no teto, purge de
  janelas expiradas e despejo LRU por último hit — crescimento impossível por construção.
- **Limites finais** (calibrados pelo worker, ver relatório de compatibilidade):
  - `/api/chat`: 5/min por IP (inalterado).
  - `/api/extract`: 10/min anônimo por IP; **120/min por token** (worker em rajada).
  - `/api/simulate`: 10/min por IP.
  - `/api/ingest`: **120/min por token** (margem 2x sobre o pior caso estrutural ~60/min).
- `/api/metrics` e `/health` **sem limiter** — telemetria nunca bloqueada.
- Interceptor (>1MB, brute-force) e sanitização de logs inalterados; sem dupla contagem.
- Docs atualizados (API/PRD/ARCHITECTURE/SECURITY_REVIEW/COMPLIANCE/PERFORMANCE/
  ERROR_HANDLING/QA_TESTING) + contagens stale de testes corrigidas (commit separado).

## Limite final de ingest
- **Valor:** 120 req/min por token fingerprint.
- **Evidência/margem:** worker posta N payloads (manifest ≈70 URLs + seeds + GEO)
  em rajada sem delay; 429 não é retentado no worker (só 5xx) → perda de payload.
  Pior caso estrutural ~60/min → 2x = 120 (teto da faixa autorizada 30–120).
  Detalhes: `reports/rate_limiter_worker_compatibility_054_1.md`.

## Segurança
- Token cru não usado como chave (testes: `fingerprint != token`, caplog sem cru).
- Anti-leak clean (rg sobre todos os arquivos commitados: zero hits).
- `git add -A` não usado; artefatos `.autonomous/`/`reports/*.json` alheios unstaged.

## Validação
- **Testes locais:** 721 passed / 20 skipped (suíte completa; +12 testes novos de rate limit).
- **Ruff:** indisponível no ambiente principal (instalação proibida no task) — sem gate de lint no CI; estilo segue o repo.
- **CI:** success nos 3 pushes (`82aa3cc`, `4f40775`, `5b3e8b4`).
- **Deploy:** dry-run OK → upload único (82 arquivos) → Space `RUNNING` @ `7ebdcec`.
- **Métricas vivas preservadas** (`reports/metrics_pre_054_1.json` → `metrics_post_054_1.json`):
  verified=20, fact=412, concept=2023, quorum=3, graph_scoped_gap=0,
  fact_accounting_status=ok, same_scope=0, unaccounted_raw=0,
  publisher_family=3, effective=3, top_invalid=[], fallback_promoted=0,
  hebbian=True → **ALL_CRITERIA_OK**.
- Nota: primeira leitura pós-restart pegou AuraDB hibernado (grafo frio,
  `hebbian=false`); recuperou sozinho em 20s — comportamento durável esperado (DR-1).

## Próximo passo
- **#048.10M.1 — DEFENDEU pilot dry-run, sem worker** (liberado por este SUCCESS).
