# 🏛️ Arquitetura — Nexus-Alpha (docs)

> Este documento é a visão operacional por camadas. O desenho macro do pipeline
> (fluxos ASCII, protocolo zero-trust, memória durável) vive em
> [`ARCHITECTURE.md` na raiz](../ARCHITECTURE.md) e permanece canônico — aqui
> está o mapa de módulos, contratos e fronteiras que os agentes devem respeitar.

**Última revisão:** 2026-09-23 · **Estado:** v1.12.0-beta concluída / freeze v1.13.0

---

## 1. Camadas e responsabilidades

| Camada | Diretório | Responsabilidade | Não faz |
|---|---|---|---|
| **Miner** | `src/miner/` | Coleta (scraping assíncrono httpx), anti-bloqueio, reputação de domínio, quarentena de rejeitados, seeds curados, reach opcional (Jina/RSS/yt-dlp) | Promover fatos; tocar o grafo diretamente |
| **Cognition** | `src/cognition/` | Extração de triplas (spaCy + fallback + LLM canônico), refinamento determinístico (canonicalizer, predicate_mapper, span_validator), RAG, GraphRAG, chat, reflexão noturna | Alterar quórum; promover fato por embedding |
| **Database** | `src/database/` | Conectores assíncronos: `graph_connector.py` (Neo4j, Cypher puro sem APOC) e `vector_connector.py` (Qdrant + fallback in-memory) | Conter lógica de negócio |
| **Security** | `src/security/` | Triangulação, sanitização de logs, interceptor (>1MB, brute-force), rate limiter (5 req/min no `/api/chat`) | Logging não-sanitizado |
| **Brain** | `src/brain/` | Memória cognitiva working/episódica/semântica + consolidação Hebbiana (`memory.py`, `regions.py`) | Persistir working memory (é efêmera por design) |
| **Simulation** | `src/simulation/` | `SwarmSimulator` (dinâmica de opinião determinística por seed) | Alterar o grafo |
| **Training** | `src/training/` | Export de fatos verificados → Alpaca/JSONL + config LoRA (opt-in, sem torch no runtime) | Entrar no runtime principal ou CI |
| **Frontend** | `src/frontend/` + `src/app/` | Next.js 14: Dashboard, BrainPanel (read-only), KnowledgeGraph, ChatWidget; proxy Vercel em `src/app/api/nexus/[...path]/route.ts` | Escrever no backend (read-only exceto chat/ingest) |

## 2. Contratos de dados

### NexusPayload (JSON-LD) — contrato entre miner e ingest
```
source_url · timestamp · domain_score · extracted_entities[]
```
Todo payload passa por `interceptor.py` (≤1MB), autenticação
(`X-Nexus-Token` + Bearer HF) e `refine_triple` antes de tocar o Neo4j.

### Chave de fato
`fact_hash = sha256(subject|predicate|object)` com normalização
(strip por campo + lower) — idempotência de episódios via MERGE
`(fact_hash, day)`; chave canônica de `:Fato` calculada no ingest
(#041: fold NFKD + artigos + hífen).

### Predicados
Vocabulário controlado ≤ 30 entradas (`predicate_mapper.py`), caixa alta,
motivos de rejeição tipados (`ok`, `unmapped_predicate`, `invalid_predicate`,
`numeric_predicate`, `url_or_code_predicate`, `stopword_predicate`,
`nonverbal_predicate`, `modal_predicate`, `ambiguous_predicate`,
`self_loop`, `missing_entity` + motivos do `span_validator`).

## 3. Fronteiras de deploy

```text
┌─ GitHub Actions (worker) ── cron 6h ── scripts/worker_cycle.py
│        │ POST /api/ingest (X-Nexus-Token)
┌─ Hugging Face Space (core) ── app.py FastAPI :7860 ── Dockerfile.hf
│        ├── Neo4j AuraDB (grafo, durável)
│        └── Qdrant Cloud (vetores 384-dim, fallback in-memory)
┌─ Vercel (proxy + frontend) ── Next.js /api/nexus/[...path] → Space privado
└─ Kaggle (opt-in) ── fine-tuning LlamaFactory externo
```

- O Space é **privado**: o frontend público nunca fala direto com ele;
  o proxy server-side injeta `NEXUS_SPACE_URL` + `HF_TOKEN` + `NEXUS_API_TOKEN`
  (nunca prefixo `NEXT_PUBLIC_`).
- `Dockerfile` instala apenas `requirements-hf.txt` (lite) — LlamaFactory fica
  inerte no Space por construção.

## 4. Degradação graciosa (matriz)

| Falha | Comportamento | Evidência no payload/métricas |
|---|---|---|
| Neo4j indisponível | ingest não grava; resposta `demo-memory` + `failed`/`degraded` (#058.4; flag `NEXUS_ALLOW_DEMO_FALLBACK` default `false`) | `db_status: "demo-memory"` |
| Qdrant indisponível | vetores in-process | `vector_connector` fallback |
| `/api/brain/episodes` sem grafo | leitura da memória volátil | campo `source: "volatile"` |
| Fato sem quórum | **quarentena**, nunca descarte | `quarantine` em `/api/metrics` |
| spaCy ausente | extração heurística (`extractor.py`) | testes rodam sem spaCy (CI lite) |
| LLM não configurado | resposta extrativa no chat | zero dependência externa |

## 5. Regras de evolução da arquitetura

1. **Ponto único de alavanca:** transformações determinísticas de triplas
   acontecem no choke point `/api/ingest → refine_triple → chave do Neo4j`.
   Nada no Cypher dobra acentos ou remove artigos.
2. **Cypher puro sem APOC** (portabilidade AuraDB Free).
3. **1 item por commit**, staging explícito (sem `git add -A`) — ver [`RULES.md`](./RULES.md).
4. Qualquer novo módulo precisa de testes que rodem no CI **lite**
   (`requirements-dev.txt`, sem torch/transformers/spacy).
5. Freeze `v1.13.0`: nenhuma mudança de infraestrutura até a observabilidade
   confirmar estabilidade da retenção automática.

## 6. Diagramas detalhados

- Pipeline macro + chat + enxame: [`../ARCHITECTURE.md` raiz, seções 1–2](../ARCHITECTURE.md).
- Modelo cognitivo e limites: [`MEMORY.md`](./MEMORY.md).
- Métricas de saúde: [`ANALYTICS.md`](./ANALYTICS.md) e [`MONITORING.md`](./MONITORING.md).
