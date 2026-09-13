# Nexus-Alpha — Ecossistema Autônomo de IA

> **Repositório privado — ENDARTStudios**  
> Sprint governada via `SPRINT.md` (v1.1.0-alpha) | CI `.github/workflows/ai-validation.yml`

---

## 📡 Propósito
Nexus-Alpha é uma inteligência artificial autônoma focada em mineração semântica da web, indexação vetorial, grafo de conhecimento e auto-evolução contínua — operando sob infraestrutura gratuita (Hugging Face Spaces + GitHub Actions + Qdrant Cloud + Neo4j AuraDB).

## 🧱 Arquitetura (Camadas)

| Camada | Função | Arquivos Principais |
|---|---|---|
| **Miner** | Web scraping assíncrono + anti-bloqueio + proxy rotation | `src/miner/web_miner.py`, `anti_block.py` |
| **Cognition** | Chain-of-Thought + RAG ativo + NER (spaCy + fallback regex) | `src/cognition/reasoning_engine.py`, `rag_engine.py`, `nlp_extractor.py` |
| **Memory** | Grafo (Neo4j) + Vetor (Qdrant/Milvus) + Memória local híbrida | `src/database/graph_connector.py`, `vector_connector.py` |
| **Security** | Filtro anti-fake-news por triangulação + sanitizador de logs + quarentena | `src/security/triangulation.py`, `log_sanitizer.py`, `interceptor.py` |
| **Reflection** | Auto-reflexão noturna + desempate web para contradições | `src/cognition/reflection.py` |

## 🚀 Execução Local

```bash
# 1. Ambiente
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Infraestrutura (Docker)
docker-compose up -d neo4j-db
# (opcional: Qdrant via docker-compose ou Qdrant Cloud com QDRANT_HOST)

# 3. Pipeline completo
python -m src.main "Inteligência Artificial"

# 4. Dashboard técnico (modo escuro + animações Motion)
streamlit run dashboard/app.py

# 5. Mock server para testes UI
python src/frontend/mock_server.py
```

## 🔒 Segurança e Governança

- **Segredos:** todas as credenciais são carregadas exclusivamente via `os.environ.get()` (nunca hardcoded).
- **Sanitização:** `log_sanitizer.py` mascara `bolt://neo4j:...`, tokens `X-Nexus-Token`, `api_key`, `NexusSecurePass` antes de qualquer saída pública.
- **Intercepção:** `interceptor.py` rejeita payloads >1MB e bloqueia brute-force após 10 tentativas.
- **Anti-bloqueio:** `AntiBlockSystem` rotaciona `User-Agent` e `Referer`; `ProxyRotator` faz rotação de proxies.
- **Triangulação:** `TriangulationFilter` promove fatos apenas com 3+ domínios independentes + confiança média ≥ limite configurável (`settings.yaml`).

## 📊 Testes

```bash
python -m pytest tests/ -v
```

Os 86 testes cobrem: miner, cognition, RAG, NLP, triangulation, reflection, memory, vector, embeddings, quarantine, anti-block, proxy, reasoning engine, chat (API/serviço/LLM), topologia de grafo, sanitização de logs, interceptor, dashboard components.

## 📋 Governança

- `SPRINT.md` — documento dinâmico de governança (funcionalidade alvo, tarefas, critérios, plano de teste).
- `.github/workflows/ai-validation.yml` — CI: pytest + auditoria anti-leak + conformidade `SPRINT.md`.
- `HANDOVER_PROMPT.md` — instruções de onboarding para novos agentes/desenvolvedores.
- `vercel.json` + `public/robots.txt` — blindagem contra scrapers e bloqueio de rotas públicas sensíveis (`/api/`, `/_next/image*`).

## 🧪 Infraestrutura Gratuita (Zero Cost)

- **Cérebro:** Hugging Face Spaces (`app.py` via FastAPI, porta 7860).
- **Agendador:** GitHub Actions cron (`.github/workflows/ai-cron.yml` — a cada 6h).
- **Memória Vetorial:** Qdrant Cloud (free tier) ou fallback in-memory (`vector_connector.py`).
- **Grafo:** Neo4j AuraDB Free (`graph_connector.py`).
- **Computação de Ajuste:** Kaggle Notebooks (30h GPU/semana) ou Hugging Face Spaces (CPU).

## 📁 Estrutura do Repositório

```
nexus-alpha/
├── .github/workflows/ai-validation.yml
├── config/
│   ├── settings.yaml
│   └── security_policies.json
├── src/
│   ├── miner/
│   ├── cognition/
│   ├── database/
│   ├── security/
│   └── frontend/
├── dashboard/
├── tests/
├── scripts/
├── Dockerfile / Dockerfile.hf / docker-compose.yml
├── app.py / vercel.json / public/robots.txt
├── SPRINT.md / HANDOVER_PROMPT.md
└── requirements.txt
```
