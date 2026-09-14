# 🏁 Sprint Governance & Backlog Log — Nexus-Alpha

Este documento estabelece o escopo de execução exclusivo para a **Sprint Atual**.
Nenhum agente, modelo de IA ou desenvolvedor pode realizar alterações em arquivos
ou introduzir dependências que não estejam explicitamente mapeadas neste documento.

---

## 📅 Sprint Atual: `v1.7.0-alpha` — Escalonamento e Estabilização de Produção

- **Status:** 🟢 Planejada / Em Execução
- **Impacto:** Alto (expansão contínua da malha sob governança estrita de LLM)
- **Complexidade:** Baixa (monitoramento e ajustes finos de prompts e seeds)

---

## 🎯 Resultados Consolidados da Sprint Anterior (`v1.6.0-alpha`)

- **Módulo Entregue:** `LLMCanonicalExtractor` via DeepSeek-V3 Serverless Router.
- **Métricas Alcançadas:**
  - Total de Conceitos: **388**
  - Fatos Verificados (`verified_facts`): **1 ──► 2** 🎯
  - Vetores no Qdrant: **23**
- **Sucesso Empírico:** triangulação exata com quórum 3 para:
  1. `Inteligência Artificial --[UTILIZA]--> Aprendizado Profundo`
  2. `Inteligência Artificial --[UTILIZA]--> Machine Learning`
- **Status do Backlog:** **114 testes verdes** e gate anti-leak 100% validado.

---

## 📋 Escopo do Novo Ciclo (`v1.7.0-alpha`)

### [Issue #027] — Monitoramento Ativo e Alinhamento de Casos de Borda (Edge Cases)
- **Descrição:** monitorar triplas em 2x e eliminar variações de casing
  (`Generative Ai` vs `GENERATIVE AI`) com caixa alta total no pós-processamento.
- **Arquivos Afetados:** `src/cognition/llm_extractor.py` (Modificação),
  `tests/test_llm_extractor.py` (Modificação).
- **Critérios de Conclusão:** entidades sempre em caixa alta total, sem dispersão
  residual por capitalização.

---

## 🛡️ Restrições de Deploy e Critérios de Aceitação (Definition of Done)

1. **Zero Quebra de Contrato:** compatibilidade com `/api/graph/topology` (Next.js).
2. **Quórum Intacto:** triangulação obrigatória fixada em 3 domínios.

---

## 📜 Histórico de Sprints Concluídas

- `v1.2.0-alpha` — Correção de `/health` e TLS `neo4j+s://` do AuraDB.
- `v1.3.0-alpha` — Integração de tooling (MCP, subagents, Agent-Reach, browser-use, Strix).
- `v1.4.0-alpha` — Atendimento conversacional (`ChatService` + `/api/chat` + ChatWidget).
- `v1.5.0-alpha` — Hardening & eficiência (APOC-free, embeddings locais, singletons, `/api/metrics`).
- `v1.6.0-alpha` — Simulação de enxame (`/api/simulate`).
- `v1.7.0-alpha` — Qualidade de extração (spaCy pt) + memória vetorial.
- `v1.8.0-alpha` — Ruído, limpeza e corroboração real (`:Fato` + `verified_facts`).
- `v1.9.0-alpha` — Produção visual (scaffold Next.js, chat real, ForceGraph, CORS Vercel).
- `v1.10.0-alpha` — Malha de seeds (allowlist tech) + canonicalização léxica.
- `v1.11.0-alpha` — Resolução vetorial de entidades (`EntityResolver`).
- `v1.12.0-alpha` — Schema canônico via LLM (`LLMCanonicalExtractor` + `/api/extract`).
