# 🏁 Sprint Governance & Backlog Log — Nexus-Alpha

Este documento estabelece o escopo de execução exclusivo para a **Sprint Atual**.
Nenhum agente, modelo de IA ou desenvolvedor pode realizar alterações em arquivos
ou introduzir dependências que não estejam explicitamente mapeadas neste documento.

---

## 📅 Sprint Atual: `v1.9.0-alpha` — Cérebro Espelhado (Memória Cognitiva)

- **Status:** 🟢 Planejada / Em Execução
- **Impacto:** Alto (arquitetura cognitiva: working/episódica/semântica + consolidação)
- **Complexidade:** Média (Hebbian, replay de episódios e associação inversa)

### 🎯 Funcionalidade Alvo e Escopo

Espelhar a **lógica cognitiva** do cérebro humano sobre o grafo de conhecimento
(memória hierárquica córtex/hipocampo, *Hebbian learning*, consolidação em
"sono" e associação inversa automática).

> **Nota de viabilidade:** o conectoma humano literal (86 bi de neurônios, BigBrain
> ~1 TB) **não** é acessível/copiável e não caberia na infra gratuita. Referências
> conceituais dos atlas (EBRAINS Julich-Brain/BigBrain, Allen Human Brain Atlas,
> Scalable Brain Atlas do INCF) são usadas apenas como **taxonomia de regiões** —
> nenhum dado foi copiado.

### 📋 Tarefas Mapeadas (Mapeamento de GitHub Issues)

#### [Issue #030] — Sistema de Memória Cerebral
- **Descrição:** `WorkingMemory` (slots com decaimento), `EpisodicMemory` (log
  temporal append-only) e `BrainMemorySystem` (consolidação + Hebbian).
- **Arquivos Afetados:** `src/brain/regions.py`, `src/brain/memory.py`,
  `tests/test_brain_memory.py` (Criação).
- **Critérios de Conclusão:** consolidação promove fatos repetidos e cria a
  associação inversa correspondente.

#### [Issue #031] — Persistência Semântica e Endpoints
- **Descrição:** `GraphConnector.consolidate_facts` (Hebbian: `replays`/`peso`) e
  rotas `/api/brain/stats|activate|episode|consolidate`.
- **Arquivos Afetados:** `src/database/graph_connector.py`, `app.py`,
  `scripts/worker_cycle.py` (Modificação).
- **Critérios de Conclusão:** cada ingestão vira episódio; cada ciclo roda a
  consolidação.

---

## 🛡️ Critérios de Aceitação (Definition of Done)

1. **Gate de CI:** suíte em **137 testes verdes** + anti-leak verde.
2. **Degradação Graciosa:** sem Neo4j, a consolidação retorna 0 sem quebrar.

---

## 📜 Histórico de Sprints Concluídas

- `v1.2.0-alpha` — Correção de `/health` e TLS `neo4j+s://` do AuraDB.
- `v1.3.0-alpha` — Integração de tooling (MCP, subagents, Agent-Reach, browser-use, Strix).
- `v1.4.0-alpha` — Atendimento conversacional, malha de seeds e quórum modular.
- `v1.5.0-alpha` — Resolução vetorial de entidades + schema canônico via LLM.
- `v1.6.0-alpha` — Extração LLM canônica (`LLMCanonicalExtractor` + `/api/extract`).
- `v1.7.0-alpha` — Consolidação, caixa alta total e rate limiting.
- `v1.8.0-alpha` — Motor GraphRAG (subgrafos 1–2 saltos no chat).
