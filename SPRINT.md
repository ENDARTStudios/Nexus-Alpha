# 🏁 Sprint Governance & Backlog Log — Nexus-Alpha

Este documento estabelece o escopo de execução exclusivo para a **Sprint Atual**.
Nenhum agente, modelo de IA ou desenvolvedor pode realizar alterações em arquivos
ou introduzir dependências que não estejam explicitamente mapeadas neste documento.

---

## ✅ Sprint Concluída / ENCERRADA (CLOSED): `v1.12.0-beta` — Memória Episódica Durável

- **Status:** 🟣 CONCLUÍDA / ENCERRADA
- **Impacto:** Alto (o hipocampo sobrevive a restarts do Space)
- **Complexidade:** Média (modelo `:Episodio` + agregação + retenção)
- **Entregas:** `:Episodio` durável (`fact_hash + day`, MERGE idempotente); índices
  (`created_at`, `last_seen_at`, `status`, `fact_hash`); leitura durável com fallback
  (`source`); retenção 30d/10k; marcação de consolidados; `cognitive_health` no
  `/api/metrics`; `scripts/stress_episodes.py`.
- **Evidência:** 422 episódios sobreviveram a um restart do Space; estresse de 1.000 nós
  (≈1.100 nós/s, leitura <0,2s) com a retenção limpando os sintéticos corretamente.
- **DoD:** 146 testes verdes + allowlist do proxy (7/7) + anti-leak.
- **Decisão executiva:** **NÃO** criar cron separado de consolidação — o worker de 6h já
  consolida; um cron extra duplicaria `replays`/peso hebbiano e criaria corrida no Neo4j.

---

## 🧊 Scope Freeze — próximo ciclo (`v1.13.0`)

**Congelamento de infraestrutura por 2–3 ciclos (12–18h) em produção.** A próxima
evolução não é infraestrutura, mas **qualidade semântica**:

1. Canonicalização/entity linking de entidades (sinônimos reais).
2. Embeddings contextuais mais ricos (trocar o modelo base se necessário).
3. Refino do prompt do CoT para reduzir falsos positivos na extração de triplas.

Nenhuma alteração de código até a observabilidade confirmar a estabilidade da retenção
automática.

### 🎯 Funcionalidade Alvo e Escopo (histórico desta sprint encerrada)

Persistir episódios no Neo4j para que a memória episódica **não se perca** quando o
Space reinicia (o bucket em `data/` é somente-leitura e o `$TMPDIR` é efêmero).

**Anti-inflação:** agregação por `fact_hash` + `day` (MERGE idempotente) — o mesmo
fato no mesmo dia incrementa `replays` em vez de criar micro-eventos.

### 📋 Tarefas Mapeadas (GitHub Issues)

#### [Issue #036] — Modelo `:Episodio` + persistência idempotente
- **Descrição:** `fact_hash = sha256(subject|predicate|object)` normalizado; MERGE
  por `(fact_hash, day)`; status agregado.
- **Arquivos Afetados:** `src/database/graph_connector.py`,
  `src/brain/memory.py` (`fact_hash`, `episode_payloads`), `app.py`.
- **Critérios:** repetição no mesmo dia vira `replays`; `MERGE` idempotente.

#### [Issue #037] — Leitura durável, índices e retenção
- **Descrição:** `/api/brain/episodes` lê o Neo4j (fallback volátil); índices por
  `created_at`/`status`/`fact_hash`; retenção 30 dias OU 10.000 episódios no
  ciclo de consolidação; marcar episódios consolidados.
- **Arquivos Afetados:** `src/database/graph_connector.py`, `app.py`.
- **Critérios:** episódios persistem após restart; retenção poda sem destruir o grafo.

---

## 🛡️ Critérios de Aceitação (Definition of Done)

1. **Gate de CI:** suíte em **146 testes verdes** (inclui degradação offline).
2. **Contadores:** hebbian/consolidado permanecem derivados do grafo.

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
- `v1.11.0-alpha` — Proxy server-side (Space privado) + métricas duráveis + allowlist.

