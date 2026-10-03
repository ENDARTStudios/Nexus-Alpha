# 054.2.R1 — Boot sequence map (read-only, código em `apps/api`)

**Data:** 2026-10-03 · HEAD `cd2fa8c` · Fonte: leitura de `apps/api/app.py` e `apps/api/src/database/graph_connector.py`

## Entrypoint
`uvicorn app:app` (Dockerfile.hf, porta 7860) → FastAPI com `lifespan` (app.py:326-334):
- se `NEXUS_BOOTSTRAP_SCHEMA` (default true): `await get_graph_connector().ensure_schema()`;
- `ensure_schema` (graph_connector.py:357-369) **engole toda exceção** (`except Exception` → `return False`, só warning) — o app SOBE sempre, mesmo sem Neo4j.

## HTTP readiness
Uvicorn atende **imediatamente após o lifespan**. `/health` é estático `{"status": "ok"}` (app.py:362-364) — **nenhuma checagem de grafo**. Não existe endpoint `/api/ready`.

## Neo4j driver lifecycle
- **Lazy singleton**: `get_graph_connector()` (app.py:98-102) cria o driver na primeira chamada.
- `GraphConnector.__init__` só carrega config (sem conectar). `connect()` (graph_connector.py:335-348) cria o `AsyncGraphDatabase.driver` — o Neo4j driver é lazy: TCP+handshake só acontecem na primeira `session.run()`.
- `connection_timeout=10.0`.

## /api/metrics lifecycle
`/api/metrics` (app.py:367+) → `graph = get_graph_connector()` → `await graph.graph_snapshot(retries=2)`:
- 2 tentativas com **0,5s de sleep entre elas** (graph_connector.py:440-467);
- qualquer exceção em todas as tentativas → retorna `empty` com **`ok: False` e todos os contadores zerados**;
- o endpoint **não distingue**: monta o payload completo com zeros + `hebbian_consistency_check: snapshot["ok"]` e responde **HTTP 200 `status: online`**.

## Hebbian calculation
`cognitive_health.hebbian_consistency_check = snapshot["ok"]` (True só se a query do snapshot teve sucesso) — portanto cold boot → **False transitório**, sem dano real.

## Cache/fallback
- **Nenhum cache de métricas** — cada chamada consulta o grafo.
- **Fallback silencioso**: todos os `count_*`/`graph_snapshot` têm `except Exception → return 0/empty` (availability-over-correctness, por design pós-#052) — a contrapartida é o falso zero em cold boot.
- `/api/metrics` também tem try/except próprio para `verified_fact_domain_counts` (→ `{}`).

## Hipóteses
- **H4 (cold boot do Space) + H5 (transiente do Neo4j/AuraDB pausado) confirmados por 3+ observações**: 1ª leitura pós-restart = zeros/hebbian=False; leituras seguintes (15-20s) = baseline íntegra.
- O gatilho do AuraDB free: pausa por inatividade; a 1ª conexão acorda o cluster (dezenas de segundos), e o retry interno de 2×0,5s é curto demais para cobrir o wake-up.

## Conclusão
O boot-race é **latência de wake-up do AuraDB pausado** encontrando **readiness sem gate**: o Space atende HTTP e produz métricas "online com zeros" antes de a 1ª query bem-sucedida confirmar o grafo. Não há estado inconsistente real — só janela transitória sem sinalização.
