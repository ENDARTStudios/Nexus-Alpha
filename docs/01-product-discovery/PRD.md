# 📋 PRD — Documento de Requisitos de Produto (Nexus-Alpha)

**Versão:** 2.0 · **Data:** 2026-09-23 · **Estado:** alinhado a `v1.12.0-beta` concluída e freeze `v1.13.0`

---

## 1. Visão

Construir uma **inteligência artificial autônoma** que minera a web de forma
semântica, transforma conteúdo bruto em um **grafo de conhecimento verificado**
e evolui continuamente — **sem custo de infraestrutura** (Hugging Face Spaces,
GitHub Actions, Qdrant Cloud free tier, Neo4j AuraDB Free).

O produto final é um **cérebro digital consultável**: um chatbot e um painel
de monitoramento que respondem perguntas apenas com fatos corroborados por
**3+ domínios independentes** — nada entra no conhecimento sem passar pelo
protocolo de verificação.

## 2. Problema

LLMs genéricos alucinam e não expõem a origem do que dizem. A Nexus-Alpha
ataca isso na raiz:

1. **Ruído de entrada:** a web mistura factóide, opinião e desinformação.
2. **Fontes não independentes:** 4 URLs do mesmo domínio não corroboram nada (#049).
3. **Fragmentação semântica:** o mesmo fato aparece com superfícies distintas
   ("Clube" vs "Club", PT vs EN) e nunca atinge quórum (#048, evidência em produção).

## 3. Personas

Ver detalhes em [`DEFINE_THE_USER.md`](./DEFINE_THE_USER.md).

| Persona | Necessidade | Superfície |
|---|---|---|
| **Operador (ENDARTStudios)** | governar o ecossistema e auditar a saúde cognitiva | Dashboard + `/api/metrics` |
| **Visitante do site** | perguntar e receber respostas com base em fatos verificados | ChatWidget (`/api/chat`) |
| **Agente autônomo (worker)** | executar o ciclo de mineração a cada 6h sem intervenção | `scripts/worker_cycle.py` |
| **Pesquisador de KG** | exportar fatos verificados para treino (SFT/LoRA) | `scripts/train_lora.py` (opt-in) |

## 4. Funcionalidades (estado atual)

### F1 — Mineração semântica autônoma ✅
Worker a cada 6h (GitHub Actions) coleta seeds + clusters curados
(`config/seed_clusters.yaml`), aplica `AntiBlockSystem` (UA/Referer rotativos,
delay dinâmico), extrai triplas `{sujeito, predicado, objeto}` (spaCy PT +
fallback heurístico) e envia via `POST /api/ingest` autenticado.

### F2 — Verificação anti-fake-news ✅
`TriangulationFilter` + `SecurityProtocol`: reputação de domínio (allowlist
curada 0.85; `.org`/`.edu`/`.gov` 0.9; desconhecidos 0.6 → quarentena;
baixa-confiança 0.4) + quórum de **3 domínios independentes** (contagem por
host desde #049) para promover `:Fato.verificado`.

### F3 — Memória cognitiva persistente ✅ (v1.12.0-beta)
Working (7 slots, RAM) → Episódica (`:Episodio` durável no Neo4j, MERGE
idempotente por `fact_hash + day`, retenção 30d/10k) → Semântica (consolidação
Hebbiana). Episódios sobrevivem a restarts do Space (evidência: 422 episódios).

### F4 — Atendimento conversacional ✅
`POST /api/chat`: recuperação híbrida (Neo4j `search_context` + Qdrant
`query_similarity` + GraphRAG subgrafos 1–2 saltos), geração **extrativa por
padrão** (zero alucinação) com LLM opcional via `NEXUS_LLM_BASE_URL`.
Rate limit 5 req/min/IP.

### F5 — Painéis de monitoramento ✅
Dashboard Streamlit (`dashboard/app.py`) + frontend Next.js (Dashboard,
BrainPanel read-only, KnowledgeGraph com `react-force-graph-2d`, ChatWidget).
Saúde cognitiva em `/api/metrics`.

### F6 — Simulação de enxame ✅
`POST /api/simulate` → `SwarmSimulator`: dinâmica de opinião multi-agente
determinística (`seed`), relatório de consenso/polarização/veredito.

### F7 — Fine-tuning opt-in ✅ (v1.14.0)
Export de fatos verificados → dataset Alpaca/JSONL + config LoRA/SFT para
LlamaFactory externo (Kaggle). Fora do runtime e do CI.

## 5. Requisitos não funcionais

| Requisito | Meta | Estado |
|---|---|---|
| Custo de infraestrutura | R$ 0 (free tiers) | ✅ |
| Segurança de segredos | zero credenciais no código; sanitizeador de logs | ✅ gate anti-leak |
| Disponibilidade do core | degradação graciosa sem Neo4j/Qdrant (`demo-memory`) | ✅ |
| Suíte de testes | verde em todo push (`pytest -q`, ~195 testes) | ✅ gate |
| Latência do chat | resposta < 3s p95 (extrativo, grafo quente) | 🟡 medir |
| Cross-domain verificado | `facts_with_multi_domain > 0` | ❌ bloqueado por equivalência semântica (ver [`RESEARCH.md`](./RESEARCH.md)) |

## 6. Fora de escopo (explícito)

- Serving/merge de adapter fine-tuned; integração do LoRA com `llm_provider.py`.
- LLM ou embeddings como **promotores** de fatos (embedding só sugere — regra de ouro).
- Redução do quórum de triangulação (fixo em 3).
- Alterações de infraestrutura durante o freeze `v1.13.0`.

## 7. Métricas de sucesso

Ver [`ANALYTICS.md`](./ANALYTICS.md) para definições completas. Resumo:

- `cognitive_health.episodic_persistence_rate` ≥ 0.95
- `verification.verified_facts_domain_independent` > 0 (meta do ciclo)
- `ingestion_accounting.canonical_to_fact_gap` ≤ 5
- Suíte de testes 100% verde + anti-leak limpo em todo push.

## 8. Roadmap resumido

Detalhado em [`ROADMAP.md`](./ROADMAP.md). Próximo marco: quebrar o gargalo
de **equivalência semântica entre fontes** (entity linking diagnóstico #047 /
item 2) — sem tocar infraestrutura.
