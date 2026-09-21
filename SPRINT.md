# 🏁 Sprint Governance & Backlog Log — Nexus-Alpha

Este documento estabelece o escopo de execução exclusivo para a **Sprint Atual**.
Nenhum agente, modelo de IA ou desenvolvedor pode realizar alterações em arquivos
ou introduzir dependências que não estejam explicitamente mapeadas neste documento.

---

## 📅 Sprint Atual: `v1.10.0-alpha` — Painel Cérebro (Observabilidade Read-Only)

- **Status:** 🟢 Planejada / Em Execução
- **Impacto:** Alto (observabilidade da memória cognitiva sem risco de efeitos colaterais)
- **Complexidade:** Baixa (contrato de API + componente read-only)

### 🎯 Funcionalidade Alvo e Escopo

Expor o cérebro em produção no frontend, **sem** criar cron de consolidação
separado (decisão: o worker de 6h já consolida; um cron extra duplicaria
`replays`/peso hebbiano e criaria corrida de escrita no Neo4j).

### 📋 Tarefas Mapeadas (GitHub Issues)

#### [Issue #032] — Contrato Normalizado `/api/brain/stats` + `/api/brain/episodes`
- **Descrição:** normalizar o payload (working/episódica/consolidação/grafo/vetores)
  e listar episódios recentes com status (`novo`/`repetido`/`consolidado`).
- **Arquivos Afetados:** `app.py`, `src/brain/memory.py`,
  `src/database/graph_connector.py` (`count_facts`, `count_consolidated`).
- **Critérios:** payload **somente-leitura**, sem segredos (neo4j/password/token).

#### [Issue #033] — Painel `BrainPanel` (read-only)
- **Descrição:** hook `useBrainStats`/`useBrainEpisodes` (polling de 60s) e painel
  com skeletons, status de consolidação e tabela de episódios.
- **Arquivos Afetados:** `src/frontend/lib/brain.ts`,
  `src/frontend/components/BrainPanel.tsx`, `src/app/page.tsx`.
- **Critérios:** build Next.js verde; sem botão de consolidação nesta versão.

---

## 🛡️ Critérios de Aceitação (Definition of Done)

1. **Gate de CI:** suíte em **141 testes verdes** (inclui contrato + anti-vazamento).
2. **Read-Only:** nenhuma rota nova escreve no grafo.

---

## 📜 Histórico de Sprints Concluídas

- `v1.2.0-alpha` — Correção de `/health` e TLS `neo4j+s://` do AuraDB.
- `v1.3.0-alpha` — Integração de tooling (MCP, subagents, Agent-Reach, browser-use, Strix).
- `v1.4.0-alpha` — Atendimento conversacional, malha de seeds e quórum modular.
- `v1.5.0-alpha` — Resolução vetorial de entidades + schema canônico via LLM.
- `v1.6.0-alpha` — Extração LLM canônica (`LLMCanonicalExtractor` + `/api/extract`).
- `v1.7.0-alpha` — Consolidação, caixa alta total e rate limiting.
- `v1.8.0-alpha` — Motor GraphRAG (subgrafos 1–2 saltos no chat).
- `v1.9.0-alpha` — Cérebro espelhado (working/episódica/semântica + Hebbian).

