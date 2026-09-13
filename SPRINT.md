# 🏁 Sprint Governance & Backlog Log — Nexus-Alpha

Este documento estabelece o escopo de execução exclusivo para a **Sprint Atual**.
Nenhum agente, modelo de IA ou desenvolvedor pode realizar alterações em arquivos
ou introduzir dependências que não estejam explicitamente mapeadas neste documento.

---

## 📅 Sprint Atual: `v1.5.0-alpha` — Resolução Vetorial e Colisão Dinâmica

- **Status:** 🟢 Planejada / Em Execução
- **Impacto:** Crítico (cura da dispersão filológica de entidades compostas)
- **Complexidade:** Média (acoplamento de similaridade de cosseno no fluxo de ingestão)

### 🎯 Funcionalidade Alvo e Escopo

Complementar o modelo heurístico de sinônimos estáticos (`SemanticCanonicalizer`)
com um algoritmo de **clustering semântico por embeddings**. Entidades com
proximidade vetorial acima do limiar colapsam automaticamente sob o mesmo nó
canônico no Neo4j AuraDB, forçando o acúmulo honesto de confirmações para a
promoção de `verified_facts` (quórum estrito mantido em 3).

> **Nota técnica:** o embedding local (`src/cognition/embeddings.py`) é *lexical*
> (feature hashing). Pares near-duplicados pontuam ~0.82, então o limiar efetivo é
> **0.80** (o valor 0.88 era calibrado para embeddings semânticos densos).

### 📋 Tarefas Mapeadas (Mapeamento de GitHub Issues)

#### [Issue #023] — Desenvolvimento do Módulo `EntityResolver`
- **Descrição:** resolvedor vetorial usando o utilitário nativo de embeddings, com
  cache volátil por instância/rodada.
- **Arquivos Afetados:** `src/cognition/entity_resolver.py` (Criação),
  `tests/test_entity_resolver.py` (Criação), `src/cognition/embeddings.py`
  (novas funções `get_embedding`/`cosine_similarity`).
- **Critérios de Conclusão:** fusão de termos textualmente distintos mas próximos
  (ex.: `IA Generativa` ↔ `IA Generativa (GenAI)`).

#### [Issue #024] — Integração Cirúrgica no Pipeline e na API
- **Descrição:** injetar o resolvedor logo após a canonicalização, antes do
  validador de quórum.
- **Arquivos Afetados:** `src/main.py` (Modificação), `app.py` (Modificação).
- **Critérios de Conclusão:** incremento mensurável em `verified_facts` mantendo o
  quórum de triangulação fixado em 3.

---

## 🛡️ Restrições de Deploy e Critérios de Aceitação (Definition of Done)

1. **Gate de CI Estrito:** a expansão eleva a suíte para **107+ testes verdes**, sem
   quebras nos construtores do `test_main.py`.
2. **Preservação de Acrônimos:** o resolvedor não corrompe siglas (`MIT`, `AI`, `IA`).

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
- `v1.10.0-alpha` — Malha de seeds (allowlist tech) + canonicalização léxica (`SemanticCanonicalizer`).
