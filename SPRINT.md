# 🏁 Sprint Governance & Backlog Log — Nexus-Alpha

Este documento estabelece o escopo de execução exclusivo para a **Sprint Atual**.
Nenhum agente, modelo de IA ou desenvolvedor pode realizar alterações em arquivos
ou introduzir dependências que não estejam explicitamente mapeadas neste documento.

---

## 📅 Sprint Atual: `v1.8.0-alpha` — Ignição do Motor GraphRAG

- **Status:** 🟢 Planejada / Em Execução
- **Impacto:** Altíssimo (transição de RAG simples para contextualização topológica profunda)
- **Complexidade:** Alta (navegação em caminhos de relacionamentos variáveis de 2 saltos no Neo4j)

### 🎯 Funcionalidade Alvo e Escopo

Implementar o pipeline de GraphRAG: extrair subgrafos contextuais de 1 a 2 saltos
dos termos pesquisados e injetar essa malha estruturada no prompt da LLM, via
`ChatService` (preservando sessões, fallback, rate limiting e o contrato da rota).

### 📋 Tarefas Mapeadas (Mapeamento de GitHub Issues)

#### [Issue #028] — Criação da Engine de Subgrafos `GraphRAGEngine`
- **Descrição:** consulta topológica com caminhos variáveis `RELACIONA*1..2`
  (schema real; tipos dinâmicos `UTILIZA|...` **não** existem no grafo).
- **Arquivos Afetados:** `src/cognition/graph_rag.py` (Criação),
  `tests/test_graph_rag.py` (Criação).
- **Critérios de Conclusão:** retorno textual dos mapas relacionais, com dedupe e
  degradação graciosa.

#### [Issue #029] — Enriquecimento do Prompt na API Central
- **Descrição:** injetar o subgrafo no contexto da LLM através do `ChatService`
  (a rota `/api/chat` já o consome), sem quebrar o contrato da resposta.
- **Arquivos Afetados:** `src/cognition/chat_service.py` (Modificação),
  `src/cognition/__init__.py` (Modificação).
- **Critérios de Conclusão:** fatos de fonte `graphrag` presentes e selo honesto
  quando houver colisão.

---

## 🛡️ Restrições de Deploy e Critérios de Aceitação (Definition of Done)

1. **Gate de CI:** suíte em **126 testes verdes**, anti-leak verde.
2. **Contrato Preservado:** `/api/chat` mantém `reasoning_steps`/`sources`/`provider`.

---

## 📜 Histórico de Sprints Concluídas

- `v1.2.0-alpha` — Correção de `/health` e TLS `neo4j+s://` do AuraDB.
- `v1.3.0-alpha` — Integração de tooling (MCP, subagents, Agent-Reach, browser-use, Strix).
- `v1.4.0-alpha` — Atendimento conversacional, malha de seeds e quórum modular.
- `v1.5.0-alpha` — Resolução vetorial de entidades + schema canônico via LLM.
- `v1.6.0-alpha` — Extração LLM canônica (`LLMCanonicalExtractor` + `/api/extract`).
- `v1.7.0-alpha` — Consolidação, caixa alta total e rate limiting.
