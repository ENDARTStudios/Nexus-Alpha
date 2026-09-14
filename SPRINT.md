# 🏁 Sprint Governance & Backlog Log — Nexus-Alpha

Este documento estabelece o escopo de execução exclusivo para a **Sprint Atual**.
Nenhum agente, modelo de IA ou desenvolvedor pode realizar alterações em arquivos
ou introduzir dependências que não estejam explicitamente mapeadas neste documento.

---

## 📅 Sprint Atual: `v1.6.0-alpha` — Schema Canônico Baseado em LLM

- **Status:** 🟢 Planejada / Em Execução
- **Impacto:** Crítico (resolução do gargalo de extração heterogênea via inferência guiada)
- **Complexidade:** Alta (orquestração de prompts estritos e validação estrutural pós-inferência)

### 🎯 Funcionalidade Alvo e Escopo

Substituir (de forma **opt-in**) a extração heurística por um pipeline baseado em
LLM operando sob um **vocabulário controlado de predicados** e entidades
normalizadas. Isso garante uniformidade estrutural na raiz da coleta, forçando a
colisão de triplas semanticamente equivalentes e destravando `verified_facts`.

> **Fallback obrigatório:** sem `NEXUS_LLM_BASE_URL` configurado, o extrator LLM
> devolve vazio e o pipeline cai no extrator heurístico (spaCy/regex) — nunca
> deixa de produzir fatos.

### 📋 Tarefas Mapeadas (Mapeamento de GitHub Issues)

#### [Issue #025] — Construção do `LLMCanonicalExtractor`
- **Descrição:** extração guiada por schema JSON usando o `llm_provider` nativo,
  com filtro de predicados autorizados (`UTILIZA`, `EXECUTA`, `PRODUZ`, …).
- **Arquivos Afetados:** `src/cognition/llm_extractor.py` (Criação),
  `tests/test_llm_extractor.py` (Criação),
  `src/cognition/llm_provider.py` (`generate_text` síncrono).
- **Critérios de Conclusão:** retorno estrito de JSON parseável e triplas
  normalizadas, sem lixo descritivo.

#### [Issue #026] — Acoplamento do Novo Extrator no Core e na API
- **Descrição:** injetar o extrator no `src/main.py`, no worker
  (`scripts/worker_cycle.py`) e expor `POST /api/extract` no Space.
- **Arquivos Afetados:** `src/main.py`, `scripts/worker_cycle.py`, `app.py`.
- **Critérios de Conclusão:** elevação mensurável nos `verified_facts` após ciclos
  sobre as seeds híbridas, mantendo o quórum em 3.

---

## 🛡️ Restrições de Deploy e Critérios de Aceitação (Definition of Done)

1. **Gate de CI Estrito:** a suíte expande para **111+ testes verdes**.
2. **Fallback Garantido:** sem LLM configurado, a ingestão heurística permanece
   funcional (nenhum ciclo produz zero fatos).

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
