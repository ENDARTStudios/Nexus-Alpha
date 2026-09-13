# 🏁 Sprint Governance & Backlog Log — Nexus-Alpha

Este documento estabelece o escopo de execução exclusivo para a **Sprint Atual**.
Nenhum agente, modelo de IA ou desenvolvedor pode realizar alterações em arquivos
ou introduzir dependências que não estejam explicitamente mapeadas neste documento.

---

## ✅ Sprint Concluída: `v1.2.0-alpha` — Ajuste de Rotas e Conexão de Produção

- **Status:** 🟢 Concluída
- **Entregas:** rota explícita `GET /health` no `app.py` (Issue #016); protocolo
  `neo4j+s://` (TLS estrito do AuraDB) + configuração env-first no
  `graph_connector.py` (Issue #017); sanitização do fixture de teste do
  `log_sanitizer.py` para manter o gate anti-leak verde.
- **Pendência externa:** ativação do `cluster-active` depende de billing do GitHub
  Actions e das secrets `NEO4J_URI`/`NEO4J_PASSWORD` no Space.

---

## ✅ Sprint Concluída: `v1.3.0-alpha` — Integração de Tooling & Capacidades Externas

- **Status:** 🟢 Concluída (implementada; pendente de commit)
- **Impacto:** Médio (produtividade de desenvolvimento e ampliação das fontes de mineração)
- **Complexidade:** Média (adaptadores opcionais + configuração de agentes)
- **Pilar:** **Custo Zero** — nenhuma integração pode exigir chave paga por padrão;
  todas degradam graciosamente quando ausentes.

### 🎯 Funcionalidade Alvo e Escopo

Ampliar as capacidades da Nexus-Alpha com um conjunto de ferramentas externas
selecionadas, mantendo o núcleo estável e o CI verde. Duas frentes:

1. **Dev-tooling (opencode):** memória de código e agentes especialistas para
   acelerar o desenvolvimento.
2. **Capacidades de runtime (minerador/segurança):** alcance de fontes que o
   scraper estático não cobre e auditoria de segurança opcional.

### 📋 Tarefas Mapeadas (Mapeamento de GitHub Issues)

#### [Issue #018] — MCP de dev-tooling no opencode (config externa)
- **Descrição:** registrar os servidores MCP `codebase-memory` (grafo de código)
  e `agentmemory` (memória persistente) na config global do opencode.
- **Arquivos Afetados:** `~/.config/opencode/opencode.jsonc` (externo ao repositório)
- **Critérios:** handshake MCP validado (`initialize` + `tools/list`) para ambos.

#### [Issue #019] — Subagents e skill de diagramação
- **Descrição:** instalar 8 subagents curados (agency-agents) e a skill
  `diagram-design` para documentação visual.
- **Arquivos Afetados:** `~/.config/opencode/agent/*.md`, `~/.agents/skills/diagram-design/`
- **Critérios:** frontmatter válido (`mode: subagent`); `SKILL.md` presente.

#### [Issue #020] — Adaptador Agent Reach (fontes de mineração)
- **Descrição:** camada opcional de alcance sobre primitivos gratuitos — Jina
  Reader (web), feedparser (RSS) e yt-dlp (YouTube) — integrada ao `WebMiner`.
- **Arquivos Afetados:** `src/miner/agent_reach.py`, `tests/test_agent_reach.py`
- **Critérios:** degradação graciosa (`None` sem exceção) quando o backend falta.

#### [Issue #021] — Backend opcional Browser Use
- **Descrição:** renderização de páginas dinâmicas via `browser-use`, opt-in e
  acionada apenas quando o conteúdo estático é insuficiente.
- **Arquivos Afetados:** `src/miner/browser_miner.py`, `src/miner/web_miner.py`,
  `src/miner/__init__.py`, `tests/test_browser_miner.py`, `tests/test_reach_integration.py`
- **Critérios:** `WebMiner` sem os adaptadores mantém comportamento idêntico.

#### [Issue #022] — Auditoria de segurança com Strix (opcional)
- **Descrição:** wrapper não-bloqueante que aciona o pentest autônomo quando
  Docker + chave de LLM estão presentes.
- **Arquivos Afetados:** `scripts/security_audit.py`, `requirements-tooling.txt`
- **Critérios:** sem pré-requisitos, imprime instruções e sai com código 0.

#### [Issue #023] — Documentação e governança
- **Descrição:** registrar a arquitetura das camadas opcionais e o mapa de tooling.
- **Arquivos Afetados:** `SPRINT.md`, `ARCHITECTURE.md`

---

## 🛡️ Critérios de Aceitação (Definition of Done)

1. **Pass de Testes:** `pytest` verde (inclui os novos testes dos adaptadores).
2. **Zero-Custo Preservado:** `requirements.txt` inalterado; dependências novas
   isoladas em `requirements-tooling.txt` e **não** exigidas pelo CI.
3. **Degradação Graciosa:** ausência de backend/CLI nunca derruba o pipeline.
4. **Gate anti-leak:** nenhuma credencial literal fora de `graph_connector.py`.

## Plano de Teste

- `tests/test_agent_reach.py`: payload Jina, conteúdo curto, erro HTTP, limpeza
  de VTT, ausência de yt-dlp/feedparser, despacho de `fetch`.
- `tests/test_browser_miner.py`: desativação sem módulo/chave, import-error gracioso.
- `tests/test_reach_integration.py`: fallback do `WebMiner` (renderer > reach > estático).
- `python scripts/security_audit.py`: sem pré-requisitos, deve sair com código 0.

---

## 📅 Sprint Atual: `v1.4.0-alpha` — Atendimento Conversacional (Chatbot)

- **Status:** 🟢 Planejada / Em Execução
- **Impacto:** Alto (transforma a Nexus-Alpha em um chatbot de site sobre a memória híbrida)
- **Complexidade:** Média (rota de conversação + widget de UI)
- **Pilar:** **Custo Zero** — geração plugável: responder extrativo por padrão (sem
  dependências) e LLM opcional via endpoint compatível com OpenAI (HF Inference,
  Ollama/local, OpenRouter).

### 🎯 Funcionalidade Alvo e Escopo

Expor o conhecimento minerado/validado como um atendimento conversacional:

```
[ Widget no site ] → POST /api/chat → [ ChatService ]
                                          ├─ recuperação híbrida (Neo4j + Qdrant)
                                          └─ geração (extrativo ou LLM remoto)
```

### 📋 Tarefas Mapeadas (Mapeamento de GitHub Issues)

#### [Issue #024] — Camada de geração plugável
- **Descrição:** `ExtractiveResponder` (padrão, zero deps) + `OpenAICompatibleLLM`
  (opcional, cobre LLM local via Ollama/`NEXUS_LLM_BASE_URL`).
- **Arquivos Afetados:** `src/cognition/llm_provider.py`, `tests/test_llm_provider.py`
- **Critérios:** fallback extrativo sempre disponível; remoto só quando configurado.

#### [Issue #025] — Recuperação híbrida + sessões de conversa
- **Descrição:** `ChatService` extrai palavras-chave, consulta grafo e vetor,
  sintetiza e mantém histórico curto por `session_id`.
- **Arquivos Afetados:** `src/cognition/chat_service.py`,
  `src/database/graph_connector.py` (`search_context`),
  `src/cognition/__init__.py`, `tests/test_chat_service.py`
- **Critérios:** degradação graciosa sem Neo4j/Qdrant; histórico LRU limitado.

#### [Issue #026] — Rota `POST /api/chat` + CORS
- **Descrição:** endpoint público de conversação no FastAPI, com CORS configurável
  por `NEXUS_CORS_ORIGINS`.
- **Arquivos Afetados:** `app.py`, `tests/test_chat_api.py`
- **Critérios:** `200` com `reply`/`reasoning_steps`; `422` para mensagem vazia.

#### [Issue #027] — Widget de chat (Next.js/Tailwind/Motion)
- **Descrição:** bolha flutuante com tema grafite + roxo elétrico, indicador de
  raciocínio ("Nexus pensando...") e skeletons de mensagem.
- **Arquivos Afetados:** `src/frontend/components/ChatWidget.tsx`,
  `src/frontend/lib/api.ts`, `src/frontend/lib/motion.config.ts`
- **Critérios:** responsivo; usa `framer-motion`; consome `NEXT_PUBLIC_NEXUS_API_URL`.

---

## 🛡️ Critérios de Aceitação (Definition of Done)

1. **Pass de Testes:** `pytest` verde (chat + geração + recuperação).
2. **Custo Zero Preservado:** nenhuma dependência nova obrigatória; LLM é opcional.
3. **Degradação Graciosa:** sem Neo4j/Qdrant/LLM o chat responde honestamente.
4. **Gate anti-leak:** nenhuma credencial literal fora de `graph_connector.py`.

## Plano de Teste

- `tests/test_llm_provider.py`: extrativo com/sem contexto; disponibilidade do remoto.
- `tests/test_chat_service.py`: fusão grafo+vetor, falha do grafo, mensagem vazia,
  histórico de sessão limitado.
- `tests/test_chat_api.py`: `/health`, `/api/chat` (200) e validação (422).

---

## ✅ Sprint Concluída: `v1.5.0-alpha` — Hardening & Eficiência (Auditoria Global)

- **Status:** 🟢 Concluída
- **Objetivo:** corrigir bugs de runtime, remover dependências frágeis e reduzir o custo por requisição.

### Correções aplicadas

| # | Problema | Correção | Arquivos |
|---|---|---|---|
| H1 | `dashboard/app.py` usava `asyncio` sem importar | `import asyncio` + `asyncio.run` | `dashboard/app.py` |
| H2 | `interceptor.py` importava `sanitize_text` inexistente | função criada + exportada | `src/security/log_sanitizer.py`, `src/security/__init__.py` |
| H3 | `VectorConnector.upsert` não armazenava (código morto) | passou a persistir de fato | `src/database/vector_connector.py` |
| H4 | Dimensão do vetor divergente (768 config vs 384 código) | alinhado para 384 + embedding real | `config/settings.yaml`, `src/main.py` |
| H5 | Ingestão dependia de APOC (`apoc.create.relationship`) | relação `RELACIONA {predicate}` (Cypher puro) | `src/database/graph_connector.py` |
| H6 | Driver Neo4j criado/fechado a cada requisição | singletons + pool reaproveitado | `app.py` |
| H7 | `worker_cycle` usava relógio monotônico e `domain_score=0.0` | epoch + melhor score das fontes | `scripts/worker_cycle.py` |
| H8 | `detect_contradictions` nunca casava (tipo dinâmico) | query sobre `r.predicate` | `src/database/graph_connector.py` |

### Novidades
- `src/cognition/embeddings.py` — embedding local determinístico (feature hashing), tornando a busca vetorial lexicalmente útil sem dependências.
- `GET /api/metrics` — métricas de grafo/vetores/quarentena.
- Bootstrap de constraints/índices do Neo4j no `lifespan` (`NEXUS_BOOTSTRAP_SCHEMA`).
- `.env.example` documentando todas as variáveis de ambiente.

### DoD
1. `pytest` verde (86 testes).
2. Nenhuma dependência nova obrigatória.
3. Gate anti-leak verde.

---

## ✅ Sprint Concluída: `v1.6.0-alpha` — Simulação de Enxame (Predição)

- **Status:** 🟢 Concluída
- **Objetivo:** expandir as capacidades com um motor de predição por enxame sobre o grafo de conhecimento.

### Contexto de licença
Capacidade inspirada em motores de predição multi-agente (ex.: MiroFish). O
MiroFish é **AGPL-3.0**, portanto **nenhum código foi reutilizado** — a
implementação é original (stdlib puro), preservando o Custo Zero e a licença do projeto.

### Entregas

| Item | Descrição | Arquivos |
|---|---|---|
| `SwarmAgent` | Conceito do grafo elevado a agente com `stance`/influência/vizinhança | `src/simulation/agent.py` |
| `SwarmSimulator` | Dinâmica de opinião com *bounded confidence*; seed de topologia ou relações | `src/simulation/swarm.py` |
| Relatório | consenso, polarização, veredito, confiança, clusters e trajetória | `src/simulation/swarm.py` |
| `POST /api/simulate` | Simulação por tópico ou grafo inteiro, injeção "visão divina" e narrativa LLM opcional | `app.py` |

### DoD
1. `pytest` verde (94 testes).
2. Zero dependências novas; determinístico com `seed`.
3. Degradação graciosa com grafo vazio (`status: empty`).

---

## ✅ Sprint Concluída: `v1.7.0-alpha` — Qualidade de Extração & Memória Vetorial

- **Status:** 🟢 Concluída
- **Objetivo:** melhorar a qualidade dos fatos minerados e popular a memória vetorial no fluxo de produção.

### Entregas

| Item | Descrição | Arquivos |
|---|---|---|
| spaCy PT no worker | instala `pt_core_news_sm` (wheel explícito, não-fatal) | `.github/workflows/ai-cron.yml` |
| Extrator SVO | raiz verbal, sintagmas via *subtrees*, filtro de pronomes e de palavras funcionais | `src/cognition/extractor.py` |
| Anti-boilerplate | seletores de ruído do Wikipedia (`.mw-editsection`, `#catlinks`, `.navbox`…) | `src/miner/web_miner.py` |
| Indexação vetorial | `/api/ingest` grava `hash_embedding` no Qdrant e devolve `vectors_indexed` | `app.py` |
| Runtime do Space | `qdrant-client` adicionado ao `requirements-hf.txt` | `requirements-hf.txt` |

### Resultado (produção)
- `db_status: cluster-active` e `vectors_indexed: 1` por ciclo.
- Grafo: **265 conceitos**, 87+ relações; memória vetorial: **4** fragmentos (Qdrant Cloud).
- Extração com predicados lemmatizados (`CONSISTIR`, `IMPULSIONAR`…) e sujeitos/objetos frasais.

### DoD
1. `pytest` verde (95 testes).
2. Nenhuma dependência nova no CI.
3. Gate anti-leak verde.

---

## ✅ Sprint Concluída: `v1.8.0-alpha` — Limpeza, Ruído e Corroboração Real

- **Status:** 🟢 Concluída
- **Objetivo:** executar os 3 passos de consolidação do conhecimento (ruído, limpeza, triangulação).

### Passo 1 — Filtro de ruído
- `EntityExtractor._valid_term`: rejeita termos com `|`, marcadores de navegação
  ("Portal", "Categoria", "editar"…) e "sopa" de nomes próprios (4+ tokens, 3+ capitalizados).
- `WebMiner.NOISE_SELECTORS`: +`.div-col`, `.portal`, `.sistersitebox`, `.reflist`, `.vertical-navbox`.

### Passo 2 — Limpeza e re-mineração
- Neo4j e Qdrant zerados; grafo reconstruído do zero.

### Passo 3 — Corroboração/triangulação real
- Modelo `:Fato` (nó) com `(:FonteWeb)-[:CONFIRMA]->(:Fato)`; `confirmacoes` e
  `verificado = confirmacoes >= $quorum` (default 3; `NEXUS_VERIFY_QUORUM`).
- Worker envia **um payload por fonte** (preserva o domínio) e usa 6 seeds diversas + `top_k=10`.
- `/api/ingest` e `/api/metrics` expõem `verified_facts`.

### Bugs corrigidos no caminho
- Em Cypher, relacionamento não pode ser endpoint → corroboração migrada para nó `:Fato`.
- `VectorConnector` nunca detectava o backend Qdrant (`backend or "memory"` tornava o auto-detect código morto).
- `RAGEngine.top_k=5` cortava as fontes → apenas 2 seeds eram mineradas.

### Resultado (produção)
- `db_status: cluster-active`; `vectors: 5` (Qdrant persistente).
- **206 conceitos, 106 fatos, 1 fato verificado** (`[4x] IA generativa --[DISTRIBUIR]--> IA explicável`).

### DoD
1. `pytest` verde (97 testes).
2. Gate anti-leak verde.
