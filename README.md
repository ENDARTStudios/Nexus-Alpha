# Nexus-Alpha — Ecossistema Autônomo de IA

> **Repositório privado — ENDARTStudios**  
> Sprint governada via `SPRINT.md` (v1.1.0-alpha) | CI `.github/workflows/ai-validation.yml`

---

## 📁 Estrutura (monorepo `apps/`)

```
nexus-alpha/
├── apps/
│   ├── api/                 ← Backend Python (FastAPI + mineração + grafo)
│   │   ├── app.py           ← core FastAPI (HF Space, porta 7860)
│   │   ├── src/             ← miner/ cognition/ database/ security/ brain/ ops/ simulation/ training/
│   │   ├── config/          ← settings.yaml, seed_clusters.yaml, security_policies.json
│   │   ├── tests/           ← suíte pytest (rodar de apps/api)
│   │   ├── scripts/         ← worker_cycle.py, deploy/audit/probe/validate
│   │   ├── dashboard/       ← Streamlit (operador)
│   │   └── requirements*.txt
│   └── web/                 ← Frontend Next.js 14 (Vercel)
│       ├── src/app/         ← App Router + proxy /api/nexus
│       ├── src/frontend/    ← ChatWidget, BrainPanel, KnowledgeGraph
│       └── package.json / vercel.json / public/
├── docker-compose.yml       ← nexus-core (apps/api) + nexus-web (apps/web) + neo4j-db
├── docs/ · SPRINT.md · .github/workflows/
└── reports → evidências governadas
```

> **Comandos do backend rodam a partir de `apps/api/`** (CWD resolve `config/` e `data/`);
> **comandos do frontend a partir de `apps/web/`**. Vercel: Root Directory = `apps/web`.

---

## 📡 Propósito
Nexus-Alpha é uma inteligência artificial autônoma focada em mineração semântica da web, indexação vetorial, grafo de conhecimento e auto-evolução contínua — operando sob infraestrutura gratuita (Hugging Face Spaces + GitHub Actions + Qdrant Cloud + Neo4j AuraDB).

## 🧱 Arquitetura (Camadas)

| Camada | Função | Arquivos Principais (em `apps/api/`) |
|---|---|---|
| **Miner** | Web scraping assíncrono + anti-bloqueio + proxy rotation | `src/miner/web_miner.py`, `anti_block.py` |
| **Cognition** | Chain-of-Thought + RAG ativo + NER (spaCy + fallback regex) | `src/cognition/reasoning_engine.py`, `rag_engine.py`, `nlp_extractor.py` |
| **Memory** | Grafo (Neo4j) + Vetor (Qdrant/Milvus) + Memória local híbrida | `src/database/graph_connector.py`, `vector_connector.py` |
| **Brain** | Memória cognitiva (working/episódica/semântica) + Hebbian + consolidação | `src/brain/memory.py`, `regions.py` |
| **Security** | Filtro anti-fake-news por triangulação + sanitizador de logs + quarentena | `src/security/triangulation.py`, `log_sanitizer.py`, `interceptor.py` |
| **Reflection** | Auto-reflexão noturna + desempate web para contradições | `src/cognition/reflection.py` |

### 🧠 Modelo Cognitivo Persistente

Memória inspirada no cérebro (córtex/hipocampo), durável no Neo4j:

- **Working** (RAM, decai) → **Episódica** (`:Episodio`, `fact_hash + day`, MERGE idempotente) → **Semântica** (`:Fato`/`:RELACIONA`, consolidação Hebbiana).
- **Limites:** episódios retidos por **30 dias ou 10.000 nós**; quórum de triangulação **3**; 7 slots de working memory.
- **Fallback:** `/api/brain/episodes` lê o Neo4j e, se indisponível, cai para a memória volátil (campo `source`).
- **Saúde cognitiva:** `GET /api/metrics` → `cognitive_health` (`episodic_persistence_rate`, `hebbian_consistency_check`, `retention_pressure`).
- **Restart do Space:** efêmeros zeram; episódios/fatos consolidados **persistem**.
- **Estresse:** `python scripts/stress_episodes.py [N]` (insere N episódios sintéticos, mede e valida a retenção).

## 🚀 Execução Local

```bash
# 1. Ambiente (backend — SEMPRE de apps/api)
cd apps/api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Infraestrutura (Docker — a partir da raiz)
docker-compose up -d neo4j-db
# (opcional: Qdrant via docker-compose ou Qdrant Cloud com QDRANT_HOST)

# 3. Pipeline completo (de apps/api)
python -m src.main "Inteligência Artificial"

# 4. Dashboard técnico (modo escuro + animações Motion)
streamlit run dashboard/app.py

# 5. Mock server para testes UI
python scripts/mock_server.py
```

Frontend (Next.js — de `apps/web/`): `npm install && npm run dev`.

## 🔒 Segurança e Governança

- **Segredos:** todas as credenciais são carregadas exclusivamente via `os.environ.get()` (nunca hardcoded).
- **Sanitização:** `log_sanitizer.py` mascara `bolt://neo4j:...`, tokens `X-Nexus-Token`, `api_key`, `NexusSecurePass` antes de qualquer saída pública.
- **Intercepção:** `interceptor.py` rejeita payloads >1MB e bloqueia brute-force após 10 tentativas.
- **Anti-bloqueio:** `AntiBlockSystem` rotaciona `User-Agent` e `Referer`; `ProxyRotator` faz rotação de proxies.
- **Triangulação:** `TriangulationFilter` promove fatos apenas com 3+ domínios independentes + confiança média ≥ limite configurável (`settings.yaml`).

