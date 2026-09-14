# 🏁 Sprint Governance & Backlog Log — Nexus-Alpha

Este documento estabelece o escopo de execução exclusivo para a **Sprint Atual**.
Nenhum agente, modelo de IA ou desenvolvedor pode realizar alterações em arquivos
ou introduzir dependências que não estejam explicitamente mapeadas neste documento.

---

## 📅 Sprint Atual: `v1.7.0-alpha` — Consolidação, Caixa Alta e Rate Limiting

- **Status:** 🟣 Concluída com Sucesso
- **Impacto:** Crítico (unificação total de display semântico e proteção ativa contra flooding)

### 📋 Resultados Medidos em Produção

- **Conceitos unificados em UPPER:** 494 nós estruturados de forma homogênea.
- **Validação Ativa:** `INTELIGÊNCIA ARTIFICIAL --[UTILIZA]--> MACHINE LEARNING` (3x corroborado).
- **Segurança de Borda:** `InMemoryRateLimiter` acoplado ao `/api/chat` (5 req/min por IP, 429).
- **Métrica do Portão (DoD):** esteira estabilizada em **119 testes verdes** (meta 116+ superada) com zero vazamentos.

O sistema opera em **Modo Autônomo Permanente** (cron 6h no GitHub Actions + persistência direta no Neo4j AuraDB e Qdrant Cloud via Space).

---

## 📜 Histórico de Sprints Concluídas

- `v1.2.0-alpha` — Correção de `/health` e TLS `neo4j+s://` do AuraDB.
- `v1.3.0-alpha` — Integração de tooling (MCP, subagents, Agent-Reach, browser-use, Strix).
- `v1.4.0-alpha` — Atendimento conversacional, malha de seeds e quórum modular.
- `v1.5.0-alpha` — Resolução vetorial de entidades + schema canônico via LLM.
- `v1.6.0-alpha` — Extração LLM canônica (`LLMCanonicalExtractor` + `/api/extract`).
