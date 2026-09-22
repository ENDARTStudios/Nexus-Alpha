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

## v1.13.0 (item 3-lite) — Refino determinístico de extração

### Decisão executiva
- Ponto único de alavanca: normalização no choke point do ingest (`/api/ingest` →
  `refine_triple` → `chave` do Neo4j). Nada no Cypher dobra acentos/remove artigos.
- Sem LLM, sem baixar quórum (mantido em 3), sem promover fato por embedding
  (regra de ouro: embedding só como sugestão, item 2).
- Fallback determinístico para entidades desconhecidas (#041): colapsar é
  obrigatório; acentos de desconhecidas são foldados (trade-off aprovado —
  acentos se preservam via alias no dicionário, não via original arbitrário).
- Limitação honesta: tokens distintos (`Clube` vs `Club`) NÃO colapsam por fold;
  exigem alias ou item 2.

### Tarefas mapeadas
| Issue | Descrição | Arquivos afetados |
|---|---|---|
| #041 | Fold NFKD + artigos iniciais + hífen na chave de lookup; dicionários reconstruídos com chaves foldadas (falha alto em colisão); fallback determinístico UPPER | `src/cognition/canonicalizer.py`, `tests/test_canonicalizer.py` |
| #042 | Refiner via `map_predicate`; EXTRA_MAP reflexivo (`conecta se[a]`, `utiliza se`); teste golden cross-extractor | `src/cognition/triple_refiner.py`, `src/cognition/predicate_mapper.py`, `tests/test_predicate_mapper.py`, `tests/test_extraction_equivalence.py` |
| #043 | Guard `validate_predicate` (numérico/URL/stopword/não-verbal vs `unmapped`) + guard no `EntityExtractor` (spaCy e fallback) + observabilidade de rejeição | `src/cognition/predicate_mapper.py`, `src/cognition/extractor.py`, `app.py`, `tests/test_extractor.py`, `tests/test_triple_refiner.py`, `tests/test_graph_topology.py` |
| #044 | (backlog) Expandir `EXTRA_MAP` a partir de `top_unmapped_predicates` | futuro |

### Fora de escopo
- Alterar `requirements-dev.txt`, `.github/workflows/`, quórum, `TriangulationFilter`
  (content-blind, fora do path de produção), `EntityResolver` no ingest (item 2),
  `graph_connector.py`, recanonicalização de nós históricos (`scripts/recanonicalize_facts.py` futuro).

### Definition of Done
- `python -m pytest -q` verde (195); `git diff -- requirements-dev.txt .github/workflows/` vazio.
- Golden: `usa`/`utiliza`/`UTILIZA` → `UTILIZA`; `conecta-se a` → `CONECTA_A`;
  `José`≡`Jose`; `A IA`≡`IA`; `zapearia`→`invalid_predicate`, `publicar`→`unmapped_predicate`.
- Anti-leak: nenhum segredo nos arquivos/payloads/testes.
- **Nota de fragmentação:** a `chave` do `:Fato` é calculada no ingest — nós
  históricos fragmentados NÃO se fundem sozinhos. A subida de
  `cross_source_matches`/`verified_facts` só é mensurável após **re-ingest
  controlado** (backup → zerar → deploy → worker com seeds → comparar
  `raw_triples`/`canonical_triples`/`rejected_noise`/`cross_source_matches`/`verified_facts`).
  Sem re-ingest, métrica flat não invalida o código.
- Gate de treino (inalterado): `records >= 50`, `verified_facts >= 10`, sem
  segredos, YAML válido → só então smoke Kaggle (`epochs 1, batch 2, grad_accum 2, max_samples 100`).

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

---

## v1.13.0 — #044: expansão conservadora do predicate mapper (aliases PT)

### Contexto
Após o #043, `top_invalid_predicates` ficou vazio e os rejeitados passaram a ser
**verbos legítimos**. `verified_facts` foi de 2 → 3, `cross_source_matches` de 10 → 11.

### Escopo
Aliases determinísticos de alta confiança em `src/cognition/predicate_mapper.py`:
- `ter/tem/tinha/teve/temos/terei/teria/terão` → **POSSUIR**
- `incluir/inclui/incluiu/incluindo/incluído` → **CONTIENE**
- `aplicar/aplica/aplicou/aplicando/aplicado` → **UTILIZA**
- `publicar/publica/publicou/publicando/publicado` → **PRODUZ**
- `desenvolver/desenvolve/desenvolveu/desenvolvendo/desenvolvido` → **PRODUZ**

Rejeições com motivo próprio (não mapeadas):
- **`modal_predicate`**: `poder/pode/poderia/…`, `dever/deve/deveria/…`
- **`ambiguous_predicate`**: `passar/passou/…`, `aumentar/aumentou/…`
- `descrever/descreve/descreveu` → seguem `unmapped_predicate` (meta-relação).

### Nota de contrato
O motivo de sucesso do mapper permanece `"ok"` (consistente com os testes
committed de voz reflexiva). O `rejection_reasons` ganhou as chaves
`modal_predicate`/`ambiguous_predicate` sem alterar `app.py` (o contador é dinâmico).

---

## ⚠️ Exceção de governança — commit `712724d`

O commit `712724d` (hotfix do guard: nomes canônicos com `_`) foi enviado junto com
os commits `ae3ceea` (#041) e `8088295` (#042) para **alinhar Space e `main`**, já
que o deploy do Space envia a árvore de trabalho (disco), não o commit.

**Decisão:** manter (sem reverter). Próximas mudanças voltam à regra de **1 item por
commit** com staging explícito (sem `git add -A`).

---

## v1.13.0 — #046: Auditoria de near-match cross-source (metric-only)

### Escopo (read-only)
- `src/cognition/cross_source_audit.py` — funções puras (similaridade lexical,
  classificação de near-match, relatório) — **nunca** promove fato nem altera
  `confirmacoes`; sem Qdrant (vetores stale).
- `scripts/audit_cross_source.py` — CLI read-only sobre `:Fato`/`:FonteWeb`.
- `tests/test_cross_source_audit.py` — puros, sem Neo4j.

### Resultado (pós-reset, 106 fatos)
```text
facts_total = 106  |  one_domain = 106  |  two_or_more_domains = 0
near_matches.high = 0  |  near_match_rate_high = 0.0
potential_verified_if_linking = 0
mismatch_types = { subject_variant:0, object_variant:0, predicate_variant:0, true_unique:106 }
```

### Achados importantes
1. **`confirmacoes` conta URLs, não domínios.** O único fato "cross-source" tinha
   `confirmacoes=4` com **4 URLs do mesmo domínio** (`pt.wikipedia.org`). Logo,
   `cross_source_matches` (confirmacoes>=2) **superestima** independência. A
   auditoria por domínio (host) é a medida correta → **0**.
2. **Objetos extraídos são fragmentos, não entidades** — amostra real:
   `ARTHUR SAMUEL --DEFINE--> EM 1959`, `ALGORITMO BACKPROPAGATION --UTILIZA--> COM ISSO`,
   `AREA DE REDES NEURAIS --POSSUIR--> APOS A PUBLICACAO EM 1986`,
   `SERVICO DE STREAMING DE MUSICA --PRODUZ--> EM 2015`.
   Datas, orações e locuções adverbiais como objeto → triplas sem valor semântico,
   impossíveis de corroborar por construção.

### Leitura
`mismatch_types` é 100% `true_unique`, mas a causa **não é falta de corpus nem falta
de aliasing** — é **qualidade da extração (span do objeto/sujeito)**. Antes de #047
(aliasing) ou #048 (seeds), o gargalo é **validação de objeto**: rejeitar objetos
que sejam data, oração ou locução preposicional.

---

## v1.13.0 — #049: Corroboração por domínio distinto (protocolo de verificação)

### Motivação
`confirmacoes` contava **URLs**, não domínios: 4 páginas de `pt.wikipedia.org`
inflavam `confirmacoes=4`. Isso viola o contrato anti-fake-news ("corroborado por
domínios independentes").

### Escopo (commit único)
- `graph_connector.domain_from_url()` — host minúsculo, sem `www.`, sem path/query/porta.
- `INGEST_QUERY`: grava `f.domain = $domain` em `:FonteWeb` e passa a contar
  `count(DISTINCT ff.domain)` (antes `count(DISTINCT ff)`).
- `SNAPSHOT_QUERY`: expõe `max_confirmacoes`.
- `app.py /api/metrics`: bloco `verification`
  (`quorum`, `facts_with_multi_domain`, `max_domain_confirmations`,
  `verified_facts_domain_independent`).

### Invariantes
- **Quórum mantido em 3** (não baixar).
- `verified_facts` passa a significar **domínio independente**; se cair, é a métrica
  ficando honesta (não regressão).

---

## v1.13.0 — #050: Validador determinístico de span de entidade

### Motivação
O audit (#046) mostrou objetos que são **fragmentos**, não entidades: `EM 1959`,
`COM ISSO`, `APOS A PUBLICACAO EM 1986`, `COMO OBJETIVO`. Triplas assim são
impossíveis de corroborar.

### Escopo
- `src/cognition/span_validator.py` — puro e determinístico:
  `validate_entity_span(span, role, known_entities)` /
  `reject_reason_for_span(...)`. Regras: data/ano, numérico, locução
  preposicional/adverbial, pronome, fragmento oracional, quantificador (sujeito),
  stopword inicial, comprimento excessivo, pontuação/código. Whitelist do
  dicionário canônico (`known_entities`).
- `triple_refiner.refine_triple_ex` valida subject/object (sobre o span bruto)
  **antes** de gravar; motivo vai para quarentena/métricas (dinâmico).
- **Sem** LLM, **sem** embedding, **sem** `torch`/`llamafactory`.

### Dry-run (read-only, 106 fatos atuais)
```text
facts_total = 106  |  would_pass = 67  |  would_reject = 39
reject_reasons = { object_date_like:14, object_prepositional_phrase:14,
                   subject_quantifier_phrase:8, object_adverbial_phrase:1,
                   object_generic_phrase:2 }
```
`EM 1959`, `COM ISSO`, `APOS A PUBLICACAO EM 1986`, `MAIORIA ...` são rejeitados;
entidades legítimas (`Inteligência Artificial`, `Santos FC`) passam.

### Observação
Validador v1 **conservador**; fatos borderline (`OBJETIVO --APRENDE--> REGRA GERAL
QUE MAPEIA`) ainda passam e podem ser tratados em iteração futura.

---

## v1.13.0 — #051: Auditoria read-only pós-limpeza (diagnóstico de alavanca)

### Escopo (read-only, sem deploy)
- `src/cognition/cross_source_audit.py`: `domain_coverage()`, `reconcile_pipeline()`,
  e `potential_verified_if_aliasing` no relatório.
- `scripts/audit_post_clean.py`: reconcile + cobertura + near-match + predicate health.
- `tests/test_cross_source_audit_post_clean.py`.

### Resultado (66 fatos limpos)
```text
pipeline_reconciliation = { raw:209, canonical:78, rejected:130, persisted:66,
                            canonical_to_fact_gap:12, unaccounted_raw:1,
                            same_domain_multi_url_merge:1 }
domain_coverage = { facts_total:66, domains_total:13, one_domain:66, multi_domain:0 }
near_matches = { high:0, medium:0, low:0 }
potential_verified_if_aliasing = 0
mismatch_types = { subject_variant:0, object_variant:0, predicate_variant:0, true_unique:66 }
predicate_health = { unmapped:49, modal:26, ambiguous:11,
  top_unmapped: DESCREVER 6, DAR 4, VIR 3, DIVIDIR 2, CONSTRUIR 2, IR 2,
                PERMITIR 2, IMPLEMENTAR 2, IDENTIFICAR 2, ANALISAR 2 }
```

### Diagnóstico do gap canonical→facts
`19` URLs distintas confirmam `66` fatos (`14` URLs confirmam >1 fato) e há `0`
chaves duplicadas. O gap de `12` vem de triplas canônicas **repetidas entre payloads
com a mesma `source_url`** (o `MERGE` reusa `FonteWeb`/`:Fato` sem nova confirmação).
`canonical_triples` conta **por payload**, não por chave distinta → **lacuna de
observabilidade (#052)**.

### Alavanca indicada
- near-match `high = 0` ⇒ **não** é aliasing de entidade/objeto (#047).
- `top_unmapped` sem verbos claros recorrentes (`>=3`) ⇒ **não** é predicate mapper (#045).
- `true_unique = 66` ⇒ **cobertura de corpus (#048)**.
- `canonical_to_fact_gap = 12 (> 5)` parcialmente explicado ⇒ **#052 (observabilidade) tem prioridade**.

