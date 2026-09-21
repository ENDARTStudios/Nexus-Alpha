# 🏁 Sprint Governance & Backlog Log — Nexus-Alpha

Este documento estabelece o escopo de execução exclusivo para a **Sprint Atual**.
Nenhum agente, modelo de IA ou desenvolvedor pode realizar alterações em arquivos
ou introduzir dependências que não estejam explicitamente mapeadas neste documento.

---

## 📅 Sprint Atual: `v1.11.0-alpha` — Acesso Seguro do Frontend (Proxy Vercel)

- **Status:** 🟢 Planejada / Em Execução
- **Impacto:** Altíssimo (destrava BrainPanel, grafo e chat sem expor o Space)
- **Complexidade:** Média (rota proxy server-side + consolidação de métricas)

### 🎯 Funcionalidade Alvo e Escopo

Manter o Space **privado** e criar um **proxy server-side** (`/api/nexus/*`) que
injeta `Authorization: Bearer <HF_TOKEN>` + `X-Nexus-Token: <NEXUS_API_TOKEN>`.
O browser nunca vê credencial alguma.

### 📋 Tarefas Mapeadas (GitHub Issues)

#### [Issue #034] — Proxy catch-all `/api/nexus/[...path]`
- **Descrição:** rota Next.js que encaminha GET/POST ao Space privado com os tokens
  server-side; frontend passa a usar `nexusUrl()` (proxy por padrão, direto só se
  `NEXT_PUBLIC_NEXUS_API_URL` estiver definido).
- **Arquivos Afetados:** `src/app/api/nexus/[...path]/route.ts`,
  `src/frontend/lib/nexus.ts`, `src/frontend/lib/brain.ts`,
  `src/frontend/lib/api.ts`, `src/frontend/components/KnowledgeGraph.tsx`.
- **Critérios:** Space permanece privado; nenhuma resposta contém segredos.

#### [Issue #035] — Métricas duráveis e atômicas
- **Descrição:** `hebbian_pairs` deixa de usar memória volátil e passa a derivar do
  grafo; todos os contadores em **uma única consulta** (`graph_snapshot`), evitando
  zeros transitórios no cold-start do Space.
- **Arquivos Afetados:** `src/database/graph_connector.py`, `app.py`,
  `tests/test_brain_memory.py`.
- **Critérios:** contadores consistentes e persistentes entre restarts.

### 🔑 Variáveis (Vercel — somente servidor, NUNCA em `NEXT_PUBLIC_*`)
```
NEXUS_SPACE_URL=https://<user>-<space>.hf.space
HF_TOKEN=hf_xxx
NEXUS_API_TOKEN=xxx
```

---

## 🛡️ Critérios de Aceitação (Definition of Done)

1. **Gate de CI:** suíte em **141 testes verdes** (contrato + anti-vazamento).
2. **Space Privado:** nenhum endpoint público novo; proxy é o único ponto de saída.

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
- `v1.10.0-alpha` — Painel Cérebro (contrato normalizado + `BrainPanel` read-only).

