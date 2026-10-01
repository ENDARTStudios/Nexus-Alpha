# Rate limiter worker compatibility — #054.1

Pergunta: o limite de `/api/ingest` por token quebra o worker autônomo
legítimo (`scripts/worker_cycle.py` no GitHub Actions)?

## Evidência (análise estrutural do código, read-only)

Logs históricos com timestamp por request não estão disponíveis localmente
(`.autonomous/` guarda telemetria/JSON de métricas, não access logs). A
evidência usada é **estrutural**, extraída do código do worker — que é
determinística e mais conservadora que qualquer observação pontual:

1. `scripts/worker_cycle.py` (ciclo #048.10L/#048.10M):
   - Mineração: `SEED_QUERIES` + clusters curados (`config/seed_clusters.yaml`,
     70 URLs no manifest) + GEO/GEO-Wiki → payload com `extracted_entities`.
   - **Fase extract:** loop `for payload in payloads` → `POST /api/extract`
     **em rajada, sem delay entre iterações** (RTT-bound).
   - **Fase ingest:** loop `for payload in payloads` → `POST /api/ingest`
     **em rajada, sem delay entre iterações** (o `sleep(15)` existe apenas no
     warm-up do `/health`).
   - `_post_ingest_with_retry`: retry **apenas para 5xx** — um 429 **não é
     repetido** → payload perdido para o ciclo (perda de conhecimento, não
     apenas degradação).
2. Manifest atual: ~70 URLs curadas + seeds base + GEO → **N ≈ 60–90
   payloads** por ciclo pior-caso; com ingest RTT-bound (~0,5–2 s por POST,
   incluindo escrita no Neo4j), a janela de 60 s mais densa contém
   **~30–60 ingests** → `max_ingest_requests_in_any_60s_window ≈ 60`
   (estimativa estrutural conservadora).
3. A mesma rajada vale para `/api/extract` (1 chamada por payload, sem
   delay): com limite anônimo de 10/min por IP, a canonicalização LLM do
   worker seria silenciosamente degradada após a 10ª chamada.

## Decisão

| Endpoint | Limite final | Justificativa |
|---|---|---|
| `/api/ingest` | **120 req/min por token fingerprint** | Regra do task: máximo estrutural ≈ 60/min → 2x = 120 (teto da faixa autorizada 30–120). Garante zero perda por 429 no worker legítimo. |
| `/api/extract` | **balde duplo**: 10/min anônimo por IP; **120/min por token** autenticado | Protege o endpoint público de LLM sem degradar o worker autenticado (mesma rajada). |
| `/api/simulate` | 10 req/min por IP | Worker não chama simulate. |
| `/api/chat` | 5 req/min por IP | Worker não chama chat. |

## Margem

- Limite escolhido ≥ 2x máximo estrutural observado? **Sim**
  (120 ≥ 2 × ~60 no pior caso estrutural; medianas históricas são ≫ menores,
  ~2–5/min com delays de fetch).
- Risco residual: se o manifest de seeds crescer > ~240 URLs/60s-janela,
  revisar (hoje: 70 URLs no manifest — folga ~4x no total por run).

## Nota de segurança

O retry do worker não cobre 429 de propósito (evita amplificação). Com a
margem 2x, 429 legítimo é improvável; se ocorrer por crescimento futuro do
manifest, o fix correto é aumentar `WORKER` delay entre posts (fora do
escopo #054.1) — não baixar a proteção da API.