## 📊 Testes

```bash
cd apps/api
python -m pytest tests/ -v
```

Os ~800 testes cobrem: miner, cognition, RAG, NLP, triangulation, reflection, memory, vector, embeddings, quarantine, anti-block, proxy, reasoning engine, chat (API/serviço/LLM), topologia de grafo, sanitização de logs, interceptor, dashboard components, piloto DEFENDEU.

## 📋 Governança

- `SPRINT.md` — documento dinâmico de governança (funcionalidade alvo, tarefas, critérios, plano de teste).
- `.github/workflows/ai-validation.yml` — CI: pytest + auditoria anti-leak + conformidade `SPRINT.md`.
- `docs/08-knowledge-management/HANDOVER_PROMPT.md` — instruções de onboarding para novos agentes/desenvolvedores.
- `vercel.json` + `public/robots.txt` — blindagem contra scrapers e bloqueio de rotas públicas sensíveis (`/api/`, `/_next/image*`).
- **`docs/`** — documentação completa do projeto, indexada em [`docs/README.md`](docs/README.md):
  produto ([`PRD.md`](docs/01-product-discovery/PRD.md)), arquitetura ([`ARCHITECTURE.md`](docs/02-architecture-design/ARCHITECTURE.md)),
  API ([`API.md`](docs/04-api-integrations/API.md)), regras ([`RULES.md`](docs/03-development-process/RULES.md)), decisões
  ([`ADR.md`](docs/02-architecture-design/ADR.md)), memória ([`MEMORY.md`](docs/08-knowledge-management/MEMORY.md)), operação
  ([`MONITORING.md`](docs/07-operations-marketing/MONITORING.md), [`BACKUP_DR.md`](docs/06-devops-deployment/BACKUP_DR.md),
  [`PRODUCTION_DEPLOY.md`](docs/06-devops-deployment/PRODUCTION_DEPLOY.md)) e processo
  ([`ONBOARDING.md`](docs/08-knowledge-management/ONBOARDING.md), [`ITERATION.md`](docs/08-knowledge-management/ITERATION.md)).

## 🧪 Infraestrutura Gratuita (Zero Cost)

- **Cérebro:** Hugging Face Spaces (`app.py` via FastAPI, porta 7860).
- **Agendador:** GitHub Actions cron (`.github/workflows/ai-cron.yml` — a cada 6h).
- **Memória Vetorial:** Qdrant Cloud (free tier) ou fallback in-memory (`vector_connector.py`).
- **Grafo:** Neo4j AuraDB Free (`graph_connector.py`).
- **Computação de Ajuste:** Kaggle Notebooks (30h GPU/semana) ou Hugging Face Spaces (CPU).

### Fine-tuning opt-in (LlamaFactory)

A Nexus-Alpha pode exportar fatos verificados do grafo para um dataset Alpaca/JSONL e gerar configuração LoRA/SFT para treino externo com LlamaFactory.

Este fluxo é **opt-in** e não faz parte do runtime principal nem do CI.

Ambiente recomendado para treino:
- Python 3.11–3.13
- GPU, por exemplo Kaggle T4/P100
- Dependências separadas:

```bash
pip install -r requirements-llamafactory.txt
```

Uso local para preparar artefatos:

```bash
python scripts/train_lora.py export --limit 100
python scripts/train_lora.py config
```

Para treinar apenas quando LlamaFactory estiver instalado no ambiente opt-in:

```bash
python scripts/train_lora.py train
```

Sem LlamaFactory instalado, o comando `train` retorna erro amigável e não quebra o runtime da Nexus-Alpha.

## 📁 Estrutura do Repositório

```
nexus-alpha/
├── apps/
│   ├── api/                        ← Backend Python (FastAPI + mineração + grafo)
│   │   ├── app.py                  ← core FastAPI (HF Space :7860)
│   │   ├── src/                    ← miner/ cognition/ database/ security/ brain/ ops/ simulation/ training/
│   │   ├── config/                 ← settings.yaml, seed_clusters.yaml, security_policies.json
│   │   ├── tests/ · scripts/ · dashboard/
│   │   ├── Dockerfile · Dockerfile.hf · README_HF.md
│   │   └── requirements{,-dev,-hf,-llamafactory,-tooling}.txt
│   └── web/                        ← Frontend Next.js 14 (Vercel)
│       ├── src/app/                ← App Router + proxy /api/nexus (policy.mjs)
│       ├── src/frontend/           ← ChatWidget, BrainPanel, KnowledgeGraph
│       ├── Dockerfile.web · vercel.json · public/robots.txt
│       └── package.json · tsconfig.json · tailwind.config.ts
├── docker-compose.yml              ← nexus-core (apps/api) + nexus-web + neo4j-db
├── .github/workflows/              ← ai-validation · ai-cron · db-backup
├── docs/ · SPRINT.md · reports/ → evidências governadas (apps/api/reports pós-move)
└── AGENTS.md · ARCHITECTURE.md · README.md
```

**Vercel:** Root Directory do projeto = `apps/web`. **HF Space:** deploy via
`apps/api/scripts/deploy_hf_space_safe.py` (allowlist: `app.py`, `src/**`, `config/**`, `requirements*`).
