# 054.2.R1 — Hipóteses de root cause (boot-race)

## H1 — HTTP server starts before Neo4j driver/session is ready
- **A favor:** lifespan roda `ensure_schema` (engole exceção); uvicorn sobe sempre.
- **Contra:** o driver é lazy — o que falha não é o driver, é a 1ª query durante o wake-up do AuraDB.
- **Veredito:** parcialmente verdadeira (é o H4/H5 com outro nome); não é a causa final.
- **Probabilidade:** média.

## H2 — /api/metrics catches Neo4j exception and returns zeros silently ✅ CONFIRMADA POR CÓDIGO
- `graph_snapshot` (graph_connector.py:461-467): `except Exception` → `empty` com `ok: False`.
- `/api/metrics` não distingue "grafo vazio" de "grafo inalcançável".
- **Evidência a favor:** observações de 3+ ciclos (zeros → baseline em 15-20s, sem escrita no meio).

## H3 — hebbian check fails during cold connection and is cached as false
- **Contra:** **não há cache** — cada `/api/metrics` re-consulta o grafo. O False é transitório e some na leitura seguinte (comprovado: hebbian=True 15s depois, sem nenhuma intervenção).
- **Veredito:** refutada.

## H4 — Space scale-to-zero/cold boot ✅ CONFIRMADA (gatilho)
- HF Spaces com perfil de baixo uso + AuraDB free tier **pausa por inatividade**; o restart do Space ou a janela de inatividade do AuraDB criam a corrida.
- **Evidência:** 3 ocorrências concentradas logo após restart/inatividade (worker incident, R3, R1).

## H5 — Transient Neo4j error after restart causes temporary zeros ✅ (é o mecanismo de H4)
- AuraDB free responde à 1ª conexão durante o resume; `graph_snapshot` retries=2×0,5s é curto demais.
- **Evidência:** zeros na amostra 1 e baseline na amostra 2 (15s), sem nenhuma escrita no meio.

## H6 — Metrics endpoint has no readiness gate ✅ CONFIRMADA POR CÓDIGO
- `/health` estático; `/api/metrics` não tem gate — qualquer falha vira payload de zeros com HTTP 200.
- É a **lacuna estrutural** que permite o falso diagnóstico.

## H7 — Unknown
- Refutada por eliminação (H2/H4/H5/H6 cobrem todas as observações).

## Síntese da causa raiz
```
AuraDB pausado (inatividade) + Space restart
  → 1ª session.run falha transitória
  → graph_snapshot engole (2 retries de 0,5s — curto p/ wake-up de dezenas de segundos)
  → /api/metrics serve zeros + hebbian=False com HTTP 200
  → consumidor interpreta como drift/dano (falso diagnóstico)
  → 15-20s depois o wake-up completa e a baseline volta — sem nenhuma intervenção
```

## Correção mínima por hipótese
| Hipótese verdadeira | Patch mínimo | Risco |
|---|---|---|
| H2/H4/H5/H6 | **R2**: `graph_ready` explícito no payload quando `snapshot["ok"]=False` (aditivo) | baixo |
| H4/H5 (mitigação de leitura) | **R4**: `check_space_telemetry` detecta zeros+hebbian=False+online e faz warm-up com backoff antes de declarar drift | baixo (não mascarar falha real) |
| (estrutural futuro) | **R1**: `/api/ready` separado · **R3**: warm-up interno pós-ensure_schema com retry bounded | médio |
