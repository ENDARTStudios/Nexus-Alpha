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

## v1.14.0 — Integração LlamaFactory (opt-in)

### Decisão executiva
- O freeze de `v1.13.0` é levantado **apenas** para este escopo aditivo e opt-in.
- Itens de qualidade semântica de `v1.13.0` permanecem no backlog e não são removidos.
- LlamaFactory **não** entra no runtime principal nem no CI.
- Fine-tuning roda externamente, preferencialmente em Kaggle/GPU, com Python 3.11–3.13.

### Escopo
- Exportar fatos verificados do grafo para dataset SFT no formato Alpaca/JSONL.
- Gerar configuração LoRA/SFT YAML compatível com LlamaFactory.
- Criar CLI wrapper opt-in em `scripts/train_lora.py`.
- Não implementar serving, merge de adapter ou integração com `llm_provider.py`.

### Tarefas mapeadas
| Issue | Descrição | Arquivos afetados |
|---|---|---|
| #038 | Exportação de fatos verificados para dataset Alpaca/JSONL | `src/training/dataset.py`, `src/database/graph_connector.py`, `scripts/train_lora.py` |
| #039 | Geração de configuração LoRA/SFT para LlamaFactory | `src/training/config.py`, `config/llamafactory/sft_lora.yaml`, `scripts/train_lora.py` |
| #040 | CLI wrapper opt-in + testes sem dependência de torch/llamafactory | `scripts/train_lora.py`, `src/training/runner.py`, `tests/test_training_sft.py`, `requirements-llamafactory.txt` |

### Arquivos novos
- `requirements-llamafactory.txt`
- `src/training/__init__.py`
- `src/training/dataset.py`
- `src/training/config.py`
- `src/training/runner.py`
- `scripts/train_lora.py`
- `config/llamafactory/sft_lora.yaml`
- `tests/test_training_sft.py`

### Arquivos alterados
- `SPRINT.md`
- `src/database/graph_connector.py`
- `.gitignore`
- `README.md`

### Fora de escopo
- Alterar `requirements-dev.txt`.
- Alterar `.github/workflows/`.
- Importar `torch` ou `llamafactory` no runtime normal.
- Instalar LlamaFactory no CI.
- Fazer serving/merge do adapter fine-tuned.
- Baixar quórum de verificação para aumentar dataset.

### Definition of Done
- `python -m pytest -q` permanece verde, incluindo novos testes.
- `git diff -- requirements-dev.txt .github/workflows/` fica vazio.
- `python scripts/train_lora.py export --limit 100` gera:
  - `data/sft/nexus_verified_facts.jsonl`
  - `data/sft/dataset_info.json`
- `python scripts/train_lora.py config` gera YAML válido em `config/llamafactory/sft_lora.yaml`.
- `python scripts/train_lora.py train`, sem LlamaFactory instalado, retorna erro amigável, sem traceback cru.
- Nenhum segredo aparece nos arquivos novos ou nos payloads/testes.

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

---

## ⚠️ Exceção de governança — commit `2a41622`

O commit `2a41622` misturou escopos ao incluir arquivos da v1.14.0 (LlamaFactory opt-in)
e do item 3-lite da v1.13.0 no mesmo commit.

**Decisão:** manter o commit por segurança operacional — já foi enviado ao remoto
(`push`) e o CI está verde. Não será revertido nem reescrito (sem `force-push`).

**A partir do próximo commit:** voltar à regra de **1 item por commit** e evitar
`git add -A` sem inspeção prévia. Fluxo padrão:

```powershell
git status
git add <paths específicos>
git diff --cached
git commit
```

A v1.14.0 permanece inerte no runtime do Space (o `Dockerfile` instala apenas
`requirements-hf.txt`).

---

## v1.13.0 — item 3.1: Predicate Mapper determinístico + quarentena

### Motivação (medida)
O refinador (item 3-lite) removeu ruído, mas a extração heurística ainda produzia
predicados fora do vocabulário controlado (`PRESERVIR`, `TEÓRICAR`, `AMIGÁVEL`…),
derrubando ~94% das triplas e travando a corroboração cross-source.

### Escopo
- `src/cognition/predicate_mapper.py`: `map_predicate(raw) -> (canonical | None, reason)`
  com normalização (minúsculas, sem acento, sem pontuação) e vocabulário controlado
  **auditável e limitado** (<= 30).
- `src/cognition/triple_refiner.py`: `refine_triple_ex` com motivo
  (`ok`/`missing_entity`/`unmapped_predicate`/`self_loop`) + `RejectionQuarantine`
  **volátil** (`/tmp`), **limitada** (10k, rotação) e **nunca promovida ao grafo**.
- `app.py`: métricas `extraction_quality.rejection_reasons`,
  `top_unmapped_predicates` e `quarantine`.

### Regras mantidas
- **Não** usar embedding para promover fato (não altera quórum).
- Quórum de triangulação permanece **3**.
- Sem dependência pesada nova no runtime.

### Backlog determinístico
Mapear os predicados mais frequentes de `top_unmapped_predicates` (20 itens) com
teste por par `raw → canonical`. Se `canonical_triples ↑` mas
`cross_source_matches` ficar estável, o gargalo passa a ser entidade/segmentação.

---

## v1.13.0 — #043: Guard determinístico de predicado no EntityExtractor

### Diagnóstico (medido)
O `predicate_mapper` só recuperou +2 triplas. Os rejeitados mais frequentes eram
**não-verbos** (`YEAR`, `THROUGH`, `STORY`, `CODER`, `DEEPR`) — o spaCy PT aplicado
a conteúdo EN/misto emite substantivos/funções como predicado. O gargalo é
**segmentação/seleção de predicado**, não vocabulário.

### Escopo
- `predicate_mapper.validate_predicate(raw) -> (canonical | None, reason)`:
  guard puro, determinístico, com motivos
  `numeric_predicate`, `url_or_code_predicate`, `stopword_predicate`,
  `nonverbal_predicate`, `unmapped_predicate`, `invalid_predicate`.
- `EntityExtractor` aplica o guard **na origem** (não gera tripla inválida) e
  expõe `rejection_reasons` para log.
- `triple_refiner.refine_triple_ex` usa o mesmo guard (protege o grafo server-side).
- Métricas: `extraction_quality.rejection_reasons` granular +
  `top_invalid_predicates` (além de `top_unmapped_predicates`).

### Invariantes mantidas
- Sem LLM, sem embedding promotor, sem mudança de quórum (3).
- `unmapped_predicate` fica reservado a **verbos legítimos** fora do vocabulário
  (backlog #044); lixo vira `invalid_predicate`/`nonverbal_predicate`.

