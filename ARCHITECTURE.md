# 📐 Arquitetura do Ecossistema Nexus-Alpha

Este documento descreve o fluxo de dados, a topologia de rede e os protocolos de
segurança do ecossistema **Nexus-Alpha**, uma inteligência artificial autônoma de
mineração semântica e auto-evolução operando em infraestrutura **Custo Zero**
(GitHub Actions grátis + Hugging Face Spaces + Qdrant Cloud + Neo4j AuraDB).

---

## 🔄 1. Pipeline de Dados e Fluxo Macroscópico

O ciclo de vida do conhecimento na Nexus-Alpha segue um fluxo unidirecional e
assíncrono dividido em 5 etapas:

```text
[ GitHub Actions ] (A cada 6 horas — cron '0 */6 * * *')
       │
       ▼ (Gera Cabeçalhos Furtivos: User-Agent/Referer rotativos + delay dinâmico)
[ AntiBlockSystem ] ───► [ Web Scraping ] (Coleta dados brutos)
                               │
                               ▼ (Gera Triplas {sujeito, predicado, objeto})
                        [ NLPExtractor ]  (spaCy + fallback heurístico)
                               │
                               ▼ (POST Seguro /api/ingest — X-Nexus-Token + Bearer HF)
                    [ Hugging Face Spaces ] (FastAPI Core — app.py)
                               │
             ┌─────────────────┴─────────────────┐
             ▼ (Memória Sementica)               ▼ (Córtex de Grafos Relacionais)
     [ Qdrant Cloud ]                     [ Neo4j AuraDB ]
(store_memory / vetor 384-dim)         (ingest_payload / nós + relações)
```

> **Nota de resiliência (verificado em 2026-09-09):** quando o Neo4j ou o Qdrant
> estão indisponíveis, o `app.py` degrada graciosamente. O loop de ingestão
> responde com `"db_status": "demo-memory"` (persistência em memória) e os fatos
> sem triangulação suficiente são enviados à **quarentena**, nunca descartados.

---

### 💬 Fluxo de Atendimento Conversacional (Chatbot)

```text
[ Cliente no site ] → (bolha de chat) → [ ChatWidget (Next.js + Motion) ]
                                              │ POST /api/chat
                                              ▼
                                     [ FastAPI /api/chat ]
                                              │
                                ┌─────────────┴─────────────┐
                                ▼ (fatos)                    ▼ (geração)
                       [ Memória Híbrida ] ──────────► [ LLM plugável ]
                       (Neo4j + Qdrant)              (extrativo ou remoto)
```

*   **Recuperação:** `src/cognition/chat_service.py` extrai palavras-chave e
    consulta `GraphConnector.search_context` (Neo4j) + `VectorConnector.query_similarity`
    (Qdrant), com histórico curto por `session_id`.
*   **Geração:** `src/cognition/llm_provider.py` — responder **extrativo** por padrão
    (zero dependências); LLM opcional via `NEXUS_LLM_BASE_URL` (compatível com
    OpenAI, Hugging Face Inference e LLM local via Ollama/vLLM).
*   **UI:** `src/frontend/components/ChatWidget.tsx` — tema grafite (`#0F172A`) com
    borda roxo elétrico (`#8B5CF6`), indicador "Nexus pensando..." e skeletons de
    mensagem. Config de movimento em `src/frontend/lib/motion.config.ts`.

### 🧬 Simulação de Enxame (Predição)

Expansão de capacidade inspirada em motores de predição multi-agente (ex.: MiroFish).
Como o MiroFish é **AGPL-3.0**, nenhum código foi reutilizado — a implementação é
**original** e usa apenas a biblioteca padrão.

```text
[ POST /api/simulate ] → [ SwarmSimulator ]
                              ├─ seed: topologia do grafo OU search_context(tópico)
                              ├─ agentes (stance + influência) e canais de influência
                              └─ rodadas de bounded confidence → relatório
```

*   **`src/simulation/agent.py`** — `SwarmAgent`: cada conceito vira um agente com
    posição (`stance`), influência (grau no grafo) e vizinhança.
*   **`src/simulation/swarm.py`** — `SwarmSimulator`: dinâmica de opinião
    (convergência/polarização), injeção "visão divina" e relatório (consenso,
    polarização, veredito, confiança, clusters, trajetória).
*   **Determinismo:** `seed` reproduz a simulação; custo limitado (≤50 rodadas).

---

## 🗂️ 2. Topologia dos Módulos Core

O repositório é estritamente modularizado para garantir a manutenibilidade por
agentes independentes:

*   **`src/miner/` (Camada de Ingestão):** scripts de raspagem e o `anti_block.py`.
    É responsável por disfarçar as requisições mudando `User-Agents` e inserindo
    atrasos dinâmicos para evitar banimentos por IPs de nuvem. Ainda contém
    `web_miner.py` (scraper assíncrono), `quarantine.py` (fila local de rejeitados)
    e `security_protocol.py` (cálculo de confiança de domínio).

*   **`src/cognition/` (Camada Cognitiva):** Orquestra o *Chain-of-Thought*
    (`reasoning_engine.py` + `reasoning.py`), o processamento de linguagem natural
    (`nlp_extractor.py` com fallback heurístico do `extractor.py`), o RAG ativo
    (`rag_engine.py`), as memórias locais (`memory.py`) e a auto-reflexão noturna
    (`reflection.py`). Traduz blocos de texto bruto em relacionamentos semânticos
    `{sujeito, predicado, objeto}`.

