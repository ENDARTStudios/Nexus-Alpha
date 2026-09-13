# 🏁 Sprint Governance & Backlog Log — Nexus-Alpha

Este documento estabelece o escopo de execução exclusivo para a **Sprint Atual**.
Nenhum agente, modelo de IA ou desenvolvedor pode realizar alterações em arquivos
ou introduzir dependências que não estejam explicitamente mapeadas neste documento.

---

## 📅 Sprint Atual: `v1.3.0-alpha` — Produção Visual e Integração do Córtex

- **Status:** 🟢 Planejada / Em Execução
- **Impacto:** Altíssimo (consumo dos endpoints estáveis reais pelo Frontend Next.js)
- **Complexidade:** Média (endpoints autenticados e tratamento de CORS em produção)

### 🎯 Funcionalidade Alvo e Escopo

Conectar os componentes visuais (`ChatWidget.tsx` e `KnowledgeGraph.tsx`) aos
endpoints estáveis da API do Hugging Face (`/api/chat` com Cypher real e
`/api/graph/topology`), substituindo os mocks e destacando os fatos verificados.

### 📋 Tarefas Mapeadas (Mapeamento de GitHub Issues)

#### [Issue #018] — Acoplamento do Chatbot Real ao Grafo Vivo
- **Descrição:** consumir `/api/chat` (Neo4j real) e exibir o selo "Fato Verificado"
  quando a resposta se basear em fato corroborado.
- **Arquivos Afetados:** `src/frontend/components/ChatWidget.tsx`,
  `src/frontend/lib/api.ts`, `src/cognition/chat_service.py`,
  `src/database/graph_connector.py` (`CONTEXT_QUERY` expõe `verificado`), `app.py`.
- **Critérios de Conclusão:** o chat responde com dados reais do cluster online; o
  selo só aparece quando `verified` é verdadeiro.

#### [Issue #019] — Renderização da Topologia Viva no ForceGraph
- **Descrição:** consumir `/api/graph/topology` e colorir os nós conforme as
  propriedades reais do Neo4j (conceitos vs nós de fatos verificados).
- **Arquivos Afetados:** `src/frontend/components/KnowledgeGraph.tsx`,
  `src/database/graph_connector.py` (`TOPOLOGY_QUERY` expõe `verificado`).
- **Critérios de Conclusão:** renderização dinâmica dos conceitos e conexões reais;
  nós verdes para fatos verificados, violeta para os demais.

---

## 🛡️ Restrições de Deploy e Critérios de Aceitação (Definition of Done)

1. **Gate de Testes:** a suíte (97+) e o gate anti-leak devem permanecer verdes.
2. **CORS Seguro:** a API do Hugging Face deve aceitar as requisições do domínio de
   deploy da Vercel via `NEXUS_CORS_ORIGINS`.

---

## 📜 Histórico de Sprints Concluídas

- `v1.2.0-alpha` — Correção de `/health` e TLS `neo4j+s://` do AuraDB.
- `v1.3.0-alpha` — Integração de tooling (MCP, subagents, Agent-Reach, browser-use, Strix).
- `v1.4.0-alpha` — Atendimento conversacional (`ChatService` + `/api/chat` + ChatWidget).
- `v1.5.0-alpha` — Hardening & eficiência (APOC-free, embeddings locais, singletons, `/api/metrics`).
- `v1.6.0-alpha` — Simulação de enxame (`/api/simulate`).
- `v1.7.0-alpha` — Qualidade de extração (spaCy pt) + memória vetorial.
- `v1.8.0-alpha` — Ruído, limpeza e corroboração real (`:Fato` + `verified_facts`).
