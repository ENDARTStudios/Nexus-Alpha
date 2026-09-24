# 🔌 API — Nexus-Alpha (FastAPI `app.py`)

Core FastAPI executado no Hugging Face Space (porta **7860**), acessível
publicamente **apenas** via proxy Vercel `/api/nexus/[...path]` (o Space é
privado). Autenticação de ingest: header `X-Nexus-Token` + Bearer HF.

Referência dos endpoints (rota base: `/`):

---

## Sistema

### `GET /`
Descrição do serviço (health básico textual).

### `GET /health`
Liveness para o Space e para o proxy. **200** mesmo em degradação —
o corpo informa o estado (`db_status`).

### `GET /api/metrics`
Agregado de observabilidade. Blocos (detalhes em [`ANALYTICS.md`](./ANALYTICS.md)):
`cognitive_health` (`episodic_persistence_rate`, `hebbian_consistency_check`,
`retention_pressure`) · `extraction_quality` (`rejection_reasons`,
`top_unmapped_predicates`, `top_invalid_predicates`,
`duplicate_canonical_triples` legado, `fallback_events`,
`masked_extraction_failures`) · `fallback_health` (`demo_memory_events`,
`masked_extraction_failures`, `fallback_promoted_to_graph`,
`sources_with_zero_entities`, `allow_demo_fallback`; #058.4) ·
`verification` (`quorum`,
`facts_with_multi_domain`, `max_domain_confirmations`,
`verified_facts_domain_independent`) · `ingestion_accounting` (`raw_triples`,
`canonical_triples`, `distinct_canonical_keys`, `duplicate_*`,
`persisted_facts`, `canonical_to_fact_gap`, `accounting_mode`, timestamps) ·
`quarantine`.

## Ingestão e extração

### `POST /api/ingest`
**Autenticado.** Recebe payload(s) de mineração (contrato NexusPayload:
`source_url`, `timestamp`, `domain_score`, `extracted_entities[]`) →
`refine_triple` determinístico → grafo/quarentena.
- `interceptor.py`: payload > 1MB → rejeitado; brute-force > 10 → bloqueado.
- Degradação: sem Neo4j responde com `db_status: "demo-memory"`; **nunca**
  `partial_success` com `entities_processed=0` (#058.4) — status vira
  `degraded` (se `NEXUS_ALLOW_DEMO_FALLBACK=true`) ou `failed` (default
  produção). Flag `NEXUS_ALLOW_DEMO_FALLBACK` default `false`.
- Resposta inclui contadores de ingest da requisição e
  `masked_extraction_failure` / `allow_demo_fallback`.

### `POST /api/extract`
Extração canônica de triplas a partir de texto (usa
`LLMCanonicalExtractor` se LLM configurado; sem LLM, extrator local).
Útil para diagnóstico de extração sem minerar.

## Cérebro

### `GET /api/brain/stats`
Contadores cognitivos derivados do grafo (working/episódica/semântica,
hebbian, consolidados) — contrato normalizado consumido pelo `BrainPanel`.

### `GET /api/brain/episodes`
Episódios duráveis. Lê **Neo4j** primeiro; fallback volátil com
`source: "neo4j"|"volatile"` no payload.

### `POST /api/brain/activate`
Ativa item na working memory (7 slots, decaimento).

### `POST /api/brain/episode`
Registra episódio (`fact_hash + day`, MERGE idempotente; repetição → `replays`).

### `POST /api/brain/consolidate`
Consolida episódios → semântica + poda de retenção (30d/10k).
> Não criar cron para isto: o worker de 6h já consolida (decisão v1.12).

## Consulta

### `GET /api/graph/topology`
Nós/arestas para visualização (`KnowledgeGraph`/`react-force-graph-2d`).

### `POST /api/chat`
Chat conversacional. Recuperação híbrida: `search_context` (Neo4j) +
`query_similarity` (Qdrant) + GraphRAG (subgrafos 1–2 saltos), histórico
curto por `session_id`. Geração **extrativa por padrão**; LLM opcional via
`NEXUS_LLM_BASE_URL`. Rate limit **5 req/min/IP** (429 acima).

### `POST /api/simulate`
`SwarmSimulator`: seed determinística sobre topologia do grafo ou
`search_context(tópico)`; agentes com stance/influência; ≤50 rodadas de
bounded confidence; retorna consenso, polarização, veredito, confiança,
clusters, trajetória.

---

## Convenções transversais

1. **Erros:** mensagens curtas em pt-BR; sem stack trace/segredo no corpo
   (sanitização por `log_sanitizer.py`). Códigos: 401/403 auth · 413 payload
   grande · 429 rate limit/brute-force.
2. **Degradação nunca é 500:** indisponibilidade de banco muda o **corpo**
   (`db_status`, `source`), não derruba o endpoint.
3. **CORS:** `NEXUS_CORS_ORIGINS` / `NEXUS_CORS_ORIGIN_REGEX`
   (default: `https://.*\.vercel\.app`).
4. **Schema bootstrap:** `NEXUS_BOOTSTRAP_SCHEMA=true` cria índices no boot.
5. Extensões de endpoint: seguir [`ERROR_HANDLING.md`](./ERROR_HANDLING.md) e
   registrar mudança de contrato em `docs/API.md` no mesmo PR.