*   **`src/security/` (Camada de Defesa):** executa a quarentena e a blindagem
    contra falsas informações por triangulação cruzada (`triangulation.py`),
    exigindo confirmação em múltiplos domínios independentes. Inclui o
    `log_sanitizer.py` (mascara credenciais com `[MASKED]` em logs públicos), o
    `interceptor.py` (rejeita payloads >1MB e bloqueia brute-force) e o
    `rate_limiter.py` (barreira deslizante de 5 req/min por IP no `/api/chat`).

*   **`src/database/` (Camada de Persistência):** conectores assíncronos oficiais —
    `graph_connector.py` (Neo4j / Cypher) e `vector_connector.py` (Qdrant /
    fallback em memória). O modelo usa a relação `RELACIONA {predicate}` em
    **Cypher puro (sem APOC)**, garantindo portabilidade no AuraDB. Os vetores são
    gerados por `src/cognition/embeddings.py` (feature hashing local, sem API).

---

## 🔐 3. Protocolo Zero-Trust e Secrets Management

*   **Isolamento Estático:** nenhuma credencial de banco de dados (`NEO4J_PASSWORD`)
    ou token de comunicação de API (`NEXUS_API_TOKEN`) existe de forma literal no
    código do repositório — a leitura é sempre via `os.environ.get()`.

*   **Injeção Dinâmica:** o GitHub Actions consome chaves via *Repository Secrets*
    (`secrets.NEXUS_API_TOKEN`, `secrets.HF_SPACE_URL`, `secrets.HF_TOKEN`) e as
    injeta no processo do worker. O Hugging Face Docker consome variáveis de
    ambiente criptografadas do próprio Space.

*   **Sanitização Atômica:** o registrador do sistema (`log_sanitizer.py`) intercepta
    as mensagens de erro em tempo de execução e substitui qualquer padrão que
    lembre chaves privadas por `[MASKED]`, evitando vazamento acidental nos
    consoles de build públicos do GitHub Actions.

---

## 💾 4. Resiliência e Continuidade

*   **Gate de Qualidade (`ai-validation.yml`):** roda em cada `push` a `main`/`dev`
    e em `pull_request`. Impede merges que quebrem a integridade do código (pytest),
    que vazem segredos (auditoria anti-leak via `grep`) ou que violem a governança
    (checagem de conformidade com `SPRINT.md`).

*   **Estratégia de Redundância (`db-backup.yml`):** um worker autônomo executa
    dumps semanais automáticos das estruturas do Neo4j a cada domingo às 00:00
    (`0 0 * * 0`), gerando um snapshot JSON segura em `backups/` e efetuando o
    commit+push automático via *Nexus-Alpha Bot*, garantindo recuperação total.

---

## 🛰️ 5. Camadas de Alcance e Tooling Opcional

Além do pipeline principal, o ecossistema admite camadas **opcionais** que ampliam
o alcance sem violar o pilar Custo Zero. Todas degradam graciosamente: quando o
backend não está instalado, o minerador segue com o scraper estático.

*   **`src/miner/agent_reach.py` — Agent Reach:** camada de alcance sobre
    primitivos gratuitos. Usa o **Jina Reader** (`https://r.jina.ai/<url>`) para
    converter páginas JS-heavy em markdown limpo, **feedparser** para feeds
    RSS/Atom e **yt-dlp** para transcrições do YouTube. Nenhuma chave de API.
*   **`src/miner/browser_miner.py` — Browser Use (opt-in):** renderização de
    páginas dinâmicas via `browser-use`. Exige `pip install browser-use` **e** uma
    chave de LLM (`OPENAI_API_KEY`); desativado por padrão.
*   **`scripts/security_audit.py` — Strix (opt-in):** wrapper não-bloqueante para
    pentest autônomo. Exige Docker + chave de LLM; sem eles, imprime instruções.
*   **Dependências:** isoladas em `requirements-tooling.txt` — o CI não as exige.

### 🧰 Tooling de Desenvolvimento (opencode)

*   **MCP `codebase-memory`:** indexa o repositório em um grafo de código (15 tools).
*   **MCP `agentmemory`:** memória persistente entre sessões (7 tools em modo local).
*   **Subagents (`~/.config/opencode/agent/`):** kg-engineer, rag-engineer,
    data-engineer, devops-automator, code-reviewer, minimal-change-engineer,
    appsec-engineer, secrets-engineer.
*   **Skill `diagram-design` (`~/.agents/skills/`):** diagramas editoriais SVG/HTML.

> Configs de MCP/agents/skills vivem no escopo global do opencode, **não** no
> repositório — não afetam o build nem o runtime de produção.

---

## 🏗️ 6. Stack e Infraestrutura (Zero Cost)

| Componente | Papel | Camada/Arquivo |
|---|---|---|
| GitHub Actions | Agendador + runner do worker | `.github/workflows/ai-cron.yml` |
| Hugging Face Spaces | Core FastAPI (porta 7860) | `app.py`, `Dockerfile.hf` |
| Neo4j AuraDB | Grafo de conhecimento | `src/database/graph_connector.py` |
| Qdrant Cloud | Memória vetorial semântica | `src/database/vector_connector.py` |
| Next.js + Tailwind + Motion | Dashboard de monitoramento | `src/frontend/`, `dashboard/` |

---

## 📜 7. Como Executar

```bash
# Ciclo completo local
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
docker-compose up -d neo4j-db        # opcional
python -m src.main "Inteligência Artificial"

# Testes (35 casos)
python -m pytest tests/ -v
```

> O ciclo em produção é auto-acionado a cada 6 horas pelo cron do GitHub Actions
> (`ai-cron.yml`) e pode ser disparado manualmente via `workflow_dispatch`.
