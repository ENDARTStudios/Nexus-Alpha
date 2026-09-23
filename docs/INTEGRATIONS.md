# 🔗 Integrações — Nexus-Alpha

Todas as integrações operam em **free tier** e degradam graciosamente.
Segredos exclusivamente via variáveis de ambiente (`.env.example` documenta
todas).

---

## 1. Persistência

### Neo4j AuraDB (grafo de conhecimento) — obrigatório em produção
- Conector: `src/database/graph_connector.py` (async, `neo4j+s://`).
- Cypher **puro sem APOC** (portabilidade free tier).
- Env: `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`.
- Local: `docker-compose up -d neo4j-db` (`bolt://neo4j-db:7687`).
- Cuidado: free tier pode **pausar por inatividade** — ver DR-1 em
  [`BACKUP_DR.md`](./BACKUP_DR.md).

### Qdrant Cloud (memória vetorial) — opcional
- Conector: `src/database/vector_connector.py`; collection
  `nexus_semantic_memory`, 384 dims.
- Env: `QDRANT_HOST`, `QDRANT_API_KEY`. Sem env → fallback in-memory.
- Vetores gerados localmente por `src/cognition/embeddings.py`
  (feature hashing — **sem API de embedding**, zero custo).

## 2. Execução

### Hugging Face Spaces (core FastAPI)
- `app.py` na porta 7860; imagem via `Dockerfile.hf`; deps lite em
  `requirements-hf.txt` (sem torch/spacy/transformers).
- Space **privado**; variáveis criptografadas no próprio Space.
- Deploy: [`PRODUCTION_DEPLOY.md`](./PRODUCTION_DEPLOY.md); script auxiliar
  `scripts/deploy_hf_space.py`.

### GitHub Actions
| Workflow | Agenda | Papel |
|---|---|---|
| `ai-validation.yml` | push main/dev + PRs | gate: anti-leak, pytest, SPRINT.md, allowlist proxy (Node 20) |
| `ai-cron.yml` | `0 */6 * * *` + manual | worker autônomo: `scripts/worker_cycle.py` (usa `NEXUS_API_TOKEN`, `HF_SPACE_URL`, `HF_TOKEN`) |
| `db-backup.yml` | `0 0 * * 0` (domingo) | snapshot JSON do Neo4j → `backups/` + commit do bot |

### Vercel (proxy + frontend)
- `src/app/api/nexus/[...path]/route.ts` repassa ao Space privado injetando
  `NEXUS_SPACE_URL` + `HF_TOKEN` + `NEXUS_API_TOKEN` (server-side, nunca
  `NEXT_PUBLIC_*`).
- `vercel.json` + `public/robots.txt` blindam `/api/` e `/_next/image*`.

## 3. Coleta (camada Miner)

### Agent Reach (`src/miner/agent_reach.py`) — opcional, zero chave
- **Jina Reader** (`https://r.jina.ai/<url>`): páginas JS-heavy → markdown.
- **feedparser**: RSS/Atom.
- **yt-dlp**: transcrições do YouTube.
- Deps isoladas em `requirements-tooling.txt` (CI não exige).

### Browser-use (`src/miner/browser_miner.py`) — opt-in, desativado
- Renderização dinâmica; exige `pip install browser-use` **e**
  `OPENAI_API_KEY`. Sem ambos, miner segue com scraper estático.

## 4. LLM (opcional, plugável)

- `src/cognition/llm_provider.py`: resposta **extrativa por padrão**
  (zero dependência). LLM opcional via env compatível OpenAI:
  `NEXUS_LLM_BASE_URL`, `NEXUS_LLM_MODEL`, `NEXUS_LLM_API_KEY`
  (HF Inference, OpenRouter, Ollama/vLLM locais).
- `LLMCanonicalExtractor` + `/api/extract` para extração canônica.
- **Regras:** LLM nunca é árbitro de fato (quórum 3 manda); nunca entra nas
  etapas determinísticas; nunca no CI obrigatório.

## 5. Fine-tuning (opt-in, fora do runtime)

- **LlamaFactory** externo (Kaggle T4/P100, Python 3.11–3.13,
  `requirements-llamafactory.txt`).
- Fluxo: `python scripts/train_lora.py export --limit 100` →
  `data/sft/nexus_verified_facts.jsonl`; `config` → YAML LoRA/SFT;
  `train` só com LlamaFactory instalado (senão erro amigável).
- Gate de treino: `records >= 50`, `verified_facts >= 10`, sem segredos,
  YAML válido → smoke Kaggle (`epochs 1, batch 2, grad_accum 2,
  max_samples 100`).

## 6. Tooling de desenvolvimento (fora do repositório)

- MCP `codebase-memory` (grafo de código, 15 tools) e `agentmemory`
  (memória persistente) no escopo global do opencode — **não** afetam build/runtime.
- Subagents: kg-engineer, rag-engineer, data-engineer, devops-automator,
  code-reviewer, minimal-change-engineer, appsec-engineer, secrets-engineer.
- **Strix** (`scripts/security_audit.py`, opt-in): pentest autônomo; exige
  Docker + chave de LLM; wrapper não-bloqueante.

## 7. Checklist para nova integração

1. Cabe no **custo zero** (free tier) e degrada sem rede/chave?
2. Segredo só via env; nome documentado em `.env.example`.
3. Dependência pesada? → `requirements-tooling.txt` (nunca no CI lite).
4. Teste com fallback (sem serviço) na suíte.
5. Registrar aqui + em [`ADR.md`](./ADR.md) se for decisão duradoura.
