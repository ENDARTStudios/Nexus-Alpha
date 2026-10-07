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

---

## v1.13.0 — #052: Observabilidade/contabilidade do ingest

### Motivação
O #051 revelou gap `canonical(78) → facts(66)` causado por contagem de **ocorrências**
canônicas, não de **chaves distintas**.

### Escopo
- `app.py`: classe `IngestAccounting` — `record_payload()` e `snapshot()`.
  Distingue **ocorrência canônica** de **chave canônica distinta** e classifica
  duplicação em `duplicate_same_source_url`, `duplicate_same_domain`,
  `duplicate_cross_domain`. Set de chaves **limitado** (10k); acima disso,
  `accounting_mode = approximate_overflow`.
- `/api/metrics`: bloco `ingestion_accounting`
  (`raw_triples`, `canonical_triples`, `distinct_canonical_keys`,
  `duplicate_canonical_occurrences`, `persisted_facts`, `canonical_to_fact_gap`,
  `unaccounted_raw`, `merged_into_existing_fact`, `new_facts_created`,
  `process_started_at`, `last_ingest_at`, `accounting_mode`).
- `tests/test_ingest_accounting.py`: duplicata intra-URL, mesmo domínio,
  cross-domain, reconciliação e anti-leak.

### Definições-chave
```text
canonical_triples                 = ocorrências refinadas (conta duplicatas)
distinct_canonical_keys           = chaves canônicas distintas
duplicate_canonical_occurrences   = canonical_triples - distinct_canonical_keys
canonical_to_fact_gap             = distinct_canonical_keys - persisted_facts
verified_facts sobe SÓ por duplicate_cross_domain (nunca same_domain/same_url)
```
O campo legado `extraction_quality.duplicate_canonical_triples` (dedup intra-payload)
é preservado.

### Fora de escopo
Mudança de quórum, promoção por embedding, expansão de seeds, treino LlamaFactory.

---

## v1.13.0 — #056: Domain reputation determinística (pré-requisito do #048)

### Motivação
Ao preparar o #048, medi o `SecurityProtocol`: **todo publisher comum (`.com`,
`.com.br`) recebe score 0.60 < 0.70 e vai para quarentena** no `fetch_and_verify`,
antes do ingest. Só `.edu`/`.gov`/`.ac.`/`.org` (0.9) e tech domains (0.8) passavam.
Logo, **cross-domain era impossível por construção** — o corpus só podia ser Wikipedia.

### Escopo
- `src/miner/security_protocol.py`: `REPUTABLE_PUBLISHERS` (allowlist curada:
  acervo do projeto, imprensa esportiva/geral, instituições do futebol, clubes
  oficiais) com match por **domínio registrável** (`host == d` ou `host.endswith("."+d)`)
  → score **0.85** (≥ limiar 0.70).
- `tests/test_domain_reputation.py` (publishers reputáveis não-quarentenados,
  match de subdomínio, tech/high-trust inalterados, desconhecidos/baixa-confiança
  seguem bloqueados, sem segredos/sociais).

### Invariantes
- **Quórum mantido (3)**; `.org`/`.edu`/`.gov` seguem 0.9; desconhecidos `.com`
  seguem 0.6 (quarentena); baixa-confiança (reddit/medium/wordpress) seguem 0.4.
- Sem embedding, sem LLM.

### Dívidas registradas (não implementadas)
- **#053** — Independência editorial por publisher/eTLD+1 (hoje é por host;
  `pt.` vs `en.wikipedia.org` contam como 2).
- **#054** — Ontologia temporal (`:Ano`/`:Periodo`; `OCORREU_EM`) para fatos datados.
- **#055** — Integração com a API REST do Almanaque (fonte estruturada primária).

---

## v1.13.0 — #048: Clusters curados de domínios independentes (futebol)

### Escopo
- `config/seed_clusters.yaml`: 4 clusters (Santos FC, Estádio Urbano Caldeira,
  Pelé/Santos, Garrincha/Botafogo). Cada cluster com **>=3 domínios**, **>=2
  publishers** e **>=1 publisher fora de Wikipedia**. URLs validadas manualmente
  (HTTPS/200/texto): `pt.wikipedia.org`, `en.wikipedia.org`, `santosfc.com.br`,
  `ge.globo.com`, `botafogo.com.br`.
- `src/miner/seed_loader.py`: `load_seed_clusters`, `validate_seed_clusters`,
  `cluster_to_seeds`, `manifest_health` (determinístico, PyYAML).
- `scripts/worker_cycle.py`: **complementa** as seeds atuais com os clusters
  (não remove nada).
- `tests/test_seed_clusters.py`: validação estrutural, HTTPS, domínio proibido,
  Wikipedia-only, duplicatas, anti-leak.

### Descartados na validação
- `almanaquedosclubes.com/clubes/santos` → **404**; raiz com apenas ~368 palavras.
- `cbf.com.br` → **ConnectError** (bloqueia).

### Invariantes
- Quórum 3; sem embedding/LLM; sem alterar predicate mapper/span validator/canonicalizer.
- `#053` (independência por publisher) permanece dívida: `pt.`/`en.wikipedia.org`
  ainda contam como 2 hosts (mesmo publisher).

### Critério de sucesso
`ingestion_accounting.duplicate_cross_domain > 0` e/ou
`verification.facts_with_two_or_more_domains > 0` após ciclo manual do worker.

### Resultado em produção (worker_dispatch com clusters)
```text
BASELINE: duplicate_cross_domain=0  facts_with_multi_domain=0  max_domain_conf=1  verified=0
POST    : duplicate_cross_domain=0  facts_with_multi_domain=0  max_domain_conf=1  verified=0
          distinct=108  persisted=108  gap=0  unaccounted=0
          duplicate_same_source_url=80  duplicate_same_domain=5
```
`cross_domain` **não subiu** → **Cenário 3** (domínios distintos, canonical não casa).

### Causa raiz (logs do worker)
1. **#056 funcionou** (bloqueio de reputação resolvido): as páginas não-wiki foram
   buscadas — `santosfc.com.br` (301→200), `ge.globo.com` (301→200), `botafogo.com.br` (200).
2. **Mas retornaram `entities_processed: 0`** — o refino rejeitou **todas** as triplas
   (páginas JS/listing/texto não-declarativo). Não-viraram `:Fato`.
3. As wiki PT/EN **geraram triplas**, porém **diferentes** entre si
   (mesmo fato com entidade/objeto em superfícies distintas: PT vs EN, sinônimos).
   Como o `#051` mostrou `near_match.high = 0` lexicalmente, a variação é
   **semântica** (tradução/sinônimo) — não resolvível por canonicalização/lexical.

### Leitura
O gargalo final **não é cobertura de domínios** nem reputação de fonte: é
**equivalência semântica entre fontes** (entidade/objeto em superfícies distintas).
Próximos candidatos (com evidência limpa): **item 2 — entity linking (diagnóstico,
sem promover fato)** ou **#047 — aliasing curado**.

---

## #057 — Entity linking read-only: diagnóstico de equivalência semântica

**Status:** ✅ concluída (código) · relatório gerado

### Por quê
O `#048` provou que **cobertura de domínios não é mais o gargalo** (fontes
buscadas, `gap=0`, `cross_domain=0`). O gargalo restante é **equivalência
semântica entre fontes**. O `#057` mede isso **sem tocar no grafo**.

### Regras de ouro
- similaridade **sugere** vínculo; **não** verifica fato, **não** altera quórum,
  **não** grava `:Fato`, **não** muda `confirmacoes`, **não** mescla nós.
- **Qdrant ignorado por completo** (vetores stale, sem `run_id` confiável).
- `medium` é **upper bound teórico**; só `high` alimenta revisão de alias curado.
- candidato exige `left.domains ∩ right.domains == ∅`, domínios não vazios e
  `fact_hash` distintos.
- predicado diferente **nunca** vira `high`.
- alias determinístico exige sigla expandida **no outro campo** + núcleo comum.
- Cypher do CLI validado por `assert_read_only_cypher` (bloqueia
  `MERGE/CREATE/SET/DELETE/REMOVE/DROP`).

### Arquivos
- `src/cognition/entity_linking_audit.py` (puro, sem Neo4j/Qdrant)
- `scripts/audit_entity_linking.py` (CLI read-only → `reports/`)
- `tests/test_entity_linking_audit.py` (13 testes, sintéticos)
- `reports/.gitignore` (`*` + `!.gitignore` — relatório nunca commita)

### Não altera
`app.py`, `graph_connector.py`, `worker_cycle.py`, `predicate_mapper.py`,
`span_validator.py`, `canonicalizer.py`, `triple_refiner.py`,
`config/seed_clusters.yaml`, `requirements*`, `.github/workflows/`, Qdrant.

### DoD
`python -m pytest -q` verde · `git diff -- requirements-dev.txt .github/workflows/`
vazio · relatório em `reports/entity_linking_audit_*.json` com
`candidate_pairs` / `potential_verified_if_*_aliasing` / `mismatch_types` /
`domain_coverage` / `examples` / `promote_automatically=false`.

### Leitura esperada
- **Cenário 1** (`high >= 3` e `potential_high >= 1`) → `#047` aliasing curado.
- **Cenário 2** (só `medium`) → inspeção manual dos top 20 exemplos.
- **Cenário 3** (tudo zerado) → `#058`/`#055` — problema é extração/fonte.
- **Cenário 4** (candidatos só PT/EN) → `#048.1` — trocar URLs não-wiki improdutivas.

### Resultado
Relatório: `reports/entity_linking_audit_2026-09-23.json` (local, gitignored).
```text
facts_total 108 · domains_total 13 · facts_with_2plus_domains 0
candidate_pairs: high=0  medium=0  low=0
potential_verified_if_high_aliasing   = 0
potential_verified_if_medium_aliasing = 0
mismatch_types: true_unique = 108 (demais = 0)
examples = []
domain_coverage.facts_by_domain:
  pt.wikipedia.org 66 · en.wikipedia.org 20 · demais 13 domínios tech = 22
  santosfc.com.br / ge.globo.com / botafogo.com.br = 0 fatos
```

### Veredito: **Cenário 3**
Assinatura exata (`high=0`, `medium=0`, `mismatch_types=true_unique`).
Diagnóstico read-only adicional (3.425 pares cross-domain elegíveis; 400 com
predicado igual) mostra que **não é limiar**: o par "mais quente" com predicado
igual tem `subj_sim=0.17` / `obj_sim=0.61` (`APRENDIZADO POR DICIONARIO ESPARSO
--UTILIZA--> VARIOS CONTEXTOS` vs `COMPATIBLE TO --UTILIZA--> VARIOUS APPLICATIONS`).

**Causa raiz mais profunda — a extração não produz fatos de conhecimento:**
```text
PELE --POSSUIR--> NESSE TORNEIO
PELE --POSSUIR--> GRANDE ATUACAO
GARRINCHA --EXECUTA--> TREINO
SANTOS --POSSUIR--> OUTRAS CINCO LOJAS FISICAS LOCALIZADAS
SANTOS WILL --UTILIZA--> IN PROFESSIONAL      (en.wikipedia, ruído)
```
Só **13/108** fatos citam futebol e todos são **fragmentos SVO heurísticos**
(sem entidade coerente: falta `Pelé --DEFENDEU--> Santos FC`). 100 sujeitos
distintos para 108 fatos → quase 1 fato por sujeito, sem redundância para
corroborar. Entity linking **não tem o que linkar**.

### Próximo issue (decisão do usuário)
- **#058** — melhorar extração de páginas declarativas e/ou trocar URLs não-wiki
  improdutivas dos clusters; ou
- **#055** — API REST do Almanaque como fonte estruturada (evita parsing JS/listing).

`#047` (aliasing curado) **não é o próximo passo** — não há pares candidatos.

### Invariantes
Quórum 3; sem embedding/LLM; sem promoção automática; gate de treino bloqueado
(`verified_facts_domain_independent = 0` < 10).

---

## #058 — Source extractability hardening / substituição de URLs improdutivas

**Status:** ✅ concluída (código + auditoria) · manifest atualizado

### Por quê
O `#057` provou **Cenário 3**: a extração gera fragmentos SVO heurísticos
(`PELE --POSSUIR--> NESSE TORNEIO`), sem entidade coerente de futebol. O `#048.1`
(auditoria de produtividade das URLs dos clusters) foi incorporado ao mesmo issue:
medir quais fontes produzem triplas e substituir as que não produzem.

### Regras de ouro
- auditoria **read-only** (sem Neo4j, sem Qdrant, sem `/api/ingest`, sem promoção);
- classificação `productive | weak | unproductive` é **só diagnóstica** — não altera
  quórum, `confirmacoes` nem `:Fato`;
- **não modifica** `extractor.py` (expansão de `DEFAULT_PREDICATES` seria ambígua
  → `#045.1`); verbos esportivos medidos via `FOOTBALL_VERBS`/`football_verb_hits`;
- **proibido** tocar em `app.py`, `graph_connector.py`, `predicate_mapper.py`,
  `canonicalizer.py`, `span_validator.py`, `triple_refiner.py`, `requirements*`,
  `.github/workflows/`, `llm_provider.py`, `src/training/`, Qdrant;
- domínios de aposta adicionados a `FORBIDDEN_DOMAINS` (`bet365`, `sportingbet`,
  `betano`, `betfair`).

### Arquivos
- `src/miner/source_productivity.py` (puro: sentenças, verbos, classificação,
  `payload_telemetry`, `summarize`)
- `scripts/audit_source_productivity.py` (CLI read-only → `reports/`)
- `tests/test_source_productivity_audit.py` (17 testes, sintéticos)
- `config/seed_clusters.yaml` (anotação `productivity` por fonte + refuerço
  `Botafogo_de_Futebol_e_Regatas` no cluster `garrincha_botafogo`)
- `scripts/worker_cycle.py` (1 log estruturado JSON por payload via
  `payload_telemetry`)
- `src/miner/seed_loader.py` (domínios de aposta em `FORBIDDEN_DOMAINS`)

### Não altera
`app.py`, `graph_connector.py`, `predicate_mapper.py`, `span_validator.py`,
`canonicalizer.py`, `triple_refiner.py`, `extractor.py`, `requirements*`,
`.github/workflows/`, `llm_provider.py`, `src/training/`, Qdrant.

### DoD
`python -m pytest -q` verde (273) · `git diff -- requirements-dev.txt
.github/workflows/` vazio · relatório em `reports/source_productivity_audit_*.json`
com `summary.quality` / `rejection_reasons` / `productive_urls` /
`unproductive_urls` / `truthfulness_note.read_only=true` · manifest anotado.

### Resultado da auditoria (#058, 2026-09-23)
```text
22 URLs avaliadas → productive 8 · weak 4 · unproductive 10
Productive (todas wikipedia): pt/en Santos, pt/en Pelé, pt/en Estádio Urbano
  Caldeira, pt/en Garrincha, pt Botafogo_de_Futebol_e_Regatas
Weak: pt Garrincha, ge.globo botafogo, botafogo.com.br, lance.com.br
Unproductive (exemplos): almanaquedosclubes (404), en Botafogo_F.C. (404),
  santosfc.com.br/institucional/historia (0 triplas), ge.globo santos (0 triplas),
  cbf.com.br (ConnectError), fifa.com (JS shell)
Top rejeições: invalid_predicate 303 · missing_entity 41 · subject_generic 11
total_canonical_triples 78 · total_football_related_hits 25
```

### Leitura
**Nenhuma fonte não-wiki de futebol é produtiva** — as 8 produtivas são
Wikipedia. O dominante `invalid_predicate` (303) confirma o `#045` (vocabulário
de predicados não cobre verbos esportivos). Manifest anotado honestamente; URLs
404/JS não foram forçadas. Próximo: `#045.1` (vocabulário esportivo) ou `#047`
(aliasing — se o `#058` mudar a assinatura de candidatos).

---

## #045.1 — Expand Sport Predicate Vocabulary

**Status:** ✅ concluída (código + testes + auditoria)

### Por quê
O `#058` mediu `invalid_predicate=303` como rejeição dominante. Diagnóstico:
`DEFAULT_PREDICATES` (`foi`, `was`, `processa`, `causa`, `resulta`, …) e verbos
esportivos (`defendeu`, `jogou por`, `venceu`, …) não tinham canônico → lixo.
O guard rodava em fallback regex (spaCy indisponível em CI) e descartava tudo.

### Regras de ouro (aprovadas pelo usuário)
- **lista fechada** — nada de predicados novos vagos (`JOGOU_POR`,
  `DISPUTOU_TITULO` proibidos); 5 novos canônicos: `DEFENDEU`, `VENCEU`,
  `LOCALIZADO_EM`, `DISPUTOU`, `TREINOU` (vocabulário = 23 ≤ 30, únicos);
- equívoco vago → cai em `unmapped_predicate` (quarentena `#044`), **nunca**
  `invalid_predicate` (`#043`);
- normalização prévia (lowercase, sem acentos) antes do lookup;
- golden cross-domain obrigatório (verbos/idiomas distintos → mesmo canônico);
- **não tocar**: quórum, embeddings, LLM, CI/CD, requirements, `app.py`,
  `graph_connector.py`, `extractor.py`, seeds/clusters YAML.

### Arquivos
- `src/cognition/predicate_mapper.py` — `EXTRA_PREDICATES` +5, `EXTRA_MAP`
  (verbos esportivos PT/EN + fix `foi|was→SER`, `processa→EXECUTA`,
  `connects→CONECTA_A`), `KNOWN_VERB_LEMMAS` (flexões crua + esportivos
  sem mapeamento → quarentena)
- `tests/test_predicate_mapper.py` — 6 testes novos (vocabulário limitado,
  verbos PT, verbos EN, guard, golden cross-domain via `refine_triple_ex`,
  quarentena de ambíguos) → 20 no arquivo
- `SPRINT.md`, `docs/03-development-process/TASKS.md` — registro

### Não altera
`extractor.py`, `canonicalizer.py`, `span_validator.py`, `triple_refiner.py`,
`app.py`, `graph_connector.py`, `requirements*`, `.github/workflows/`,
`llm_provider.py`, `src/training/`, Qdrant, seeds YAML.

### DoD
`python -m pytest -q` verde (**279**) · `git diff -- requirements-dev.txt
.github/workflows/` vazio · golden cross-domain: `defendeu` e `jogou por` →
`DEFENDEU` · vocabulário ≤30 únicos · métricas pós-#045.1 (auditoria
read-only em `reports/source_productivity_audit_post045.json`):
- `invalid_predicate`: **303 → 0** (redução 100%, alvo <50%) ✅
- `canonical_triples`: **78 → 128** (↑64%) ✅
- `football_hits`: **25 → 59** (↑136%) ✅
- `quality`: productive 8→9, unproductive 10→9
- restantes dominantes: `missing_entity=55`, `subject_generic=15`
  (gargalo de entity linking → próximo issue)

### Leitura
O vocabulário fechado zerou `invalid_predicate` sem ampliar o espaço de
predicados de forma ambígua. Verbos sem mapeamento claro (`contratou`,
`liderou`, `causa`, `scored`) caem corretamente em quarentena. Próximo ciclo:
re-ingest controlado via worker para medir `verified_facts_domain_independent`
e avaliar o gate de treino; se divergência de entidades persistir → `#047`.

---

## #058.2 — Span quality v2 (H3 fragment rejection)

**Status:** ✅ concluída (código + testes)

### Por quê
Inspeção 2 (`reports/inspection_2_croslingual.json`) provou **Cenário C** no
re-ingest pós-#045.1: `both_domains=0`, `shared_canonical_keys=0/44`,
`cross_candidates=0`. Das 63 linhas de divergência PT↔EN, a classificação
manual corrigiu o auto-rótulo H1→**H3 dominante**: spans são fragmentos
sintáticos (`E O`, `AND`, `ENFIM`, `TO TWO`, `ALTHOUGH GARRINCHA`,
`PELE SAID HE`), não aliases de entidade. `#047` não ataca a causa raiz.

### Regras de ouro
- **lista fechada** de palavras fechadas PT/EN, discurso e relativos — sem
  heurística estatística, sem LLM/embedding;
- regras mais específicas (prep/pronomes/quantificador) **antes** do catch-all
  de palavras fechadas (motivos de rejeição estáveis para a contabilidade);
- whitelist `known_entities` continua sobrescrevendo (inalterado);
- **não tocar**: quórum, `extractor.py`, `canonicalizer.py`,
  `predicate_mapper.py`, `triple_refiner.py`, `app.py`, `graph_connector.py`,
  `requirements*`, `.github/workflows/`, `llm_provider.py`, `src/training/`,
  Qdrant, seeds YAML.

### Arquivos
- `src/cognition/span_validator.py` — v2: `_START_PREP`+EN, `_PRONOUNS`+EN,
  `_FUNCTION_WORDS` (catch-all `E O`), `_DISCOURSE`/`_DISCOURSE_START`
  (`ENFIM`, `PRIMEIRO`), `_RELATIVE_MID_RE` + `_CLAUSE_MARKERS` EN
  (span v2 borderline `REGRA GERAL QUE MAPEIA`)
- `tests/test_span_validator.py` — +6 testes (fragmentos H3 da Inspeção 2,
  starts EN, discurso, relativa interna, entidades legítimas, integração
  `refine_triple_ex`) → 14 no arquivo
- `SPRINT.md`, `docs/03-development-process/TASKS.md` — registro

### DoD
`python -m pytest -q` verde (**285**, base 279) · `git diff -- requirements-dev.txt
.github/workflows/` vazio · motivos novos reutilizam vocabulário existente
(`*_generic_phrase`, `subject_starts_with_stopword`, `*_clause_fragment`,
`object_prepositional_phrase`) · golden da Inspeção 2:
`"e o"→subject_generic_phrase`, `"although Garrincha"→subject_starts_with_stopword`,
`"REGRA GERAL QUE MAPEIA"→object_clause_fragment`.

### Leitura
H3 é agora bloqueado no choke point do refino. `PAULO` truncado
(`São Paulo`) é bug de **boundary do extractor** (fallback regex) — fora do
escopo #058.2; `PELE SAID HE` (cauda verbal) ainda passa se o primeiro token
for entidade real. Re-executar Inspeção 2 após re-ingest para medir queda de
near-misses. **Próximo issue: `#047`** (aliasing bilíngue curado + boundary fix
do extractor) — decidido pelo usuário; re-ingest controlado só **depois**.

---

## Inspeção 2 — artefato de engenharia (chore tools)

**Status:** ✅ versionado · read-only · sem rede no CI

### Por quê
O diagnóstico cross-lingual pós-#045.1 (`both=0`, `shared_keys=0/44`,
63 divergências) precisa ser reproduzível sem recriar lógica ad-hoc. O script
versionado permite auditar novos colapsos, documenta os pares analisados e
serve de base para testes de normalização do `#047`.

### Arquivos
- `scripts/inspect_cross_lingual_divergence.py` — grafo Neo4j (SELECT) +
  re-extração offline + decomposição campo-a-campo + classificador H1–H4
- `tests/test_inspect_cross_lingual_divergence.py` — puros (read-only AST,
  `fact_key`, `classify`, targets, findings doc)
- `docs/INSPECTION_2_FINDINGS.md` — tabela de divergências revisada (H3
  dominante, auto-H1 ingênuo), causas estruturais, decisão `#047`
- `docs/03-development-process/TESTING.md` — índice de teste
- `SPRINT.md` — registro

### DoD
`python -m pytest -q` verde (**292**) · `git diff -- requirements-dev.txt
.github/workflows/` vazio · staging explícito (sem `git add -A`) ·
`reports/*.json` permanece gitignored (evidência local não versionada).

---

## #047 — Aliasing bilíngue curado + boundary fix

**Status:** ✅ concluída (código + testes)

### Por quê
Inspeção 2 provou causa estrutural dupla: (1) fold puro não colapsa
`Santos FC` ↔ `Santos Football Club` (0 shared keys); (2) extractor emite
spans H3 residuais (`PELE SAID HE`, `ALTHOUGH GARRINCHA`, `E O`,
`São Paulo`→`PAULO`). Alias passivo sozinho não resolve H3 — boundary é
obrigatório (findings §Decisão).

### Regras de ouro
- dicionário `entity_aliases.yaml` **curado manualmente** (embedding só sugere);
- aliases carregados **antes** do fold genérico em `canonicalize_entity`;
- conflito foldado → `ValueError` (falha alto, nunca silencioso);
- boundary fix determinístico (conectivo/cauda verbal + resgate `São <Term>` +
  filtro palavra fechada) — sem LLM/embedding;
- **não tocar**: quórum, embedding-promotion, LLM providers, seeds-clusters
  YAML, `requirements*`, `.github/workflows/`.

### Arquivos
- `src/cognition/entity_aliases.yaml` — 6 entradas curadas (Santos FC, Pelé,
  Garrincha, Estádio Urbano Caldeira, Botafogo, São Paulo) com variantes PT/EN
- `src/cognition/canonicalizer.py` — `_load_entity_aliases`, merge em
  `entity_synonyms` + consulta alias-first em `canonicalize_entity`
- `src/cognition/extractor.py` — `strip_boundary_noise`, `rescue_truncated_toponym`,
  `is_function_word_span` nos caminhos spaCy e fallback
- `src/cognition/nlp_extractor.py` — mesmos helpers no fallback regex
- `tests/test_entity_aliasing.py` — 9 testes (colapso, negativos, resíduos,
  golden `fact_hash` cross-lingual, anti-leak YAML)
- `tests/test_boundary_fix.py` — 9 testes (cauda verbal, conectivo, função
  fechada, topônimo, integração extractor)
- `tests/test_extraction_equivalence.py`, `tests/test_predicate_mapper.py`,
  `tests/test_source_productivity_audit.py` — goldens atualizados para o
  canônico curado (#047 reescreve `SANTOS FC`/`PELE`)
- `scripts/inspect_cross_lingual_divergence.py` — `dotenv` opcional (CI lite)
- `SPRINT.md`, `docs/03-development-process/TASKS.md`, `docs/03-development-process/TESTING.md` — registro

### DoD
`python -m pytest -q` verde (**310**, base 292) · `git diff -- requirements-dev.txt
.github/workflows/` vazio · staging explícito · mensagem
`feat(cognition): add curated cross-lingual entity aliasing and fix boundary detection residuals`
· quórum 3 inalterado · sem embedding-promotion · sem LLM · sem seeds ampliadas.

### Leitura
Aliases colapsam pares PT/EN limpos; boundary fix remove caudas verbais e
conectivos antes do refino. Re-ingest controlado **somente depois** destes
testes verdes — aí medir `verified_facts_domain_independent` e decidir gate.

---

## #058.3 — Cross-lingual extraction parity audit (read-only)

**Status:** ✅ concluída (código + testes + relatório)

### Por quê
Re-ingest pós-#047 terminou em **Cenário C** (`duplicate_cross_domain=0`,
`facts_with_two_or_more_domains=0`, `verified_facts_domain_independent=0`).
Faltava evidência de **onde** a cadeia PT/EN diverge antes de virar tripla
canônica partilhada: fetch, extração, refino, alias ou fallback
`demo-memory`. Prioridade declarada: investigar fallback demo-memory primeiro.

### Regras de ouro
- read-only: sem Neo4j/Qdrant write, sem `/api/ingest`, sem reset, sem
  promover fato, sem alterar quórum;
- matriz de causa-raiz fechada (`extraction_absence | predicate_divergence |
  entity_divergence | span_rejection | fallback_contamination |
  true_content_difference`) com hint de próximo issue;
- parser de log tolera mojibake do separador GH (`200 \xd4\xc7\xf6 {...}`);
- self-check AST do script (sem caçar literais de marcador no próprio fonte);
- **não tocar**: `app.py`, `graph_connector.py`, `worker_cycle.py`,
  `predicate_mapper.py`, `span_validator.py`, `canonicalizer.py`,
  `triple_refiner.py`, `entity_aliases.yaml`, seeds, workflows,
  `requirements*`.

### Arquivos
- `src/cognition/extraction_parity_audit.py` — módulo puro (matriz, fold NFKD,
  `parse_worker_ingest_log`, `classify_pair`, `build_parity_report`)
- `scripts/audit_extraction_parity.py` — CLI read-only (`--log/--dry-run/
  --no-graph/--out`), grafo SELECT-only, dry-run offline de extração
- `tests/test_extraction_parity_audit.py` — 15 testes (matriz, log parse,
  read-only AST, helpers)
- `SPRINT.md`, `docs/03-development-process/TASKS.md`, `docs/03-development-process/TESTING.md` — registro

### Resultado (relatório `reports/extraction_parity_pt_en_2026-09-24.json`)
- 6 alvos, 12 fontes; PT e EN ambos com canônicas em **6/6**;
- **0** colisões exatas, **1** near-collision (`near_collision_structural`);
- causa-raiz: `entity_divergence=4`, `predicate_divergence=1`,
  `true_content_difference=1`;
- hints: `#047.1` ×4, `#045.2` ×1 (Pelé), `#055/#048.2/#065` ×1 (Santos);
- **fallback log**: 2/30 `partial_success` + `db_status=demo-memory`
  (`arxiv.org/abs/2303.08774`, `en.wikipedia.org/wiki/Pelé`),
  `entities_processed=0`, `fallback_written_to_graph=false` →
  `masked_extraction_failure=2`, prioridade **`high_#058.4`**
  (não `#063`: nada foi gravado no grafo).

### DoD
`python -m pytest -q` verde (**325**, base 310) ·
`git diff -- requirements-dev.txt .github/workflows/` vazio · staging explícito
· mensagem `feat(observability): add cross-lingual extraction parity audit` ·
relatório gerado · quórum 3 · sem treino · sem seeds alteradas.

### Leitura / próximo issue
Evidência apoia **`#058.4`** (extração EN mascarada por demo-memory) como
prioridade de fallback; paralelamente **`#047.1`** (entity divergence em 4
alvos) e **`#045.2`** (predicate divergence Pelé). Registrar dívida
**`#064`** (concept reconciliation) sem executar. **Não treinar** até
`verified_facts_domain_independent ≥ 10` + records ≥ 50.

## #058.4 — Fallback transparency (status honesto + métricas)

**Status:** ✅ concluída (código + testes + docs)

### Por quê
Parity audit (#058.3) mostrou 2/30 ingestões com `partial_success` +
`db_status=demo-memory` + `entities_processed=0` — falha de extração mascarada
como sucesso parcial. Invariante: fallback nunca grava `:Fato`/vetor/quórum e
nunca reporta `partial_success` com 0 entidades.

### Escopo
- `app.py`: status `degraded` (flag on) / `failed` (default) para demo+entities=0;
  nunca `partial_success` nesse caso; flag `NEXUS_ALLOW_DEMO_FALLBACK` default
  `false`; métricas `fallback_health` + `extraction_quality.fallback_events/
  masked_extraction_failures`; resposta expõe `masked_extraction_failure` e
  `allow_demo_fallback`; vetor/episódio só gravam se `success`.
- `extraction_parity_audit.py`: parser reconhece `degraded`/`failed` e
  `masked_extraction_failure` no corpo da resposta.
- `worker_cycle.py`: warning log em status `degraded`/`failed`.
- `tests/test_fallback_transparency.py`: 6 casos (status, invariantes de
  escrita, flag, métricas, anti-leak, caminho saudável).
- Docs: `ANALYTICS.md`, `API.md`, `TESTING.md`, `ERROR_HANDLING.md`,
  `ARCHITECTURE.md`, `TASKS.md`.

### DoD
`python -m pytest -q` verde · `git diff -- requirements-dev.txt
.github/workflows/` vazio · staging explícito · mensagem
`fix(observability): surface demo-memory fallback as masked extraction failure`
· quórum 3 · sem treino · sem seeds alteradas · sem `git add -A`.

## #047.1 — Expand curated entity aliases (evidência parity #058.3)

**Status:** ✅ concluída (código + testes + docs)

### Por quê
Parity audit (#058.3) mostrou `entity_divergence=4/6` alvos (Garrincha,
Estádio Urbano Caldeira/Vila Belmiro, Botafogo, São Paulo). Aliasing
curado, determinístico e baseado em evidência — nunca intuição nem
embedding promotor.

### Escopo
- `src/cognition/entity_aliases.yaml`: bloco `evidence` (sem schemes
  http/https — anti-leak) em toda entrada; variante simples `Botafogo`;
  entrada nova clube `SÃO PAULO FUTEBOL CLUBE` (cidade `SAO PAULO`
  separada); variantes EN de Garrincha/Vila Belmiro confirmadas.
- `src/cognition/canonicalizer.py`: sem mudança de código (loader já
  ignora chaves extras como `evidence`).
- `tests/test_entity_aliasing.py`: evidence obrigatório; positivos dos
  4 alvos; negativos (Flamengo≠Fluminense, Botafogo≠Vasco,
  SPFC≠Palmeiras, Pelé≠Garrincha, Estádio≠Maracanã, cidade≠clube);
  goldens cross-lingual de subject/object por alvo.
- Docs: `SPRINT.md`, `TASKS.md`.

### Fora de escopo
`predicate_mapper.py` (#045.2) · `span_validator.py` · `app.py` ·
`graph_connector.py` · `worker_cycle.py` · `config/seed_clusters.yaml` ·
`requirements-dev.txt` · `.github/workflows/` · quórum 3 · sem treino ·
sem ampliar seeds · sem abrir #064.

### DoD
`python -m pytest tests/test_entity_aliasing.py -q` verde ·
`python -m pytest -q` verde global · `git diff -- requirements-dev.txt
.github/workflows/` vazio · seeds intactas · staging explícito ·
mensagem `feat(cognition): expand curated entity aliases for Garrincha, Estadio, Botafogo, Sao Paulo based on parity evidence`.

### Leitura / próximo issue
CI verde → **`#045.2`** (predicate divergence Pelé: `defendeu`/`played
for`) → deploy único no Space → re-ingest controlado único → rerun
parity + cross-source → classificar cenário (A–E). **Não treinar.**

## #045.2 — Expand predicate mapper (divergência Pelé, evidência #058.3)

**Status:** ✅ concluída (código + testes + docs)

### Por quê
Parity audit (#058.3) classificou alvo Pelé como `predicate_divergence`
(`shared_predicates=[]` com `shared_entities` já canônicos pós-#047).
`played for`/`defendeu` já colapsavam (#045.1); faltava a forma-base
`play for` e o golden `fact_hash` PT/EN completo do caso residual.

### Escopo
- `predicate_mapper.py`: `play for` → `DEFENDEU` (única entrada nova;
  vocabulário controlado inalterado — sem predicado novo).
- `tests/test_predicate_mapper.py`: golden
  `test_pele_cross_lingual_full_collision_fact_hash` (Pelé + Santos
  FC/Santos Football Club → mesmo `fact_hash`); positivo `play for`;
  negativos de modal/ambíguo reafirmados.
- Fora de escopo: `represented` → `DEFENDEU` **não** adicionado (conflito
  com `representa`→`SER` e sem evidência direta no relatório Pelé);
  modais/ambíguos permanecem rejeitados; quórum 3; sem treino; seeds
  intocadas; `entity_aliases.yaml` fechado no #047.1.

### DoD
`python -m pytest tests/test_predicate_mapper.py -q` verde ·
`python -m pytest -q` verde · `git diff -- requirements-dev.txt
.github/workflows/` vazio · staging explícito · mensagem
`feat(cognition): expand predicate mapper for evidenced cross-lingual sport verbs`.

### Leitura / próximo issue
Deploy único no Space → re-ingest controlado único → rerun parity +
cross-source → classificar cenário A–E. **Não treinar. Não ampliar
seeds. Não abrir #064.**

---

## Tríade pós-#058.4 — re-ingest controlado + rerun parity + classificação

**Status:** ✅ executada (deploy único + 1 re-ingest + audits read-only)

### Execução
- Baseline: `reports/baseline_pre_triade_058.json` — 124 fatos,
  `verified_facts_domain_independent=0`, `duplicate_cross_domain=0`.
- Backup: `reports/aura_snapshot_pre_triade_058.json`.
- Reset: `scripts/reset_fatos_047.py --confirm` — Fatos 124→0;
  Conceito/FonteWeb/Episódio preservados.
- Deploy Space (após `b2db8ee` + `48c9e2a`); `/health` 200;
  `fallback_health` + `allow_demo_fallback=false` (#058.4).
- Worker local: 40 URLs mineradas, 32 fontes ingeridas;
  `status=failed` + `masked_extraction_failure=true` em extrações
  vazias (arxiv, nist, ge.globo) — nunca `partial_success`.
- Pós-re-ingest: **266 fatos** (124→266), Conceito 1674, Episódio 1553,
  FonteWeb 35; `facts_with_two_or_more_domains=0`;
  `verified_facts_domain_independent=0`; `duplicate_cross_domain=0`;
  `facts_with_two_or_more_confirmations=3` (mesmo domínio).
- Cross-source: `exact_cross_source_matches=0`; `true_unique=266`;
  near_matches 0/0/0.

### Rerun parity (parâmetros corretos)
Primeiro artefato `extraction_parity_triade_058.json` usou defaults
stale (`build_space_commit=5eb6931`, log antigo, sem `--dry-run`) —
descartado. Rerun oficial:

```text
python scripts/audit_extraction_parity.py \
  --log reports/worker_cycle_triade_058.log \
  --worker-run-id triade-058 --build-space-commit 48c9e2a --dry-run \
  --out reports/extraction_parity_triade_058_rerun.json
```

| Métrica | Baseline #058.3 | Pós-tríade |
|---|---|---|
| causa `entity_divergence` | 4 | **6** |
| causa `predicate_divergence` | 1 | **0** |
| causa `true_content_difference` | 1 | **0** |
| near_collision | 1 | **4** |
| exact collision | 0 | 0 |
| fallback_used_targets | 1 | **0** |
| hints | #047.1×4, #045.2×1, #055…×1 | **#047.1×6** |

Por alvo: Pelé `predicate_divergence→near_collision_structural`
(#045.2 fechou); Garrincha/Estádio/São Paulo →
`near_collision_structural`; Santos `no_shared_surface→
entity_divergence` (predicados partilhados); Botafogo permanece
`entity_divergence` (EN `raw=1` — extração EN quase vazia).

### Classificação de cenário: **B**

- **A** (aliases resolveram): **não** — 0 colisões exatas,
  0 fatos multi-domínio.
- **B** (`entity_divergence` restante → `#047.2`): **SIM — cenário
  dominante** (6/6 alvos, hint `#047.1`).
- **C** (`predicate_divergence` → `#045.3`): **fechado** pelo #045.2
  (1→0).
- **D** (`true_content_difference` → `#055/#048.2/#065`): **saiu do
  mapa** no rerun (Santos agora `entity_divergence`); dívida de
  conteúdo permanece em backlog, sem hint ativo.
- **E** (`masked>0` → #058.4): **fechado** — worker reporta
  `failed`+`masked=true` (nunca `partial_success`); sem contaminação
  no grafo (`fallback_written_to_graph=false`).

### Gate de treino
`verified_facts_domain_independent=0` +
`facts_with_two_or_more_domains=0` → **permanece fechado**.
**Não treinar. Não ampliar seeds. Não abrir #064.**

### DoD
Parity rerun gerado · cross-source gerado · pós-re-ingest gerado ·
341 testes verdes · `git diff -- requirements-dev.txt
.github/workflows/` vazio · seeds intactas · staging explícito ·
relatórios em `reports/` (gitignored).

### Leitura / próximo issue (decisão do usuário)
Cenário **B** com resíduo estrutural: aliases #047.1 melhoram
`near_collision` (1→4) mas **não** produzem `fact_hash` cruzado —
sujeitos canônicos são em sua maioria frases genéricas
(`CLUBE`, `TIME SANTISTA`, `STRIKER`), não o nome da entidade.
Botafogo EN com `raw_triples=1` sugere extração EN quase vazia.
Decisão do usuário: **`#058.5`** (forense de extração EN Botafogo),
não `#047.2` nem entity linking nem esperar mais workers.
**Não treinar até ≥10 verified + records ≥50.**

---

## #058.5 — Botafogo EN extraction forensics and targeted repair

**Status:** ✅ concluída (forense read-only; causa raiz identificada)

### Por quê
Parity #058.3 + rerun pós-tríade mostraram Botafogo EN com
`raw_triples=1` / `entity_divergence` — mas aliases sozinhos não geram
`fact_hash` cruzado se a fonte EN não extrai triplas estruturalmente
comparáveis. A pergunta correta não é "quais aliases faltam?" e sim
"por que a página EN quase não produz triplas brutas válidas?".

### Escopo (forense read-only)
- `src/cognition/extraction_forensics.py`: módulo puro (sem rede/grafo/LLM);
  `classify_diagnosis` mapeia contadores → etapa culpada em
  `fetch | cleaning | sentence_selection | extraction | span_validation |
  predicate_mapping | entity_aliasing | persistence | unknown`;
  `looks_like_wikipedia_404`; `evaluate_hypotheses` (H1–H7);
  `build_comparison` / `build_forensics_report`.
- `scripts/audit_botafogo_en_extraction.py`: CLI read-only (AST guard);
  fetch PT + EN seed + sonda de candidatas EN; limpador WebMiner +
  `_strip_html`; extração offline; grava
  `reports/botafogo_en_extraction_forensics_YYYY-MM-DD.json`.
- `tests/test_extraction_forensics.py`: 23 testes puros (diagnóstico por
  estágio, 404, H1–H7, comparação, script read-only, módulo sem
  httpx/neo4j).
- **Não** altera: seeds, workflows, `requirements-dev.txt`, runtime,
  `entity_aliases.yaml`, `predicate_mapper.py`, `span_validator.py`.

### Evidência (relatório gerado)
- Seed EN `https://en.wikipedia.org/wiki/Botafogo_F.C._%28Rio_de_Janeiro%29`
  → **HTTP 404**; corpo da página de erro contém
  `"If the page has been deleted..."`.
- Extractor minera a página 404 → `raw_triples=1` =
  `If the page / POSSUIR / been deleted` (lixo).
- PT saudável: HTTP 200, `raw=25`, `canonical=13`.
- Candidatas EN (HTTP 200, ~640KB):
  `https://en.wikipedia.org/wiki/Botafogo_FR`,
  `https://en.wikipedia.org/wiki/Botafogo_de_Futebol_e_Regatas`.

### Classificação de causa raiz
| Campo | Valor |
|---|---|
| `primary_diagnosis` | **`fetch`** |
| `next_issue_hint` | **`#048.3`** (replace unproductive EN URL) |
| H1 (URL improdutiva/404) | **supported** |
| H2–H7 | not supported |
| `is_unknown` | false (issue concluído) |
| `collision_status` | `en_fetch_failed` |

### DoD
`python -m pytest -q` verde (364) · `git diff -- requirements-dev.txt
.github/workflows/ config/seed_clusters.yaml` vazio · staging explícito ·
mensagem `feat(observability): add Botafogo EN extraction forensics audit` ·
relatório gerado e exit 0 · quórum 3 · sem treino · sem seeds alteradas ·
sem `git add -A`.

### Leitura / próximo issue
Causa raiz: **seed EN 404** → issue seguinte **`#048.3`** (trocar URL EN
do cluster Botafogo por `Botafogo_FR` ou `Botafogo_de_Futebol_e_Regatas`).
H2–H7 só relevantes **depois** do fix de URL + novo re-ingest/parity.
**Não treinar. Não ampliar seeds. Não abrir #064.**

### Fora de escopo
`config/seed_clusters.yaml` (fix de URL é `#048.3` separado),
`entity_aliases.yaml`, `predicate_mapper.py`, `span_validator.py`,
`src/training/`, workflows, `requirements-dev.txt`.

### Correção de escopo — #058.5 / #048.3
O forense #058.5 identificou HTTP 404 na URL EN do Botafogo, mas essa URL
estava apenas nos alvos default dos scripts de auditoria, não em
`config/seed_clusters.yaml`. Portanto, a causa não afetava o worker de
produção.
Ações:
- `#048.3` passa a significar: corrigir alvos de auditoria.
- `#048.4` é criado para adicionar URL EN Botafogo produtiva ao cluster.
- O diagnóstico de `fetch` permanece válido para os scripts, mas não deve
  ser lido como causa raiz de `duplicate_cross_domain = 0` em produção.

## #048.3 — Replace stale Botafogo EN 404 audit target

**Status:** ✅ concluída (escopo corrigido: scripts de auditoria, não seeds)

### Por quê
A URL `https://en.wikipedia.org/wiki/Botafogo_F.C._%28Rio_de_Janeiro%29`
(HTTP 404, detectada no #058.5) vivia nos `DEFAULT_TARGETS`/`TARGETS` de
3 scripts de auditoria — contaminava diagnósticos futuros de paridade e
divergência cross-lingual. Não estava no manifest de seeds.

### Escopo
- `scripts/audit_extraction_parity.py`: alvo EN botafogo →
  `https://en.wikipedia.org/wiki/Botafogo_de_Futebol_e_Regatas`.
- `scripts/inspect_cross_lingual_divergence.py`: idem.
- `scripts/audit_botafogo_en_extraction.py`: idem; `en_candidates`
  reduzido a `Botafogo_FR` (a canônica já é o alvo).
- Não tocar: `config/seed_clusters.yaml`, `worker_cycle.py`, `app.py`,
  workflows, `requirements-dev.txt`.

### Evidência (validação offline, empate técnico)
| URL | HTTP | raw | canonical |
|---|---|---|---|
| antiga (`Botafogo_F.C._%28…`) | **404** | 1 | 1 |
| `Botafogo_FR` | 200 | 15 | 10 |
| **`Botafogo_de_Futebol_e_Regatas`** (escolhida) | 200 | 15 | 10 |

Escolha pela canônica (nome completo coincide com o canonical esperado;
menos ambiguidade; casa com `entity_aliases.yaml`).

### DoD
`python -m pytest -q` verde (364) · `git diff -- requirements-dev.txt
.github/workflows/` vazio · URL 404 ausente de `DEFAULT_TARGETS`/`TARGETS`
em `scripts/` · staging explícito · mensagem
`fix(audit): replace stale Botafogo EN 404 target with productive canonical URL` ·
quórum 3 · sem treino · sem seeds alteradas · sem `git add -A`.

### Fora de escopo
`config/seed_clusters.yaml` (adição de fonte EN é `#048.4`),
`app.py`, `graph_connector.py`, `worker_cycle.py`, `requirements-dev.txt`,
workflows.

## #048.4 — Add productive EN Botafogo source to cluster

**Status:** ✅ concluída (corpus; 1 item = 1 commit)

### Por quê
O cluster `garrincha_botafogo` não tinha página EN dedicada ao Botafogo —
sem ela, o pipeline não extrai fatos EN do Botafogo para colapsar com os
fatos PT, e o aliasing do #047 fica subutilizado. #048.3 corrigiu os
alvos de auditoria; este issue completa a cobertura de fonte no manifest.

### Escopo
- `config/seed_clusters.yaml`: nova fonte em `garrincha_botafogo` —
  `https://en.wikipedia.org/wiki/Botafogo_de_Futebol_e_Regatas`
  (domain `en.wikipedia.org`, publisher `Wikimedia`, `productive`).
- `tests/test_seed_clusters.py`: 2 testes novos — fonte EN canônica
  presente + ausência da URL 404 histórica no manifesto.
- Não tocar: scripts de auditoria (#048.3), `worker_cycle.py`, `app.py`,
  workflows, `requirements-dev.txt`.

### Evidência (validação offline #048.3/#058.5)
HTTP 200 · `cleaned=41234` · `sentences=325/172` · `raw_triples=15` ·
`canonical_triples=10` · não-404.

### Estado do cluster após #048.4
```text
domínios: pt.wikipedia.org, en.wikipedia.org, botafogo.com.br (3 ✓)
publishers: Wikimedia, Botafogo (2 ✓, 1 fora de wiki ✓)
URLs: 5, únicas, todas HTTPS
```
Domínio EN já existia (Garrincha EN) → **não é domínio novo**, é mais
uma fonte no mesmo domínio. `en.wikipedia.org` não conta como terceiro
domínio independente.

### DoD
`python -m pytest -q` verde (366) · `git diff -- requirements-dev.txt
.github/workflows/` vazio · manifesto contém a URL EN no cluster ·
validator sem erros · staging explícito · mensagem
`feat(seeds): add productive EN Botafogo source to garrincha_botafogo cluster` ·
quórum 3 · sem treino · sem `git add -A`.

### Fora de escopo
Scripts de auditoria (já fechados em #048.3), `worker_cycle.py`,
`app.py`, `entity_aliases.yaml`, `predicate_mapper.py`, workflows,
`requirements-dev.txt`.

### Expectativa (pós-re-ingest único)
Sucesso mínimo: `duplicate_cross_domain > 0` (PT/EN Botafogo colapsam).
`verified_facts_domain_independent` provavelmente continua 0 (falta
terceira fonte não-wiki produtiva — `botafogo.com.br` é `weak`).
**Gate de treino continua fechado. Não treinar.**

## #058.8 — Merge do regex fallback quando o spaCy retorna sparse

**Status:** ✅ concluída (fix worker-only; validado em run único)

### Por quê
Re-ingest pós-#048.4 mostrou `duplicate_cross_domain = 0`. A causa raiz
mecânica reconcilia todas as medições anteriores:

```text
offline (sem spaCy)        → regex puro      → EN raw 13–25
worker (spaCy PT sobre EN) → 1–7 triplas lixo → fallback nunca dispara → EN raw 1
```

`extract()` só acionava o fallback quando o spaCy devolvia **0** triplas.
Com o modelo `pt_core_news_sm` sobre texto EN, o spaCy devolvia 1–7
triplas inválidas → o regex nunca rodava → o lado EN não produzia
matéria-prima para colapsar. Explica o `entities=0` do EN Pelé (#058.3),
o `raw=1` do #058.5 e a divergência sistemática worker-vs-offline.

### Escopo (1 item = 1 commit)
- `src/cognition/extractor.py`: constante `SPACY_SPARSE_MIN = 10`;
  `extract()` ganha banda sparse — se `len(spacy) < 10` e fallback
  habilitado, calcula o regex **lazy** e faz merge **fallback-primeiro**,
  depois só-spaCy, dedupe com `casefold` nos 3 campos, cap em
  `max_triples`. Caminho denso (`>= 10`) e banda 0 (`== 0`) retornam
  **verbatim** (bit-a-bit idênticos ao anterior; regex não é invocado
  no denso — comprovado por spy).
- `tests/test_sparse_fallback_merge.py`: 10 testes — sparse(1) mescla,
  denso(25) sem invocar fallback (spy), fronteira 9 dispara / 10 não
  dispara (`<` congelado), banda 0 verbatim, fallback desabilitado,
  dedupe casefold nos 3 campos, cap preserva ordem fallback-first,
  constante == 10, caminho real sem spaCy inalterado.
- Não tocar: `app.py`, `graph_connector.py`, `canonicalizer.py`,
  `predicate_mapper.py`, `span_validator.py`, `triple_refiner.py`,
  seeds, aliases, workflows, `requirements*.txt`.

### Evidência (run `36064311931`, gate EN + gate PT)
| Fonte | antes | depois |
|---|---|---|
| EN Pelé | 1 | **25** (canon 12) |
| EN Garrincha | 1 | **21** (canon 13) |
| EN Botafogo | 1 | **14** (canon 9) |
| EN Santos | 7 | **11** (canon 11) |
| EN AI / ML | 6 / 8 | **25 / 25** |
| PT wiki (12 páginas) | 12–25 | **idênticos ao baseline** |

Grafo: `Fato` 119 → **248** (EN 108), `canonical_to_fact_gap` 7 → **0**,
21 pares candidatos PT/EN (antes 0) — sujeitos já colapsam
(`manuel francisco dos santos` PT+EN), divergência restante =
predicado/objeto. 1 masked (arxiv, `raw=1` genuíno). LLM 0/32.

### Árvore de decisão pós-run
```text
raw EN recuperou ✅  AND  collision = 0  →  PRÓXIMO = #047.1 (aliasing)
                                            com exemplos EN reais
                                            (NÃO #045.3, NÃO treino)
```

### DoD
`python -m pytest -q` verde (**376**, +10) · `git diff -- requirements-dev.txt
.github/workflows/ config/seed_clusters.yaml` vazio · staging explícito ·
mensagem `fix(cognition): merge regex fallback when spaCy extraction is sparse` ·
CI verde · run único `36064311931` (enable→dispatch→log→disable, cron
`disabled_manually`, nenhum run agendado escapou) · gates EN ≥ 10 e PT
inalterado · quórum 3 · sem treino · sem `git add -A`.

### Nota de design (dívida de calibração, P2)
`SPACY_SPARSE_MIN = 10` é empírico (wiki PT ≥ 12, EN problemático ≤ 7).
Se fragilizar, alternativa principiadista: limiar relativo
`len(spacy) < f(sentenças_candidatas)` em vez de constante absoluta.

### Fora de escopo
`#047.1` (próximo issue, com evidência EN real), `#045.2`/`#045.3`,
`entity_aliases.yaml`, `predicate_mapper.py`, `config/seed_clusters.yaml`,
workflows, `requirements*.txt`, treino (gate ainda fechado:
`verified_facts_domain_independent = 0 < 10`).

## #058.9 — Triagem read-only dos 21 pares PT/EN

**Status:** ✅ concluída (decisão: descartar `#047.1` e `#045.3`; caminho 2 = `#058.10`)

### Evidência (`reports/triage_058_9.json`, script só em temp dir)
- `total_pairs = 21`; high = 0, medium = 0, low = 21;
  `mismatch_field: multiple = 21`.
- `root_cause`: `true_content_difference = 13`, `extraction_noise = 8`;
  `predicate_mapper_gap = 0`; `object_alias_missing = 0`.
- Decisão: `fix_object_alias_only = 0`, `fix_predicate_mapper_only = 0`,
  `fix_both = 21` → **nenhum dos dois gaps é a causa**.
- `potential_verified` (def grafo, confs ≥ 3 & doms ≥ 2) = 2;
  (def audit, doms ≥ 3) = 0.
- Pares = cross-produto de **3 sujeitos** (`ssim = 1.0`): manuel francisco
  santos 12, santos futebol clube 8, edson arantes nascimento 1.
- EN: `SER` em 21/21 pares e **94/108 fatos EN (87%)** (monocultura
  copular); PT: POSSUIR/DEFENDEU/EXECUTA/DISPUTOU/VENCEU;
  `pt.wikipedia` ≈ 0 fatos SER. Problema SER+cláusula aparece também fora
  wiki EN (scikit-learn, plato, ibm, ollama, tensorflow, nist, huggingface,
  santosfc.com.br) → guarda é linguístico, agnóstico de domínio.

### Decisão do usuário
Descartar `#047.1` (alias) e `#045.3` (mapper) como próximos passos; abrir
**`#058.10`** com guarda sintática determinística no `span_validator`
(reason `object_predicate_complement`) quando o predicado é `SER`.

## #058.10 — Guard `object_predicate_complement` (objeto de SER = cláusula EN)

**Status:** ✅ concluída + **Fase B validada em produção** (run `36090364284`;
classificação do operador: **Cenário 2 parcial** + Regra de Ouro da Contabilidade)

### Por quê
A triagem `#058.9` mostrou que os 21 pares PT/EN não têm gap de alias nem
de mapper — o lado EN extrai **cláusulas como objeto** de predicados
copulares (`SANTOS FUTEBOL CLUBE —SER→ ELIMINATED BY PENAROL`). Como
`SER` é 87% dos fatos EN, isso infla o ruído e fecha o gate de pares.
O choke point é o `span_validator` (call-site do `refine_triple_ex`).

### Escopo (1 item = 1 commit)
- `src/cognition/span_validator.py`: parâmetro opcional `predicate` em
  `reject_reason_for_span`/`validate_entity_span`; razão única
  `object_predicate_complement`. Guard roda **só** se `role == "object"`,
  `fold_span(predicate) ∈ copulas` (`ser foi era eram sao estao is are was
  were be been being`) e **depois** da whitelist `known_entities`.
  Cinco camadas sobre tokens fold-ados (case-insensitive; sem depender de
  capitalização):
  1. agente passivo: primeiro token termina `ed`/`en` + token `by`;
  2. abertura predicativa/auxiliar `_SER_CLAUSE_STARTS` (known/born/based/
     located/called/ranked/... + auxiliares `was/are/...`);
  3. comparativo: marcador (`older/less/different/...`) + `than`;
  4. advérbio de grau `_DEGREE_STARTS` (`so/very/too/quite/...`);
  5. densidade de palavras fechadas ≥ 0.5.
  `predicate = None` → guard inativo (API v2 intacta).
- `src/cognition/triple_refiner.py`: **1 linha** —
  `validate_entity_span(raw_object, "object", known, predicate=predicate)`
  (canônico pós-`validate_predicate`).
- `tests/test_span_validator.py`: +4 testes — 14 BAD × `SER` →
  `(False, "object_predicate_complement")`; 22 GOOD × `SER` → `(True, None)`;
  escopo de predicado (`DISPUTOU` aceita, `None` inativo, subject não afetado);
  integração `refine_triple_ex` (rejeição + dois aceites `ok`).
- Não tocar: `predicate_mapper.py`, `canonicalizer.py`, aliases, seeds,
  workflows, `requirements*.txt`.

### Evidência (dry-run read-only `reports/guard_dry_run_058_10.json`, grafo atual = 248 fatos)
| Métrica | valor |
|---|---|
| fatos com predicado copular (`SER` etc.) | 141/248 (57%) |
| objetos rejeitados (`object_predicate_complement`) | **45** (32% dos SER) |
| objetos SER aceitos | 96 |
| domínios das rejeições | en.wikipedia 39, plato 2, ibm 2, ollama 1, scikit-learn 1 |
| rejeições em domínios PT | **0** (PT estável por construção — guard é EN) |
| rejeições com predicado não-copular | **0** (guard escopado a `SER`) |
| lado EN dos 19 pares `SER` da triagem `#058.9` | **16/19** rejeitados |

Exemplos reais rejeitados: `ELIMINATED BY PENAROL`, `KNOWN FOR HIS
DRIBBLING`, `SEVEN YEARS OLDER THAN PELE`, `SO IMPRESSED WITH THE YOUNG
GARRINCHA`, `BORN IN PAU GRANDE`, `COINED IN 1959 BY ARTHUR SAMUEL`,
`INAUGURATED ON 12 OCTOBER 1916`. Nenhum dos 22 GOOD (Santos, Botafogo,
Pelé, Garrincha, Vila Belmiro, Campeonato..., IA/ML) foi rejeitado.

Residual (falsos-negativos aceitos, começando conservador):
`INCREDIBLE PLAYER` ×3 pares (sem camada de capitalização — a caixa do span
bruto é ambígua entre all-caps e lowercase; decisão: não depender dela);
2 pares `VENCEU` (não-copular, fora de escopo por design do guard em `SER`).

### DoD
`python -m pytest -q` verde (**380**, +4) · `git diff -- requirements-dev.txt
.github/workflows/ config/seed_clusters.yaml config/entity_aliases.yaml
src/cognition/predicate_mapper.py src/cognition/canonicalizer.py` vazio ·
staging explícito (5 arquivos) · mensagem
`feat(cognition): suppress EN copular and passive clause objects in span validator` ·
CI verde · sem treino · sem LLM/embedding no validador · sem `git add -A`.

### Fase B — validação em produção (2026-09-25, com o operador)

Execução sob as 8 condições rígidas do operador: snapshot lógico aceito como
`snapshot_aura_ok` (3543 nós / 3248 rels) → reset escopado só `:Fato`
(248→0; Conceito 1694 e FonteWeb 36 intactos) → Space `85355c6 (git 134869b)`
com o guard → warm-up 15+2 → baseline `reports/baseline_pre_reingest_058_10.json`
(248 fatos) → worker único `36090364284` (success) → cron `disabled_manually`
antes e depois (sem runs redundantes) → 4 auditorias read-only. Qdrant,
seeds, aliases, mapper intactos; sem treino.

| Métrica (baseline → pós) | valor |
|---|---|
| `object_predicate_complement` em produção | 0 → **43** |
| padrões banidos da triagem nos fatos persistidos | 16 → **0** |
| fatos `:Fato` | 248 → 183 |
| EN facts / SER share EN | 104 / 85,58% → 59 / **81,36%** |
| PT facts / `ser_pt` | 72 / 0 → 67 / 0 |
| `duplicate_cross_domain` / `verified` | 0 / 0 → 0 / 0 (esperado pela calibração) |
| contabilidade | raw 574, canônicas 196, distintas 190, grafo 183, `reconciled_gap=7`, `unaccounted=0` |

**Gate PT (não vazou):** 72→67 é integralmente a URL `pt.wikipedia.org/wiki/
Inteligência_artificial` (falha de pool Neo4j no 1º ingest — cold-start,
8 entities perdidas); as outras 11 URLs PT tiveram yield idêntico ao baseline;
`ser_pt=0` antes e depois (guard só dispara em cópulas), dry-run 0 PT,
predicados PT todos verbais → restringir guard a EN **não** é necessário.
`gap=7` = as mesmas 7 chaves da pt-IA; `unaccounted=0`; recuperação
planejada no próximo ciclo de re-ingest natural (sem dispatch isolado —
decisão do operador; anotado no relatório).

**Classificação do operador: Cenário 2 (parcial) + Regra de Ouro da
Contabilidade.** Guard validado — os padrões tóxicos sumiram dos fatos sem
matar entidades válidas. Collision zero devido a **divergência editorial
real** (`true_content_difference`/`extraction_absence` no parity audit
pós-guard), não técnica; `#047.1`/`#045.3` permanecem mortos. Próximo passo
exige **mudança de estratégia de corpus/fonte**: `#055` (API REST do
Almanaque — confirmada: OpenAPI 3.0.3, 87 paths, leituras públicas em
`/api/v1`; ToS: API é recurso do plano Elite com chave individual e extração
em escala proibida → decisão/licença do operador) ou `#048.5` (curadoria
manual de fatos-alvo). Gate de treino fechado (`verified=0 < 10`).

Artefatos: `reports/{baseline_pre_reingest,post_reingest}_058_10.json`,
`reports/{extraction_parity,entity_linking_audit,cross_source_audit}_058_10_post.json`
(4 auditorias), `reports/aura_snapshot_pre_reingest_058_10.json` (rollback,
local), run `36090364284`.

### Fora de escopo
Fase B (re-ingest pós-guard: snapshot AuraDB → reset escopado → worker
único → re-runs read-only — executada **com o usuário** em 2026-09-25,
ver seção acima),
`#047.1`, `#045.3`, `#048.5`, `#055`, seeds, aliases, `predicate_mapper.py`,
workflows, treino (gate `verified_facts_domain_independent = 0 < 10`).



## #048.5 — Curated target-fact clusters without Almanaque API

**Status:** 🚧 **bloqueada por #058.11** — mecanismo entregue,
hipótese de fonte refutada, gargalo real identificado em extração
target-aware.

### Registro exigido (decisão do operador)

```text
#048.5 não falhou por falta de fontes, mas por gap de extração:
sentenças-alvo existem, triplas-alvo não nascem.
Próximo issue técnico: #058.11.
Troca de fato-alvo permitida apenas como varredura read-only.
```

### Resultado da auditoria offline (read-only)

3 clusters curados auditados com `scripts/audit_cluster_productivity.py`
(fetch paridade-prod + `target_fact_hits` com Jev ≥ 0.7) →
`reports/cluster_productivity_048_5.json`:

| Cluster | URLs aceitas | domínios aceitos | veredito |
|---|---|---|---|
| botafogo_libertadores_2024 | 0/7 | 0 | inelegível |
| botafogo_brasileirao_2024 | 1/7 (UOL, Jev 0.76) | 1 | inelegível |
| pele_santos_carreira | 0/6 | 0 | inelegível |

Elegibilidade exigia ≥ 3 domínios aceitos, ≥ 2 publishers, ≥ 1 não-Wiki.

### Causa raiz em 3 camadas

1. **Fetch**: corpo JS-only (`botafogo.com.br`, `agazeta`, `folhape`,
   `poder360` → 0 ocorrências do sujeito no HTML servido); ESPN
   202-challenge; Reuters 401.
2. **Extração (gargalo dominante)**: 15 URLs com
   `target_fact_sentences > 0` e **0 triplas cruas/canônicas** contendo
   o fato-alvo (teto `max_triples=25` + viés posicional + rejeições do
   refino). Jev máximo das triplas: 0.01–0.11; único hit: UOL
   `BOTAFOGO DE FUTEBOL E REGATAS --SER--> CAMPEAO BRASILEIRO` (0.76).
3. **Tabelas (RSSSF)**: sem narrativa → `canonical_triples = 0`.

`subject_alias_missing = 0`, `object_alias_missing = 0`,
`predicate_mapper_gap = 0` nos pares analisados → **não** é #047.2 nem
#045.3 (atacariam sintoma downstream; a tripla bruta jamais nasce).

### Decisão do operador (árvore corrigida)

- **B** → evidência para **#058.11** (target-aware extraction gap),
  não #045.3/#047.2.
- **A** → varredura read-only de fatos-alvo alternativos →
  `reports/target_fact_sweep_048_5a.json` com critério novo
  `target_fact_triples_canonical >= 1` por domínio (≥ 3 domínios,
  ≥ 2 publishers, ≤ 1 domínio só-`SER`, sem objeto date-like).
- `config/seed_clusters.yaml` **só** pode mudar com 3 clusters
  elegíveis; sem isso, expandir seeds é proibido e o próximo issue é
  #058.11.

### Fora de escopo
`app.py`, `graph_connector.py`, `predicate_mapper.py`,
`canonicalizer.py`, `span_validator.py`, `triple_refiner.py`,
`extractor.py`, `requirements-dev.txt`, workflows,
`config/seed_clusters.yaml` (enquanto `clusters_eligible < 3`),
API Almanaque (#055 congelado por compliance), treino (gate
`verified_facts_domain_independent = 0 < 10`).

### Próximo issue
**#058.11 — Target-aware extraction gap analysis**: read-only/diagnóstico
primeiro (por que sentença-alvo não vira tripla-alvo; classes de causa:
`sentence_score_below_threshold`, `max_triples_truncation`,
`missing_subject_entity`, `missing_object_entity`,
`no_relation_pattern`, `anaphora_unresolved`,
`long_or_composed_sentence`, ...); correção de extractor/orçamento só
depois do diagnóstico.

## #048.5a — Varredura read-only de fatos-alvo alternativos

**Status:** ✅ concluída — **veredito: `no_viable_target` (0/5 fatos
elegíveis)**.

### Pergunta respondida

```text
Existe algum fato-alvo histórico que o extrator atual consiga converter
em tripla canônica em 3+ domínios distintos?
```

### Método

`scripts/audit_target_fact_sweep.py` (read-only) →
`reports/target_fact_sweep_048_5a.json`. 5 fatos candidatos × 4–6 fontes;
`hit` = match estrutural (campo sujeito ↔ `subject_any`, campo objeto ↔
`object_any`, predicado ∈ `predicates_ok` do vocabulário controlado) **OU**
Jev ≥ 0.65; objetos date-like descartados. Elegibilidade: ≥ 3 domínios com
tripla-alvo, ≥ 2 publishers, ≥ 1 fora de Wikipedia, ≤ 1 domínio só-`SER`,
nenhuma URL JS-only/paywall/404, nenhuma tripla-alvo date-like.

### Resultado

| Fato-alvo | dom. sentença | dom. tripla-alvo | Jev máx (domínio) | veredito |
|---|---|---|---|---|
| `BOTAFOGO --LOCALIZADO_EM--> RIO DE JANEIRO` | 5 | 0 | 0.14 | inelegível |
| `BOTAFOGO --VENCEU--> LIBERTADORES` | 5 | 0 | 0.06 | inelegível |
| `BOTAFOGO --VENCEU--> BRASILEIRAO` | 4 | **1 (UOL, exato=1)** | 0.94 | inelegível (1 < 3) |
| `PELE --DEFENDEU--> SANTOS` | 6 (pt-wiki: **51 sentenças-alvo**) | 0 | 0.10 | inelegível |
| `GARRINCHA --DEFENDEU--> BOTAFOGO` | 4 | 0 | 0.51 | inelegível (`lance.com.br` = JS-only) |

### Conclusão

Mesmo com fatos-alvo **distintos** dos #048.5 e com sentenças-alvo
abundantemente presentes (pt-wiki Pelé: 51 sentenças com Pelé+Santos →
**0 triplas convertidas**), o extrator atual não converte
sentença→triplo canônico em ≥ 3 domínios. O padrão do #048.5 **replica-se**
em todos os 5 fatos → evidência negativa da varredura A.
Nenhum `config/seed_clusters.yaml` alterado.

### Decisão (passo 4 do plano aprovado)

`A` terminou como evidência negativa → **#058.11** é o próximo issue
técnico (diagnóstico read-only da lacuna sentença→triplo; sem correção às
cegas; não aumentar `max_triples` antes de medir truncamento).
`#047.2`/`#045.3` continuam fechados (só renascem se a classe de causa
detectada for, respectivamente, variante nominal ou predicado não mapeado).

## #058.11 — Target-aware extraction gap analysis

**Status:** 📌 **aberta** — read-only/diagnóstico primeiro (decisão do
operador; evidência: #048.5 + #048.5a).

### Objetivo

Explicar por que `target_fact_sentences > 0` não converge em
`raw_triples`/`canonical_triples` que contenham o fato-alvo.

### Perguntas do diagnóstico (por caso sentença-alvo sem tripla-alvo)

```text
1.  A sentença foi considerada pelo extractor?
2.  A sentença passou no score mínimo?
3.  A sentença caiu fora do limite de max_triples=25?
4.  O extractor reconheceu a entidade sujeito?
5.  O extractor reconheceu o objeto?
6.  O extractor extraiu alguma tripla da sentença?
7.  Se extraiu, o predicado foi capturado?
8.  Se capturado, foi rejeitado pelo predicate mapper?
9.  Se mapeado, o objeto foi rejeitado pelo span validator?
10. Se passou, a tripla foi duplicata/colapsada em outra chave?
11. O fato estava em tabela/lista/infobox sem narrativa?
12. O fato dependia de anáfora ("the club", "o time", "ele")?
13. O fato estava em frase longa/composta/coordenada?
14. O fato estava em frase com data/parenthetical/lista?
```

### Classes de causa (saída do diagnóstico)

```text
sentence_not_considered
sentence_score_below_threshold
max_triples_truncation
missing_subject_entity
missing_object_entity
no_relation_pattern
predicate_unmapped
object_rejected_by_span_validator
duplicate_or_wrong_key
table_without_narrative
anaphora_unresolved
long_or_composed_sentence
date_or_list_contamination
unknown
```

### Regras

- read-only primeiro; **não** aumentar `max_triples` sem medir truncamento
  (experimento em memória com cap alto é diagnóstico, não mudança de código);
- `#047.2` renasce só com `missing_subject_entity`/`missing_object_entity`
  por variante nominal; `#045.3` renasce só com `predicate_unmapped`;
- não abrir `#048.6` (mais clusters), `#055` (API Almanaque congelada por
  compliance) nem treino (gate `verified_facts_domain_independent = 0 < 10`);
- evidência atual: `reports/cluster_productivity_048_5.json` (#048.5) e
  `reports/target_fact_sweep_048_5a.json` (#048.5a).

## #058.11 — Diagnóstico read-only (fase 1)

**Status:** ✅ fase 1 concluída —
`scripts/audit_extraction_gap.py` → `reports/extraction_gap_058_11.json`
(10 casos fato×URL, 54 sentenças-alvo sondadas; extractor intocado).

### Distribuição das classes de causa

| Nível caso (10) | classe | n |
|---|---|---|
| dominante | `no_relation_pattern` | 7 |
| dominante | `predicate_unmapped` | 3 |

| Nível sentença-alvo (54) | classe | n |
|---|---|---|
| `no_relation_pattern` | root ausente/não-verbal | **37** |
| `no_relation_pattern` | guarda de span na extração | 4 |
| `no_relation_pattern` | sem `nsubj` / sem `obj` | 1 / 1 |
| `predicate_unmapped` | `invalid_predicate` / `stopword_predicate` | 10 / 1 |
| conversão (probe) | `converted_in_probe` | **0** |

Roots não-verbais dominantes: `" (NUM)`, `​ (NUM)`, `PROPN`
(`Botafogo`×3, `Pelé`×2, `Garrincha`, `Campeonato`, `Flamengo`…) —
definições enciclopédicas e fragmentos com raiz nominal. Verbos rejeitados:
`restaurar`, `superar`, `acreditar`, `iniciar`, `esperar`, `velar`,
`trabalhar`, `comemorar`, `atendir`, `for`/`returns` (EN).

### Refutações (hipóteses do plano original)

- **`max_triples_truncation` refutado** — cap 25→500 (em memória) aumenta
  contagem (C1 25→57, C6 25→140, C7 25→53, C9 25→26) mas **0/10 casos**
  passam a conter a tripla-alvo (`hits500=0`). Não aumentar `max_triples`:
  medido, não é a causa.
- **`sentence_score_below_threshold` refutado** — 49/54 sentenças-alvo ≥
  0.6; e o extractor não filtra por score (só `analyze_text`).
- **`anaphora_unresolved` / `date_or_list_contamination` /
  `long_or_composed_sentence`** — 0 casos dominantes.
- **`predicate_unmapped` não reabre #045.3 como fix do gap** — a única
  tripla-alvo crua rejeitada no refino foi
  `Pelé --MARCAR--> dos gols do Santos` (`unmapped_predicate`): não expressa
  `--DEFENDEU-->`; os 11 verbos do probe tampouco são o verbo-fato.
  Vocabulário acessório, nunca a causa do fato-alvo ausente.

### Causa-raiz consolidada

```text
extract exige ROOT ∈ (VERB, AUX) por sentença (extractor.py:196-198).
As sentenças que expressam os fatos-alvo são majoritariamente
nominais/copulativas (definição enciclopédica) ou fragmentos →
a tripla jamais nasce, com qualquer orçamento.
```

### Alavancas possíveis (fase 2 — exigem decisão do operador)

- **F1 — caminho copular/nominal**: aceitar root `NOUN`/`PROPN` com filho
  `cop` (→ `SER`). **Risco**: inflar `SER` (colide com a calibração
  #058.10, EN share 81,4%); exige gate seletivo + dry-run com métrica
  `ser_share` antes/depois.
- **F2 — vocabulário (#045.3 parcial)**: só acessório — evidência atual
  não sustenta reabertura ampla.
- **F3 — qualidade do input de sentenças**: 37/54 raízes junk
  (NUM/frags de split) — reduz ruído, mas sozinha não converte a definição
  nominal.
- **Não fazer**: aumentar `max_triples`, mexer em `SENTENCE_SCORE_THRESHOLD`,
  fix de anáfora (sem evidência), seeds, #055, treino.

### Decisão pendente
Qual(is) alavanca(s) de F1–F3 executar e com qual gate de regressão
(`ser_share`, `duplicate_cross_domain`, `invalid_predicate`) — operador
define antes de qualquer edição em `extractor.py`.

## #058.11.1 — F3: rejeição de candidatos não-proposicionais (input)

**Status:** ✅ implementada (decisão do operador: **F3 primeiro**, depois
re-diagnóstico, depois F1 gateado; F2/#045.3 congelado).

### O que mudou

- **`src/cognition/extractor.py`** — `classify_sentence_candidate(text)` /
  `is_propositional_sentence(text)`: filtro determinístico (regex +
  contagem, sem spaCy/LLM) aplicado **como candidato**, antes da árvore de
  decisão de `extract_spacy` — a regra `ROOT ∈ (VERB, AUX)` **não mudou**.
- **`src/miner/source_productivity.py`** — `split_sentences_with_stats`
  filtra candidatas e devolve `pre_filter_rejections`
  (`too_short` / `noise_marker` / `non_propositional_fragment`), exposto em
  `analyze_text` para separar descartes do filtro dos descartes por score.
- **`src/miner/web_miner.py`** — `NOISE_SELECTORS` +`table.infobox`,
  `.infobox`, `figure`, `figcaption`, `.thumb`, `.gallerybox`,
  `#mw-navigation`, `.vector-menu`, `.catlinks`, `.toccolours` (infobox,
  legendas e menu saem do texto antes de virarem "sentenças").
- **`tests/test_extractor_input_quality.py`** — 16 fragmentos rejeitados
  (título-wiki, `Image source`, `Live Reporting`, `[1]`, `1962`,
  placares/linhas de tabela, zero-width de infobox) × 14 frases que
  **devem sobreviver** (combustível do F1: `is based in`, `home ground is`,
  `founded in 1904, …`, `Estádio Urbano Caldeira, also known as …`, DEF
  nominais PT) + buckets, `split_sentences`, `pre_filter_rejections`,
  `extract_spacy` com verbo em fragmento e `clean_html`.

### Regras do filtro (conservador — prefere deixar lixo passar a bloquear
frase nominal legítima)

```text
1. < 3 tokens alfabéticos            → too_short        (1962, [1], Editar)
2. marcador duro (wiki/caption/ref/infobox/zero-width) → noise_marker
3. indício de proposição (copula PT/EN, -ed/-ing, desinências PT) → aceita
4. marcador de nav/label (See also, full name, …)      → noise_marker
5. ≥ 2 tokens numéricos sem verbo                      → non_propositional_fragment
6. ≥ 4 tokens com vírgula (aposto) ou ≥ 2 capitalizados → aceita (nominal p/ F1)
7. caso contrário                                      → non_propositional_fragment
```

### DoD (commit 1)

- `python -m pytest -q` → **414 passed, 1 skipped** (venv com spaCy: 35/35
  no arquivo novo, inclui `extract_spacy`);
- `git diff -- requirements-dev.txt .github/workflows/ config/seed_clusters.yaml
  config/entity_aliases.yaml` → **vazio**; anti-leak OK; staging explícito;
- commit `fix(miner): reject fragmented non-propositional sentence candidates
  before extraction`.

### Resultado do rerun pós-F3 (após CI verde de `141ffa5`)

`scripts/audit_extraction_gap.py` (espelha o filtro F3 em `probe_sentence`
e agrega `pre_filter_rejections`) →
`reports/extraction_gap_058_11_post_f3.json` — 10 casos, fetch 200 em
todos, anti-leak OK.

| Métrica | fase 1 | pós-F3 |
|---|---|---|
| candidatas mantidas (`sentences_total`) | 2704 | 2381 |
| candidatas rejeitadas pelo filtro F3 | — | **259** (`too_short` 154, `non_propositional_fragment` 90, `noise_marker` 15) + blocos de infobox/figure removidos a montante no `clean_html` |
| sentenças-alvo | 54 | **47** (7 junk-targets descartadas) |
| probe **doc-layer** `root_ausente_ou_nao_verbal` | **37** | **5** |
| probe doc-layer `filtro_f3_nao_proposicional` (junk identificado) | — | 29 |
| roots não-verbais `NUM`/`PUNCT` | 15 | **0** |
| probe isolated `root_ausente` | 27 | 18 |
| casos por classe | 7 `no_relation` + 3 `predicate_unmapped` | **8 `no_relation` + 2 `predicate_unmapped`** |
| `converted_in_probe` / `hits500` | 0 / 0 | **0 / 0** (inalterado) |

Raízes junk de evidência (título-wiki, caption, placar, linha de infobox):
**eliminadas** — doc-layer root-junk 37→5 (<10 ✓), `NUM`/`PUNCT` → 0,
alvo-junk 54→47. Resíduo aceito por direção conservadora ("preferir falso
negativo"): ~4 sentenças-alvo isoladas de UI/tabela ainda passam
(`Related topics… Scores & Fixtures`, linha de fixture), header+frase
real fundidos (`History Formation and merger On 1 July 1894, …`) e
artefatos de parse EN-model-PT (`root=At/When/played`).

### Veredito do gate (regra do operador)

- ~~junk cai junto do `no_relation_pattern` → parar e reavaliar #048.5~~
  **não ocorreu**: junk de evidência → ~0, mas `no_relation_pattern`
  continua dominante (8/10 casos) **com sentenças limpas** e
  `converted_in_probe` segue **0** com qualquer cap;
- sentenças-alvo limpas remanescentes ainda falham por root nominal/
  parse (`Garrincha também é pai de…` = root `NOUN`, definição real),
  guarda de span e `invalid_predicate` de verbos não-fato → gargalo
  **estrutural confirmado**.

**→ Números sustentam GO para F1 (#058.11.2), gateado pelo dry-run
`ser_share` — decisão final do operador pendente (F1 não iniciada).**

### Conhecidas limitações (registradas, não bloqueantes)

- `find_doc_sent` do probe ainda funde sentenças no doc-layer (falsa
  atribuição de root) — limitação da sonda, não da produção;
- `-ed`/`-ing`/`-ando` genéricos deixam passar junk com dígitos
  (`Related`, `Fernando`) — deliberado no F3 para não bloquear
  `impressed/related` legítimos; reavaliar só com evidência nova.

## #058.11.2 — F1: extração nominal/copular gateada (extração)

**Status:** ✅ implementada + **dry-run GO** (decisão do operador: gates
`ser_share` + validação dupla de entidade; sem treino, seeds intocados).

### O que mudou

- **`src/cognition/extractor.py`** — flag `enable_nominal_copular` (default
  `True` no construtor — worker já nasce com F1 ativo; `False` explícito =
  byte-idêntico ao pré-F1):
  - **interleaved por sentença** em `extract_spacy`: verbal primeiro, se
    falhar e flag ligada → nominal (`_extract_nominal_copular`); resolve a
    starvation de cap (a 2ª passada global nunca tinha slot nas páginas
    25→25) sem reintroduzir duplos (dedup `casefold` só p/ triplas nominais);
  - frames regex `_NOMINAL_FRAMES`: POSSUIR (`home ground/estádio é…`),
    LOCALIZADO_EM (`is based in`, `com sede em`, `fica em`), DEFENDEU
    (`played/atuou/jogou … for`), VENCEU (`won/conquistou`, `foi campeão`);
  - dep-SER (`root AUX/VERB` com `cop`/`nsubj`) + possessive-glue;
  - **gates anti-inflação**: `_nominal_term_ok` (1 letra inicial, ≥2 dígitos),
    `is_function_word_span`, `_entity_strength` (conhecido → alias →
    genérico → **span minúsculo = weak** → ≥2 caps), `generic` proibido em
    objeto, `SER` só com sujeito não-genérico;
  - **known-entity rescue**: span inválido com entidade da whitelist vira a
    entidade (`nominal_subject_rescued`/`nominal_object_rescued`);
  - limpeza: split em `.`+Maiúsc, artigo interno EN (`Stadium The team's`),
    cauda verbal (`_NOMINAL_SUBJ_TAILS`), corte de objeto em pontuação +
    **hard-cut** com vírgula espaçada re-junta (`Noroeste , de Bauru` →
    `Noroeste de Bauru`), strip de prep inicial (`da Taça…`);
  - contadores `nominal_gate_reasons` restaurados em sucesso de frame
    (sem double-count) e **`rejection_reasons` verbal intocado**.
- **`tests/test_nominal_copular_extraction.py`** — 40 testes (ACCEPTED 9,
  REJECTED 6, gates, contadores, flag-off, refine canônico, integração
  `extract_spacy`).
- **`scripts/audit_nominal_copular_dry_run.py`** — dry-run de 10 gates com
  corpus único (`gap.fetch_all` + `clean_html`), cap de produção (25),
  anti-leak no JSON, pipeline note do `pt_regression` (verbal-first por
  sentença, corpus fixo).

### DoD (commit 2)

- `python -m pytest -q` → **437 passed, 18 skipped**; venv spaCy → **453
  passed** + 1 falha pré-existente (`test_validator_does_not_import…`);
- `git diff -- requirements* .github/workflows/ config/ src/cognition/{span_validator,predicate_mapper,canonicalizer,triple_refiner}.py`
  → **vazio**; staging explícito; anti-leak OK;
- **dry-run 10/10 gates PASS** (`reports/nominal_copular_dry_run_058_11_2.json`):
  `new_triples=16`, `target_fact_hits=4`, `ser_share_after=0.359`
  (**−4.1 p.p.** vs before), `generic_objects_rejected=37`,
  `clause_like_residual=0`, `pt_regression=false`,
  `top_invalid_predicates=[]`, `canonical_to_fact_gap=0`,
  `unaccounted_raw=0`;
- commit `feat(cognition): add gated nominal copular extraction for
  entity-bearing relations`.

### Resultado do dry-run (10 casos, gates do operador)

| Métrica | valor | gate |
|---|---|---|
| triplas novas (raw = canônico) | 16 / 16 | > 0 ✓ |
| fatos-alvo novos (canônicos) | **4** (C3, C6, C9, C10) | > 0 ✓ |
| `ser_share` after / delta | 0.359 / **−4.1 p.p.** | ≤ 0.84 e ≤ +3 p.p. ✓ |
| garbage residual (classe `'W Botafogo'`/`'Noroeste , de'`) | **0** | subjetivo ✓ |

Cobertura honesta dos 10 casos: **3/4 fatos-alvo únicos** (Libertadores ✓,
Pelé→Santos ✓, Garrincha→Botafogo ✓). **Botafogo→Rio = 0**: única sentença
com local (lead) é `noise_marker` do F3 (filtro congelado, correto) e
`rio de janeiro` não está na whitelist — sem overfit de página. **C4 BBC**
(`clinched`, `copa libertadores` fora da whitelist), **C5** (objeto
`título brasileiro` genérico → rejeitado pelo gate), **C7** (tripla existe
mas morre no sparse-band merge congelado do #048.8), **C8** (phrasings não
batem frames) = 0 por decisão honesta; reportados, não "consertados".

### Próximo (após CI verde)

Worker manual único de ingestão → medir `duplicate_cross_domain` /
`verified_facts` → decidir cenário A/B/C (#048.5).

---

## #048.5 (Cenário B) — Busca de terceira fonte independente

**Status:** 🟡 read-only concluído (batch 1); nenhuma candidata elegível encontrada.

### Auditoria: `scripts/audit_third_domain_candidates.py`

- Candidatas testadas: 35 URLs (homepages/sections de grandes sites + Britannica/Guardian/FIFA/CBF/Conmebol/Reuters/APNews/Ge/UOL/Estadao/RSSSF).
- **Elegíveis: 0** — nenhuma candidata extraiu o fato-alvo `DEFENDEU`/`JOGOU`/`ATUOU` com subject+object corretos.
- Problemas observados:
  - Homepages/sections (ge.globo, uol, estadao, uol) → 200 OK mas JS-heavy/paywall → `clean_html_empty` ou 0 canônicas.
  - Britannica/Guardian → 200 OK mas extraem SER/other predicates, não DEFENDEU.
  - FIFA/CBF/Conmebol/Reuters/APNews → 401/404/ConnectError/clean_html_empty.
  - RSSSF → tabelas sem narrativa → 0 canônicas.
- **Melhor fonte existente**: `gazetadoparana.com.br` (já no cluster) → extrai `MANUEL FRANCISCO DOS SANTOS --SER--> BOTAFOGO` (cross-domain válido, mas SER ≠ DEFENDEU).

### Conclusão do batch 1

Nenhuma terceira fonte **produtiva para DEFENDEU** encontrada em homepages/sections. Próxima iteração: buscar URLs de **artigos específicos** (não homepages) com frases declarativas como *"Garrincha played for Botafogo"* / *"Garrincha defendeu o Botafogo"*.

### Fase 2.0 — Diagnóstico de duplicatas :Fato/SPO ✅ COMPLETO

**Auditoria:** `scripts/audit_fact_duplicates.py` → `reports/fact_duplicate_audit_048_6_batch2.json`

**Resultado (read-only):**

```json
{
  "persisted_facts": 223,
  "graph_distinct_spo_keys": 223,
  "graph_scoped_gap": 0,
  "duplicate_groups_total": 0,
  "duplicate_groups_same_domain": 0,
  "duplicate_groups_cross_domain": 0,
  "duplicate_groups_hidden_potential_verified": 0
}
```

**Conclusão:** Todos os 223 `:Fato` têm chaves SPO únicas. **Zero duplicatas** — nenhuma same-domain, nenhuma cross-domain escondida. 

**Explicação do `canonical_to_fact_gap = -22`:** hipótese 1/2 confirmada.
- `distinct_canonical_keys = 199` (chaves vistas neste run, run-scoped)
- `persisted_facts = 223` (total no grafo, graph-total)
- `223 - 199 = 24` fatos antigos não tocados neste ciclo = acumulação incremental benigna.
- **Não é bug.** O #052.2 já separa `run_scoped_gap` / `graph_scoped_gap` corretamente.
- **Decisão:** Seguir para fase 2.1. **Não abrir #052.3.**

### Fase 2.1 — Descoberta de URLs article-like: ENCERRADA com evidência negativa

**Relatório:** `reports/third_domain_candidates_048_6_batch2.json` (+ supplement de testes diretos).

**P0 (Garrincha --DEFENDEU--> Botafogo): 15 URLs article-like testadas, 0 elegíveis.**

| URL | Resultado |
|---|---|
| gazetadoparana (já no cluster) | SER (não elegível p/ DEFENDEU) |
| extra.globo obituário | canon=4, 0 hits (predicado errado) |
| footballorbit, en-academic, biyografi.bio | 0 canônicas |
| brasilescola biografia | corpo em container JS; só nav extraído |
| britannica Garrincha (slug correto) | fetch bloqueado (bot protection) |
| lancepedia, ge team page | JS / 0 menções |
| futfogao, portaltela, esportelandia, blog, futebolnaweb | SER/outros/0 |

**P1–P4:** descoberta via DDG `BLOCKED_NETWORK` (rate-limit 202 após ~25 queries, html+lite). Teste direto único: Britannica Pelé (slug correto) → 88 sentenças, 5 raw/2 canon, **0 hits DEFENDEU** (extrai `SANTOS--VENCEU-->SAO PAULO`).

**Veredito batch 2:** falha aceitável com evidência. Não forçar. Pivotar para **Rota A (#059 curadoria de fontes estáticas)** ou escalar validação para clusters já com 3+ domínios produtivos. **Não abrir #047.2/#045.3** (sem evidência de alias/mapper gap). **Não abrir #052.3** (fase 2.0: zero duplicatas).

### Próximo

- #059 (Rota A): corpus alternativo HTML estático com prosa declarativa, ou
- #048.6 batch 3 em outros clusters (`pele_santos`, `santos_estadio`) se surgirem fontes, ou
- Aceitar Cenário B e aguardar licenciamento #055 para corpus rico.

---

## #059 — Atlas read-only de fontes estáticas/tabulares independentes ✅ COMPLETO

**Status:** ✅ completo — `eligible_for_058_12 = 2`. **Gate #058.12 ATINGIDO.**

**Artefatos:** `scripts/audit_static_tabular_sources.py` → `reports/static_tabular_source_atlas_059.json`.

**Achado estrutural:** RSSSF usa `<pre>` (texto pré-formatado `ANO Clube`), não `<table>`. Parser do atlas cobre ambos.

| URL | Status | Tabelas/pre | Rows alvo | Elegível |
|---|---|---|---|---|
| `rsssf.org/sacups/copalib.html` (Libertadores) | 200 | 2 pre | 22 (`2024 Botafogo`, finais) | ✅ |
| `rsssf.org/tablesb/brazchamp.html` (Brasileirão) | 200 | 5 pre | 32 (`1968/1995/2024 Botafogo`, `1961/62... Santos`) | ✅ |
| rsssfbrasil.com | 200 | 0 | 0 | ❌ (sem tabela parseável) |
| worldfootball.net | 403 | — | — | ❌ bot protection |
| cbf.com.br | ConnectError | — | — | ❌ |
| conmebol.com | 200 | 0 | 0 | ❌ JS |

**Caveat registrado:** match em `<pre>` é subject-only; alinhamento linha↔competição (copalib↔Libertadores, brazchamp↔Brasileirão) deve ser fixado no schema #058.12 por URL whitelistada. brazchamp NÃO sustenta alvo Libertadores.

**Mapeamento alvo→fonte:**
- `BOTAFOGO --VENCEU--> COPA LIBERTADORES` ← copalib.html
- `BOTAFOGO --VENCEU--> CAMPEONATO BRASILEIRO SERIE A` ← brazchamp.html
- `SANTOS --VENCEU--> COPA LIBERTADORES` ← copalib.html
- `SANTOS --VENCEU--> CAMPEONATO BRASILEIRO SERIE A` ← brazchamp.html

**Decisão:** abrir **#058.12 — extração tabular controlada** com schema mínimo `honours_competition_year` (clube --VENCEU--> competição, ano como metadado).

---

## #058.12 — Extração tabular controlada (schema honours) ✅ implementada + dry-run GO

**Status:** ✅ implementada + **dry-run GO 9/9 gates** (sem seed change, sem worker — batch 3 pendente de instrução).

### O que mudou

- **`src/cognition/table_extractor.py`** (novo, ~260 linhas) — `extract_honours_from_html(html, source_url, canonicalizer)`:
  - whitelist por URL → competição (`rsssf.org/sacups/copalib.html` → `COPA LIBERTADORES`; `rsssf.org/tablesb/brazchamp.html` → `CAMPEONATO BRASILEIRO SERIE A`); URL fora da whitelist → `[]`;
  - parse de `<pre>` winners-list (`ANO Clube`, estilo RSSSF) + `<table>` de honras (caption = clube, célula = competição);
  - gates próprios: vice (`2nd:`), placar (`3-1`), cabeçalho, genérico (`Total`), ano-só, clube fora do allowlist (`BOTAFOGO DE FUTEBOL E REGATAS`, `SANTOS FUTEBOL CLUBE`);
  - predicado sempre `VENCEU` (nunca `SER`); objeto sempre a competição whitelistada (ano vai para `metadata.year`, nunca objeto);
  - saída: dicts `{subject, predicate, object, confidence=0.8, metadata{year, source_type, extraction_method, table_schema, source_url}}`.
- **`tests/test_table_extractor.py`** (novo, 11 testes): honours simples, multi-ano (3 triplas), Total/ano-só rejeitados, URL não-whitelistada, `SER` nunca emitido, fixture fiel RSSSF `<pre>`, vice pulado, allowlist, ano-só-metadado.
- **`scripts/audit_table_extraction.py`** (novo): fetch único das 2 URLs + refine produção + narrativa baseline + 9 gates + anti-leak.
- **Arquivos congelados intocados:** `extractor.py`, `span_validator.py`, `predicate_mapper.py`, `canonicalizer.py`, `triple_refiner.py`, `config/seed_clusters.yaml`, `requirements*`, `.github/workflows/`, quórum.

### DoD

- `python -m pytest -q` → **448 passed, 18 skipped** (437 + 11 novos); venv spaCy → 427 passed + 0 failed (skips = gaps de env);
- **dry-run 9/9 gates PASS** (`reports/table_extraction_dry_run_058_12.json`): `canonical_triples_generated=7`, `target_fact_hits=7` (botafogo_libertadores 1, botafogo_brasileirao 3, santos_libertadores 3; santos_brasileirao 0 = cobertura da página, só linhas `2nd:` do Santos), `ser_share_delta=-0.7`, `top_invalid_predicates=[]`, `canonical_to_fact_gap=0` (run-scoped SPO+ano; colapso SPO a jusante por design), `unaccounted_raw=0`, `no_ser_emitted`, sem regressão PT/EN;
- commit `feat(cognition): add controlled tabular extraction for whitelisted honours tables`.

### Resultado do dry-run (2 URLs RSSSF)

| Métrica | valor | gate |
|---|---|---|
| triplas tabulares canônicas | 7 / 7 refine ok, 0 falhas | > 0 ✓ |
| fatos-alvo (3/4 fatos) | **7** | > 0 ✓ |
| `ser_share` narrativa → +tabular | 1.0 → 0.3 (**−0.7**) | ≤ 0 ✓ |
| rejeições (ruído contido) | 76 fora-allowlist, 140 placar, 72 vice, 56 genérico, 125 sem-match | informativo ✓ |

### Próximo (batch 3, pendente de instrução)

Adicionar URLs RSSSF ao `seed_clusters.yaml` + worker incremental → medir `duplicate_cross_domain` / `verified_facts` (alvo: `verified >= 1` via títulos).

---

## #052.2 — Separar contabilidade run-scoped vs graph-total

**Status:** ✅ implementada + CI verde.

### Problema

O campo ``canonical_to_fact_gap`` no ``/api/metrics`` misturava:
- ``distinct_canonical_keys`` (chaves vistas **neste run**, run-scoped)
- ``persisted_facts`` (total de fatos no grafo, graph-total)

Em runs incrementais isso gerava gap negativo (ex.: −22) sem indicação clara se era
contabilidade ou bug.

### Solução (commit `docs(autonomous): fix accounting split`)

- **`src/database/graph_connector.py`**: adicionado ``distinct_fact_hashes`` ao
  ``SNAPSHOT_QUERY`` (conta chaves distinct sujeito|predicado|objeto no grafo).
- **`app.py`** — ``IngestAccounting.snapshot``: novos campos:
  - ``run_distinct_canonical_keys`` (antes ``distinct_canonical_keys``)
  - ``run_persisted_facts_created`` (= ``new_facts_created``)
  - ``run_scoped_gap`` = ``run_distinct_canonical_keys - run_persisted_facts_created``
  - ``graph_distinct_fact_hashes`` (do grafo)
  - ``graph_scoped_gap`` = ``graph_distinct_fact_hashes - persisted_facts``
  - ``canonical_to_fact_gap`` mantido (compatibilidade; run vs graph).
- **`/api/metrics`**: passa ``graph_distinct_fact_hashes`` do snapshot do grafo.

### Validação

- Testes: **437 passed, 18 skipped**
- CI: **verde** (`36285015608`)
- Métricas pós-fix: run_scoped_gap ≥ 0, graph_scoped_gap explicável.

## #048.6 batch 3 — RSSSF seeds + worker incremental (PRÉ-WORKER)

**Status:** 🟡 wiring + seeds commitados; worker pendente.

### Preflight (§3)

- **3.1 Wiring — AUSENTE, corrigido** (`8ed47fb`): `enrich_payload` só via texto limpo; HTML bruto descartado. Fix: `web_miner._mine_with_client` preserva `payload["raw_html"]` SÓ p/ URLs whitelistadas (lazy import, sem ciclo); `enrich_payload` chama `enrich_payload_with_tables` (consome+remove antes do POST; nunca quebra narrativa); `tests/test_table_wiring.py` (6 testes: fixture→tripla canônica via path real, não-whitelist, sem-html, narrativa preservada). CI verde (`36333583036`).
- **3.2 Allowlist — OK sem mudança**: `rsssf.org` score **0.9** (TLD `.org` em `HIGH_TRUST_TLDS`); fora de `FORBIDDEN_DOMAINS`. Sem commit de segurança.
- **3.3 URLs — 200 estáveis**: copalib.html (17090 B) + brazchamp.html (16760 B), mesmos bytes do #059, sem redirect.

### Seeds (§4–§5)

- **3 clusters novos** (santos_brasileirao NÃO criado — 0 hits, sem evidência):
  - `botafogo_libertadores`: pt/en Botafogo wiki + copalib.html
  - `santos_libertadores`: pt/en Santos wiki + copalib.html
  - `botafogo_brasileirao`: pt/en Botafogo wiki + brazchamp.html
- Todos: 3 domínios, 2 publishers (Wikimedia+RSSSF), 1 não-wiki, HTTPS, sem duplicatas.
- Testes: `test_rsssf_honours_clusters_present_and_valid`, `test_rsssf_publisher_counts_as_independent`, `test_santos_brasileirao_cluster_absent_without_evidence` (13/13 no arquivo).
- Header do manifest atualizado (nota #048.5/#048.6; "nenhuma não-wiki produtiva" agora histórica).

## #048.6 batch 3 — RSSSF seeds + worker incremental

**Status:** PARTIAL (Cenário B sem incremento) — **Build:** `a01fee3`→`8932674` — **Worker run:** `36334393496` (success) — **Snapshot:** `reports/aura_snapshot_pre_048_6_batch3.json` (4125 nós, Fato=223) — **Baseline:** `reports/baseline_pre_048_6_batch3.json` — **Pós-run:** `reports/post_reingest_048_6_batch3.json`.

### O que aconteceu

1. **Tentativa 1 (`36333813255`) falhou silenciosamente**: `RAGEngine(top_k=40)` truncava a cauda; com 44 URLs, as RSSSF (fim da lista) nunca foram mineradas. Causa-raiz encontrada no log (0 menções rsssf) + reproduzida localmente.
2. **Fix (`8932674`)**: `WORKER_TOP_K=60` + `_merge_urls` (clusters curados primeiro) + 4 testes (`test_worker_seeds.py`). CI verde.
3. **Tentativa 2 (`36334393496`)**: wiring disparou em produção — `Extração tabular emitted=4` (copalib) + `emitted=3` (brazchamp); LLM `0/33` (heurística preservada); ingest 200 nas duas (entities 3 e 1).

### Métricas
| Métrica | Antes | Depois | Delta |
|---|---|---:|---:|
| facts | 223 | 227 | +4 |
| duplicate_cross_domain | 1 | 1 | 0 |
| facts_with_two_or_more_domains | 1 | 1 | 0 |
| facts_with_three_or_more_domains | 0 | 0 | 0 |
| verified_facts_domain_independent | 0 | 0 | 0 |
| table_extraction.canonical_triples_from_tables | 0 | 7 emitidas worker-side (3 persistidas*) | + |
| en_ser_share | — | — | estável |
| run_scoped_gap | 0 | 0 | 0 |
| graph_scoped_gap | explicado | explicado | — |
| unaccounted_raw | 0 | 0 | 0 |
| top_invalid_predicates | [] | [] | — |
| fallback_promoted_to_graph | 0 | 0 | — |
| vectors | 844 | 905 | +61 |
| FonteWeb | 36 | 38 | +2 (rsssf.org) |

\* 3 fatos-alvo VENCEU single-domain (rsssf): Botafogo→Libertadores, Botafogo→Brasileirão, Santos→Libertadores. 1 fato junk narrativo (`COPA DE CAMPEONES SER HELD IN SANTIAGO`) passou no refine — vetor conhecido, proposta §Próximo.

### Classificação
**Cenário B (sem incremento)** — a árvore não tem bucket exato: tabular chegou ao grafo (não-C), cross-domain não subiu (não-B pleno), sem divergência legítima p/ alias/mapper (não-D: variantes medium são junk-vs-clean, `promote_automatically=false`), sem regressão (não-E).

Leitura: wiki nunca emite as chaves VENCEU canônicas via narrativa (honras wiki também são tabelas — gap simétrico confirmado). Faltam confirmações wiki das mesmas chaves.

### Próximo passo
**#048.7 — estender whitelist tabular às tabelas de honras das páginas wiki** (pt/en Botafogo, pt/en Santos): mesmo parser/schema, competição por URL+caption; dry-run antes de seed. Secundário: **#058.12.1** — emissão table-only p/ URLs whitelistadas (conter junk narrativo tipo `COPA DE CAMPEONES SER...`). Não abrir #047.2/#045.3 (sem gap legítimo). Treino segue fechado (verified=0 < 10).

## #058.12.1 + #048.7 — Table-only policy e honras wiki controladas

**Status:** DONE — **Cenário A (vitória plena)** — **Commits:** `3e4fa8b` (Fase A) + `e34ffc1` (Fase C) — **CI:** verde nos dois — **Snapshot:** `reports/aura_snapshot_pre_048_7.json` (4144 nós, Fato=227) — **Worker run:** `36335999695` (success).

### Fases
- **A (policy):** `source_policy()` (rsssf=table_only, wiki=narrative_plus_table, resto default); narrativa suprimida p/ rsssf com reason `narrative_suppressed_table_only_source`; 7 testes. Em produção: copalib 2 + brazchamp 7 triplas suprimidas.
- **B (dry-run wiki):** `scripts/audit_wiki_honours_table_extraction.py` → `full=2, partial=0, eligible=True`; bug real achado e corrigido (anos de Estreia/Última contaminavam PT — anos SÓ da célula Campeão).
- **C (runtime):** `_parse_wiki_honours` + `WIKI_HONOURS_CLUBS` (só Botafogo pt/en) + normalização mínima de competição no `table_extractor.py`; 10 testes (incl. colisão 3-fontes); Em produção: pt wiki emitted=4, en wiki emitted=4.

### Métricas
| Métrica | Antes | Depois | Delta |
|---|---:|---:|---:|
| facts | 227 | 227 | 0 (só arestas CONFIRMA) |
| duplicate_cross_domain | 1 | 3 | +2 |
| facts_with_two_or_more_domains | 1 | 3 | +2 |
| facts_with_three_or_more_domains | 0 | 2 | +2 |
| verified_facts_domain_independent | 0 | **2** | **+2** |
| table_extraction.canonical_triples_from_tables | 0 | 7+8 worker-side | + |
| en_ser_share | — | estável | — |
| run_scoped_gap | 0 | 0 | — |
| graph_scoped_gap | explicado | explicado | — |
| unaccounted_raw | 0 | 0 | — |
| top_invalid_predicates | [] | [] | — |

### Classificação
**Cenário A — vitória plena.** Fatos verificados:
- `BOTAFOGO --VENCEU--> COPA LIBERTADORES` (pt+en+rsssf, confs=3) ✅
- `BOTAFOGO --VENCEU--> CAMPEONATO BRASILEIRO SERIE A` (pt+en+rsssf, confs=3) ✅
- Garrincha DEFENDEU segue confs=2 (inalterado).

### Limitação editorial
Verificados vêm de pt.wiki + en.wiki + rsssf = **3 domínios, 2 publishers** (Wikimedia+RSSSF). Métrica inalterada; dívida **#053** (publisher/eTLD+1) registrada, não implementada.

### Próximo passo
**#048.8** — replicar padrão honours p/ Santos (dry-run próprio antes) + avaliar table-only wiki? Não. Sem #047.2/#045.3 (variantes medium = junk-vs-clean, promote=false). Treino segue fechado (verified=2 < 10).

## #048.8 — Santos honours dry-run + runtime condicional

**Status:** DONE — **Cenário A (sucesso pleno)** — **Commits:** `7c38c60` (runtime) + este (docs/reports) — **CI:** verde — **Snapshot:** `reports/aura_snapshot_pre_048_8.json` (4144 nós, Fato=227) — **Worker run:** `36346996440` (success).

### Fases
- **A (dry-run read-only):** `scripts/audit_santos_honours_dry_run.py` → `full_collision=1` (Libertadores, pt+en+rsssf, confs=9); Brasileirão `partial` (só pt+en). Bugs reais achados e corrigidos no parser: (1) `_is_target` case-fold; (2) navboxes "Ligações externas" e tabelas de treinadores sendo lidas como honras → filtro `Competi*` + exclusão de navbox; (3) novo formato PT "Títulos" (classe livre, anos na célula de temporadas).
- **B (runtime):** `table_extractor.py`: Santos adicionado a `WIKI_HONOURS_CLUBS` **com allowlist por clube** (Santos: só `COPA LIBERTADORES`; Botafogo mantém Libertadores+Brasileirão); parser wiki reescrito p/ 3 formatos + filtro de navbox. +4 testes.
- **C (worker):** tabular disparou em todas as fontes (Santos pt/en=3+3, Botafogo pt/en=8+4, rsssf=4+3); ingest 200.

### Métricas
| Métrica | Antes | Depois | Delta |
|---|---:|---:|---:|
| facts | 227 | 227 | 0 (só arestas CONFIRMA) |
| duplicate_cross_domain | 3 | 4 | +1 |
| facts_with_two_or_more_domains | 3 | 4 | +1 |
| facts_with_three_or_more_domains | 2 | 3 | +1 |
| verified_facts_domain_independent | 2 | **3** | **+1** |
| table_extraction.canonical_triples_from_tables | — | 3+3+8+4+4+3 worker-side | + |
| en_ser_share | — | estável | — |
| run_scoped_gap | 0 | 0 | — |
| graph_scoped_gap | explicado | explicado | — |
| unaccounted_raw | 0 | 0 | — |
| top_invalid_predicates | [] | [] | — |

### Classificação
**Cenário A — sucesso pleno** (`verified ≥ 3`, `three_or_more_domains ≥ 3`, `duplicate ≥ 4`). Fato novo verificado:
- `SANTOS FUTEBOL CLUBE --VENCEU--> COPA LIBERTADORES` (pt+en+rsssf, confs=3) ✅

Fatôes verificados acumulados (3): Botafogo→Libertadores, Botafogo→Brasileirão, Santos→Libertadores. Garrincha DEFENDEU preservado (confs=2).

### Limitação editorial
3 domínios, **2 publishers** (Wikimedia+RSSSF). Dívida **#053** (publisher/eTLD+1) registrada, não implementada.

### Próximo passo
**#048.8.1 / #048.9** — replicar padrão p/ mais clubes/competições estáticas (ex.: Flamengo, Palmeiras, São Paulo) para acumular rumo a `verified >= 10` (gate de treino). Não abrir #047.2/#045.3 (mediums = junk-vs-clean, `promote_automatically=false`). Treino fechado (3 < 10).

## #048.9 — Multi-club honours scale-up

**Status:** DONE — **Cenário A (sucesso pleno, meta `verified >= 10` atingida)** — **Commits:** `79bfcd4` (fix encoding), `7170964` (runtime multi-clube), `008d643` (seeds) + este (docs/reports) — **CI:** verde — **Snapshot:** `reports/aura_snapshot_pre_048_9.json` (4144 nós, Fato=227) — **Worker run:** `36349468468` (success).

### Fases
- **A (dry-run):** `scripts/audit_multi_club_honours_dry_run.py` → **`full_collision=7`** (Libertadores ×5 clubes + Brasileirão Palmeiras/São Paulo), `partial=3`. Bugs reais achados e corrigidos: (1) URL percent-encoded não casava (`unquote`); (2) RSSSF é **latin-1** → mojibake de nomes acentuados; (3) `_club_mention_ok` fazia substring de "club"⊂"clube" (rejeitava Clube de Regatas do Flamengo/São Paulo Futebol Clube/Sport Club Internacional); (4) guard de year-range (tabela de participações Flamengo).
- **B (runtime):** `web_miner.fetch_page` decodifica utf-8→latin-1 (#048.9); `table_extractor.py`: `CLUB_ALLOWLIST` +5 clubes, `WIKI_HONOURS_CLUBS` +5 (allowlist por clube), `RSSSF_WINNER_ALIASES` (source-scoped), guard year-range, `unquote`. +13 testes.
- **C (worker):** 12 clusters/26 URLs; tabular disparou em 16 páginas; RSSSF agora lê São Paulo/Grêmio (encoding).

### Métricas
| Métrica | Antes | Depois | Delta |
|---|---:|---:|---:|
| facts | 227 | 328 | +101 (novas páginas wiki) |
| duplicate_cross_domain | 4 | 11 | +7 |
| facts_with_two_or_more_domains | 4 | 11 | +7 |
| facts_with_three_or_more_domains | 3 | **10** | +7 |
| verified_facts_domain_independent | 3 | **10** | **+7** |
| table_extraction.canonical_triples_from_tables | — | 16 páginas | + |
| run_scoped_gap / graph_scoped_gap | 0/explicado | 0/explicado | — |
| unaccounted_raw | 0 | 0 | — |
| top_invalid_predicates | [] | [] | — |
| vectors | 969 | 1011 | +42 |

### Classificação
**Cenário A — sucesso pleno:** `verified >= 10`, `three_or_more_domains >= 10`, `duplicate >= 11`. Fatos verificados (10):
Botafogo→Libertadores, Botafogo→Brasileirão, Santos→Libertadores, Flamengo→Libertadores, Grêmio→Libertadores, São Paulo→Libertadores, Palmeiras→Libertadores, Internacional→Libertadores, Palmeiras→Brasileirão, São Paulo→Brasileirão.

### Limitação editorial
3 domínios, **2 publishers** (Wikimedia+RSSSF). Dívida **#053** registrada.

### Nota de qualidade
+101 fatos vêm das novas páginas wiki dos clubes (narrativa) — ruído pré-existente do extrator narrativo (ex.: `FLAMENGO VENCEU JOGO`); auditorias estruturais limpas (0 duplicatas SPO, 0 invalid predicates, 0 near-collision). Honras RSSSF com `table_only` continua suprimindo narrativa.

### Próximo passo
**Gate de treino:** `verified >= 10` atingido; ainda exige `records >= 50`, dataset sanitizado, Python 3.11–3.13 e GPU. **Não treinar automaticamente.** Próximo: issue de export/avaliação do gate (sem abrir #047.2/#045.3). Opcional: #048.10 (mais clubes) e #053 (publisher independence).

## #060 — Avaliação read-only do gate de treino e preparação do dataset

**Status:** DONE (read-only) — **BLOCKED** para treino — **Commits:** este (docs + script + testes) — **CI:** verde — **Dataset candidato:** `.autonomous/training/dataset/verified_candidate.jsonl` (não commitado) — **Records:** 10 — **Verified facts:** 10 — **Training recommended:** false — **Training allowed:** false.

### O que foi feito (sem treinar)

- **Fase A:** confirmado export **read-only** — `GraphConnector.export_verified_facts` é `MATCH (f:Fato) WHERE f.verificado=true` (sem CREATE/MERGE/SET/DELETE); `write_dataset` grava JSONL local.
- **Fase B:** Python **3.14.7** (≠3.11–3.13), sem GPU, `llamafactory` ausente, Kaggle creds ausentes, `requirements-llamafactory.txt` presente mas NÃO instalado.
- **Fase C:** `train_lora.py export --source graph --limit 100` → **10 registros** Alpaca (JSONL).
- **Fases D–G:** `scripts/evaluate_training_gate.py` (read-only) valida JSONL + computa gates.
- **Fase H:** `train_lora.py config` → YAML válido, sem segredos (nota: `dataset_dir: data/sft` ≠ dir exportado).
- **Fases I–J:** relatório `reports/training_gate_evaluation_060.json` + `reports/training_dataset_export_summary_060.json`.

### Gates
| Gate | Resultado |
|---|---|
| verified_facts >= 10 | ✅ true |
| records >= 50 | ❌ false (10) |
| schema_valid | ✅ true (10/10 JSON) |
| sanitization (secret/date/generic/clause) | ✅ true (0/0/0/0) |
| provenance (10/10) | ✅ true |
| diversity (`unique_predicates>=3`, `non_VENCEU>=0.30`, …) | ❌ false (1 predicado: VENCEU) |
| publisher independence (`>=3` ou `ratio_ge3>=0.5`) | ❌ false (2: Wikimedia+RSSSF) |
| environment (Python/GPU/LlamaFactory/flag) | ❌ false |

### Distribuições
- predicates: `VENCEU`=10
- objects: `COPA LIBERTADORES`=7, `CAMPEONATO BRASILEIRO SERIE A`=3
- subjects: 7 · domains: pt/en/rsssf=10 cada · publishers: Wikimedia, RSSSF

### Classificação
**Cenário 1 — `BLOCKED_RECORDS_INSUFFICIENT`** (+ `DIVERSITY_GATE_FAILED` monocultura `VENCEU` + `PUBLISHER_INDEPENDENCE_WARNING` + `TRAINING_BLOCKED_ENVIRONMENT`).

### Próximo issue
**#048.10A** (escalar verified para records ≥ 50) + **#048.10B** (diversificar além de VENCEU: `JOGADOR --DEFENDEU--> CLUBE`, `CLUBE --POSSUIR--> ESTÁDIO`, `ESTÁDIO --LOCALIZADO_EM--> CIDADE`, …) + **#053** (publisher independence). Dry-run read-only antes de runtime; não abrir #047.2/#045.3 sem evidência; **não treinar**.

## #048.10 — Diversified verified-fact scale-up

**Status:** BLOCKED (read-only; sem mudança de runtime/seeds) — **Commits:** este (atlas + docs) — **CI:** verde — **Atlas:** `reports/diversified_fact_families_atlas_048_10.json` — **Worker:** não executado (nada novo a medir).

### Fase 0 — Atlas read-only de famílias (cap de produção = 25)
`scripts/audit_diversified_fact_families.py` testou 4 famílias não-VENCEU (DEFENDEU, LOCALIZADO_EM clube/estádio, POSSUIR) → **`eligible_families = 0`**:

| Família | Fato | confs | doms | verified |
|---|---|---:|---:|---|
| DEFENDEU | GARRINCHA→BOTAFOGO | 2 | 2 | ✗ |
| DEFENDEU | PELÉ→SANTOS | 2 | 1 | ✗ |
| LOCALIZADO_EM | BOTAFOGO→RIO / SANTOS→SANTOS / NILTON SANTOS→RIO | 0 | 0 | ✗ |
| LOCALIZADO_EM | URBANO CALDEIRA→SANTOS | 1 | 1 | ✗ |
| POSSUIR | SANTOS→URBANO CALDEIRA / BOTAFOGO→NILTON SANTOS | 0 | 0 | ✗ |

### Causas-raiz (evidência)
1. **Extração narrativa devolve junk, não o fato limpo**: `team --POSSUIR--> Estádio…` (sujeito genérico), `botafogo --LOCALIZADO_EM--> neighborhood of Botafogo` (invertido), `Mourisco Mar --LOCALIZADO_EM--> botafogo` (invertido). Não há gate de tabela p/ essas famílias (só honras).
2. **Cap de produção (25)**: `PELÉ→SANTOS` só atinge `confs=3` com cap=300 (3º URL traz a tripla além do índice 25); elevar o cap é mudança ampla — não autorizado.
3. **Sem 3º domínio p/ não-VENCEU**: RSSSF só cobre títulos; Wikimedia pt/en dão ≤2 domínios.

### Decisão (conservadora)
Sem mudança de runtime/seeds; sem aliases/predicates novos (falha é de extração de sujeito/objeto, não de rótulo); sem worker (nada novo). Não escalar apenas VENCEU (diretriz).

### Classificação
**Cenário D — `BLOCKED_RECORDS_INSUFFICIENT`** com causa-raiz **diversidade/cobertura** (também `DIVERSITY_GATE_FAILED`): records permanece 10 (<50); nenhuma família não-VENCEU verificável.

### Próximo issue
**#048.10B** (extração controlada player→club / club→stadium / →city, resolvendo o clube como SUJEITO) + **#059** (fontes estáticas independentes não-Wikimedia) + **#053** (publishers). Não abrir #047.2/#045.3; **não treinar**; quórum 3.

## #048.10B — Controlled DEFENDEU scale-up (target-aware selection)

**Status:** PARTIAL — **Cenário B** — **Commits:** `031edf2` (runtime: target-aware) + este (docs/reports) — **CI:** verde — **Snapshot:** `reports/aura_snapshot_pre_048_10B.json` (Fato=328) — **Worker run:** `36352492698` (success).

### O que mudou
- **`src/cognition/extractor.py`** — target-aware selection (Fase 1): sentenças com jogador(allowlist)+clube+indício de defesa são processadas antes do cap; no sparse-band, triplas-alvo `JOGADOR --DEFENDEU--> CLUBE` whitelisted são promovidas antes do fallback. Sem tripla-alvo a ordem é a congelada (#058.8). Com a flag nominal/fallback off nada muda.
- **`scripts/audit_defendeu_static_sources.py`** (novo) + **`tests/test_target_aware_selection.py`** (novo, 5 testes; 2 skip sem spaCy).
- **Sem mudança de seeds/aliases** (Fase 0/2 não exigiu).

### Atlas DEFENDEU (`reports/defendeu_static_sources_atlas_048_10B.json`)
| Fato | confs | doms | verified(3-dom) |
|---|---:|---:|---|
| PELÉ→SANTOS | **3** | 2 | ✗ (2 domínios) |
| GARRINCHA→BOTAFOGO | 2 | 2 | ✗ |
| NILTON/DIDI/JAIRZINHO/HELENO | 0 | 0 | ✗ |

### Métricas
| Métrica | Antes | Depois | Delta |
|---|---:|---:|---:|
| duplicate_cross_domain | 11 | **12** | +1 |
| facts_with_two_or_more_domains | 11 | **12** | +1 |
| facts_with_three_or_more_domains | 10 | 10 | 0 |
| verified_facts_domain_independent (canônico, 3 domínios) | 10 | **10** | 0 |
| records_total (export) | 10 | 10 | 0 |
| unique_predicates | 1 | 1 | 0 |
| non_VENCEU_ratio | 0.0 | 0.0 | 0 |

### Classificação
**Cenário B** — extração destravada: `PELÉ --DEFENDEU--> SANTOS FUTEBOL CLUBE` agora tem `confs=3` (pt+en) e `duplicate_cross_domain` subiu, mas o **terceiro domínio independente** falta → `verified_facts_domain_independent` (definição canônica = 3 domínios) permanece 10, e o dataset de treino segue 10 (todas VENCEU).

### Limitação / achado
Divergência de definição registrada: a auditoria `confs>=3 AND doms>=2` dá 11; o flag canônico do Space exige **3 domínios** → 10. É a dívida **#053** (domínio ≠ publisher; e definição de independência).

### Próximo passo
**#059C** (terceira fonte estática INDEPENDENTE não-Wikimedia p/ player-club DEFENDEU) + **#053** (independência por publisher) + **#055** (Almanaque com licença). **Não treinar**; quórum 3.

## #059C — Third independent source atlas for DEFENDEU

**Status:** DONE — **Cenário A (DEFENDEU destravado)** — **Commits:** `1accf09` (runtime), `1ec1c91` (seeds), `b109dbe` (security) + este (docs/reports) — **CI:** verde — **Snapshot:** `reports/aura_snapshot_pre_048_10C.json` — **Worker run:** `36354572850` (success).

### Hipótese vencedora
**H1 — club-context player records**: `rsssfbrasil.com/sel/jogclub.htm` ("jogadores cedidos ... **como jogador do CLUBE**"). Padrão controlado `NOME (N jogos ... como jogador do CLUBE)` → `JOGADOR --DEFENDEU--> CLUBE`.

Atlas (`reports/defendeu_third_source_atlas_059c.json`):
| Fato | domínios | collision |
|---|---|---|
| PELÉ→SANTOS | pt.wiki + en.wiki + **rsssfbrasil.com** | **full_collision** |
| GARRINCHA→BOTAFOGO | pt.wiki + en.wiki | partial (rsssfbrasil não cita Garrincha) |
| JAIRZINHO→BOTAFOGO | rsssfbrasil.com | (só 1 domínio) |

### O que mudou
- **`table_extractor.py`**: `extract_player_club_from_html` (schema `club_context_player_records`, allowlists jogador/clube, anos nunca objeto); `is_honours_url` cobre a URL; wiring em `enrich_payload_with_tables`. +8 testes.
- **`config/seed_clusters.yaml`**: `rsssfbrasil.com/sel/jogclub.htm` no cluster `pele_santos` (+1 domínio).
- **`security_protocol.py`**: `rsssf.org`/`rsssfbrasil.com` em `REPUTABLE_PUBLISHERS` (sem isso, `.com` = score 0.60 → quarentena).

### Métricas
| Métrica | Antes | Depois | Delta |
|---|---:|---:|---:|
| verified_facts_domain_independent (canônico) | 10 | **11** | **+1** |
| facts_with_three_or_more_domains | 10 | **11** | +1 |
| duplicate_cross_domain | 12 | 12 | 0 |
| records_total (export) | 10 | **11** | +1 |
| unique_predicates | 1 | **2** (VENCEU, DEFENDEU) | +1 |
| unique_objects | 2 | 3 | +1 |
| unique_subjects | 7 | 8 | +1 |
| unique_publishers | 2 | **3** (Wikimedia, RSSSF, RSSSF Brasil) | +1 |
| non_VENCEU_ratio | 0.0 | **0.09** | +0.09 |
| facts | 328 | 335 | +7 |

### Classificação
**Cenário A — DEFENDEU verificado destravado**: `verified > 10` (11), `non_VENCEU_ratio > 0`, `unique_predicates >= 2`, e **1 fato DEFENDEU verificado por 3 domínios** (`PELÉ --DEFENDEU--> SANTOS FUTEBOL CLUBE`, confs=4, domínios pt/en/rsssfbrasil).

### Limitação editorial (#053)
`publisher_independence_gate` = true (3 publishers) **mas** `rsssf.org`/`rsssfbrasil.com` podem ser a mesma família editorial (RSSSF). Registrado; métrica não alterada. `diversity_gate` ainda falso (records 11 < 50; non_VENCEU 0.09 < 0.30).

### Próximo passo
**#048.10D** — escalar DEFENDEU para mais jogadores/clubes com o mesmo padrão (H1 club-context; ex.: incluir mais páginas RSSSF Brasil / competições), rumo a records ≥ 50 e diversidade. **Não treinar** (records<50, diversity fail, ambiente). Quórum 3.

## #048.10D — Controlled DEFENDEU scale-up + third predicate family readiness

**Status:** BLOCKED (read-only; **Cenário C**) — **Commits:** este (atlases + #053.1 telemetria + docs) — **CI:** verde — **Worker:** NÃO executado (`predicted_new_verified = 0`).

### Trilho A — escala DEFENDEU
Atlas `reports/defendeu_scale_atlas_048_10D.json` → `full_collision=1` (PELÉ, já verificado), **0 novos**:
- `rsssfbrasil.com/sel/jogclub.htm` só cita Pelé+Jairzinho (allowlist); demais jogadores ausentes (grep=0).
- `perfis.htm` = perfis de membros (não jogadores); `rsssf.org/tables/*full.html` só crônicas (sem clube).
- GARRINCHA→BOTAFOGO fica partial (pt+en; falta 3º domínio); JAIRZINHO só na 3ª fonte.

### Trilho B — 3ª família predical
Atlas `reports/third_predicate_family_atlas_048_10D.json` → `eligible_families=0`:
- LOCALIZADO_EM: só `BOTAFOGO→RIO` limpo (pt.wiki, 1 domínio); en.wiki devolve bairro; estádios 0.
- POSSUIR: junk estrutural. **Sem colisão 3-domínios limpa.**

### #053.1 — telemetria (sem mudar métrica)
`evaluate_training_gate.py`: +`unique_publisher_families`/`effective_publisher_count`/`publisher_family_distribution`/`publisher_family_independence_ok`. Resultado: domínios 3, **famílias 2** (RSSSF unifica rsssf.org+rsssfbrasil.com) → WARNING confirmado. `verified_facts_domain_independent`/quórum inalterados. +1 teste.

### Métricas
| Métrica | Antes | Depois | Delta |
|---|---:|---:|---:|
| verified_facts_domain_independent | 11 | 11 | 0 |
| duplicate_cross_domain | 12 | 12 | 0 |
| facts_with_three_or_more_domains | 11 | 11 | 0 |
| records_total | 11 | 11 | 0 |
| unique_predicates | 2 | 2 | 0 |
| non_VENCEU_ratio | 0.09 | 0.09 | 0 |
| top_predicate_share | ~0.91 | ~0.91 | 0 |
| unique_publisher_families | — | **2** | (novo; #053.1) |
| player_club_canonical_triples | 2 | 2 | 0 |

### Classificação
**Cenário C — records insuficientes** (sem terceira fonte DEFENDEU; sem 3ª família segura).
`diversity_gate=false`; publisher independence = domínios PASS / família WARNING (#053.1); `environment_gate=false`. **Não treinar.**

### Limitação editorial
`rsssf.org` e `rsssfbrasil.com` = mesma família (RSSSF) → `effective_publisher_count=2`. Dívida #053/#053.1.

### Próximo passo
**#059D** (fontes estáticas independentes amplas p/ player-club) + **#048.10E** (3ª família segura) + **#055** (licença). Treino fechado; quórum 3.

## #059D + #048.10E — Broad third-family atlas e escala condicional DEFENDEU/DISPUTOU

**Status:** BLOCKED (read-only; **Cenário C**) — **Commits:** este (atlas + docs) — **CI:** verde — **Worker:** NÃO executado (`predicted_new_verified = 0`).

### Descobertas
- **Breadcrumb EN Botafogo → `rsssfbrasil.com/sel/jogclub.htm`** (o mesmo já explorado); não há página RSSSF Brasil dedicada ao Botafogo.
- Fontes externas: **worldfootball.net 403**, **fbref 403** (bot protection); `national-football-teams.com` 200 mas 0 player-club.
- **DISPUTOU é predicado controlado**, mas narrativa wiki produz junk (`jogo de abertura`/`amistoso`); `brazchamp.html` lista campeões (não participantes) → sem colisão limpa.

### Atlas `reports/broad_third_family_atlas_059d.json`
`predicted_new_verified = 0`; `defendeu_partial_collision_facts = 2` (Pelé/Jairzinho, já conhecidos); `third_family_eligible_sources = 0`.

### Métricas (inalteradas)
| Métrica | Antes | Depois | Delta |
|---|---:|---:|---:|
| verified_facts_domain_independent | 11 | 11 | 0 |
| records_total | 11 | 11 | 0 |
| unique_predicates | 2 | 2 | 0 |
| non_VENCEU_ratio | 0.09 | 0.09 | 0 |
| publisher_family_count | 2 | 2 | 0 |
| player_club_canonical_triples | 2 | 2 | 0 |

### Classificação
**Cenário C — records insuficientes.** `predicted_new_verified = 0` (< 3); nenhuma fonte de terceira família acessível por HTML estático; DISPUTOU sem colisão limpa.

### Limitação editorial
Terceira família editorial (worldfootball/fbref) bloqueada por bot protection → permanece Wikimedia + RSSSF (`publisher_family_count = 2`, WARNING #053.1).

### Próximo passo
**#048.10F/#059E** (fonte estática acessível para 3ª família) ou **#055** (Almanaque com licença). Não treinar; quórum 3.

---

## Modo Vercel-degradada — a Vercel não é caminho crítico

O deploy público na Vercel está bloqueado por quota do plano Hobby (`api-deployments-free-per-day` /
"Deployment rate limited — retry in 24 hours"). Isso **não** bloqueia o núcleo cognitivo do Nexus-Alpha.

**Fonte de verdade funcional:**
- HF Space para runtime/API/metrics (`status: online`);
- GitHub Actions / worker manual para ingestão;
- Neo4j AuraDB / Qdrant para memória;
- testes locais + CI `validate-project` para qualidade;
- auditorias read-only para evidência cognitiva.

A Vercel passa a ser tratada como camada **opcional** de publicação/visualização pública, salvo decisão
futura do Operador.

**Status (2026-09-28):**
- Vercel deploy: `BLOCKED_VERCEL_HOBBY_QUOTA` (**non-required**);
- Required checks: **nenhum** (branch `main` sem proteção; `Vercel=failure` é commit status não-obrigatório);
- CI required: **verde** (`validate-project=success`);
- Núcleo cognitivo: **CONTINUING**;
- Treino: bloqueado conforme gate (#059D/#048.10E; quórum 3);
- Classificação: **SUCCESS_VERCEL_DEGRADED_MODE**.

**DoD:** `DONE = CI required verde + testes locais + Space saudável quando aplicável + evidência read-only`.
`DONE` **não** exige Vercel verde enquanto a Vercel estiver em modo degradado/non-required.

**Referência:** `reports/BLOCKED_VERCEL_HOBBY_QUOTA.md`.

## Reconciliação pós-MODO VERCEL-DEGRADADA (#059E)

- A Vercel **recuperou** no commit `8cdab7f` (`success`), mas permanece **non-required** (`VERCEL_RECOVERED_NON_REQUIRED`).
- Alerta reconciliado **read-only**: `facts 335 -> 1894` e `duplicate_cross_domain 12 -> 23` eram **campos diferentes**
  do mesmo payload — `facts` (top-level) = nós **`Conceito`** (1894); `:Fato` = `persisted_facts` (335);
  `duplicate_cross_domain` de runtime (23) ≠ `facts_with_multi_domain`/graph (12).
- **Sem salto real de dados**: `last_ingest_at` inalterado (`2026-09-27T22:18:27Z`); `extraction_quality` idêntico ao baseline.
- `run_scoped_gap` / `graph_scoped_gap` ausentes por **build antigo do Space** (`0b5bc32`, 2026-09-24), anterior ao
  #052.2 (`503e6a3`); o código em `main` **tem** os campos → `FIELDS_ABSENT_DUE_STALE_SPACE_BUILD` (não é regressão de código).
- `ai-cron` está `disabled_manually`; **nenhum** run após `d362dcd`; **nenhum** `schedule` (todos `workflow_dispatch`).
- Sem contaminação: `top_invalid_predicates = []`, `fallback_promoted_to_graph = 0`, `unaccounted_raw = 0`.
- **Classificação: `RECONCILED_BENIGN_METRIC_DEFINITION`.** Próximo passo: redeploy do Space (após confirmar HEAD) para
  restaurar telemetria. Nenhum worker executado; nenhuma seed alterada; nenhum treino; invarianties preservadas.
- Referência: `reports/RECONCILIATION_059E_METRICS_JUMP.md`.

## #052.3 — Clareza métrica e restauração de telemetria

### Problema

O campo legado `facts` no `/api/metrics` representava contagem de `:Conceito`, não de `:Fato`.
Isso causou leitura ambígua de `facts=1894` como se fossem 1894 fatos (o `:Fato` real era 335).

### Correção

- `facts` foi mantido para compatibilidade.
- `concept_count` passou a representar explicitamente `:Conceito`.
- `fact_count` passou a representar explicitamente `:Fato`/`persisted_facts`.
- `metric_glossary` foi adicionado ao payload.
- `run_scoped_gap` e `graph_scoped_gap` já existem no código (`_ingest_accounting.snapshot()`); a ausência
  no payload é **build antigo do Space** (anterior ao #052.2) — requer redeploy (runbook
  `reports/BLOCKED_052_3_SPACE_REDEPLOY.md`).

### Glossário

| Campo | Significado |
|---|---|
| facts | legado; para compatibilidade representa contagem de `:Conceito` |
| concept_count | contagem de nós `:Conceito` |
| fact_count | contagem de nós `:Fato` persistidos |
| persisted_facts | contador interno de fatos persistidos (`:Fato`) |
| duplicate_cross_domain | contador de runtime do ingest para duplicatas cross-domain |
| facts_with_multi_domain | fatos com >= 2 domínios distintos |
| verified_facts_domain_independent | fatos com >= quórum de domínios distintos |
| run_scoped_gap | gap contábil do run atual |
| graph_scoped_gap | gap contábil total do grafo |
| unaccounted_raw | raw não contabilizado (deve ser 0) |
| fallback_promoted_to_graph | deve ser 0 |
| top_invalid_predicates | deve ser [] |

- Classificação: `PARTIAL_052_3_CODE_READY_SPACE_STALE` (código pronto; Space pendente de redeploy manual).
- Referência: `reports/RECONCILIATION_052_3_METRICS_CLARITY.md`.

## #059E — Atlas DISPUTOU/OSM/DEFENDEU alternativo

**Status:** PARTIAL (read-only; sem worker, sem seeds, sem treino)
**Space restoration:** tentado (`POST .../restart` factory_reboot = 200) mas **source stale**
(`sha=85355c6d`, 2026-09-25) → `SPACE_SOURCE_STALE_REQUIRES_REDEPLOY`; campos novos ainda ausentes.
**DISPUTOU full collision:** 0 (partial 3) — sem terceira fonte gratuita independente.
**GEO full collision:** 4 (partial 4) — READY (gate >= 3).
**DEFENDEU alternative full collision:** skipped_budget.
**Classification:** `PARTIAL_059E_ATLAS_READY_SPACE_STALE`.
**Next step:** Operador redeploya o Space (runbook). Depois, runtime condicional para LOCALIZADO_EM;
DISPUTOU reavalia #055 (licença) ou fonte estática alternativa.

- Scripts read-only: `scripts/audit_disputou_participation_atlas.py`, `scripts/audit_geo_localizado_osm.py`
  (OSM via Nominatim/ODbL; Overpass instável nesta janela), `tests/test_audit_059e_atlases.py`.
- Relatórios: `reports/disputou_participation_atlas_059e.json`, `reports/geo_localizado_osm_atlas_059e.json`,
  `reports/059e_dry_run_integrated.json`.

## #048.10G — Controlled LOCALIZADO_EM via OSM/Nominatim

**Status:** DONE (código + testes + CI; **worker NÃO executado**)
**Space redeploy:** pendente do Operador (`reports/BLOCKED_048_10G_SPACE_REDEPLOY.md`)
**DISPUTOU:** adiado — sem terceira fonte gratuita com full collision
**GEO:** implementado/testado; pronto para worker futuro após redeploy

### Candidatos GEO (full collision, atlas #059E)

ALLIANZ PARQUE · MORUMBI · PACAEMBU · NEO QUÍMICA ARENA --LOCALIZADO_EM--> SÃO PAULO.

### Módulos/camadas

- `src/cognition/geo_extractor.py` — extração pura (OSM JSON + wiki) + `fetch_nominatim_json` seguro.
- `config/security_policies.json` — allowlist `nominatim.openstreetmap.org` (ODbL) + família `OpenStreetMap`.
- `config/seed_clusters.yaml` — 4 clusters GEO (pt + en + OSM/Nominatim).
- `scripts/audit_geo_localization_dry_run.py` → `reports/geo_localization_dry_run_048_10G.json`.
- `scripts/check_space_telemetry.py` — preflight anti-worker em Space stale.

### Métricas projetadas (dry-run offline; aprovado)

| Métrica | Antes | Projetado |
|---|---:|---:|
| verified_facts_domain_independent | 11 | 15 |
| records_total | 11 | 15 |
| unique_predicates | 2 | 3 |
| non_VENCEU_ratio | 0.09 | 0.33 |
| top_predicate_share | 0.91 | 0.67 |
| publisher_family_count | 2 | 3 (OSM) |

### Limitações

- `top_predicate_share` ainda > 0.50; `records_total` < 50; treino continua **fechado**.
- Worker não executado porque o Space está stale (source antigo).

## #048.10G.1 — Caminho seguro de ingestão GEO no worker

**Status:** DONE (código + testes + CI; **worker NÃO executado**)
**Space redeploy:** pendente do Operador (`reports/RUNBOOK_048_10H_GEO_WORKER.md`)
**Arquitetura escolhida:** **caminho isolado no worker** (Nominatim JSON → `geo_extractor`),
**sem alterar `web_miner.py`**.
**Dry-run GEO worker:** 4 triplas previstas; gate **aprovado**.
**Pronto para #048.10H:** true (após redeploy do Space).

- `scripts/worker_cycle.py`: separa URLs Nominatim (`_split_geo_urls`) do pipeline HTML e injeta os
  payloads GEO (`_build_geo_payloads`) no mesmo refine/ingest — sem bypass de validação.
- `WORKER_TOP_K` agora é **seed-aware**: `max(64, len(SEED_QUERIES) + active_seed_urls + 10)`
  (atual: **74**; `active_seed_urls=39`; `truncation_risk=false`).
- Dry-run: `scripts/audit_geo_worker_dry_run.py` → `reports/geo_worker_dry_run_048_10G_1.json`.
- Classificação: `SUCCESS_048_10G_1_WORKER_PATH_READY_SPACE_STALE`.

> Este ciclo **não executou worker**. **Não escreveu** em Neo4j/Qdrant. **Não treinou.**
> Aguarda redeploy do Space para o #048.10H.

## #048.10H — GEO worker incremental (condicional)

**Status:** **BLOCKED** (Space stale)
**Space preflight:** **STALE** — `scripts/check_space_telemetry.py` → `BLOCKED_SPACE_STALE_TELEMETRY`
(faltando `concept_count`, `fact_count`, `run_scoped_gap`, `graph_scoped_gap`).
**Worker run:** **NÃO executado** (preflight reprovou; nenhum snapshot, nenhuma escrita).
**Classificação principal:** `BLOCKED_048_10H_SPACE_STALE`.

> Este ciclo **não executou worker**. **Não escreveu** em Neo4j/Qdrant. **Não treinou.**

## #048.10I — Atlas DEFENDEU Botafogo (fallback read-only)

**Status:** **BLOCKED**
**RSSSF Brasil (página dedicada do Botafogo):** **não encontrada** — `clubes/botafogo.htm`,
`clubes/bfr.htm`, `tablesn/botafogo.htm`, `sel/botafogo.htm`, `recordes/botafogo.htm` → **404**.
**defendeu_full_collision_facts:** **0** · **defendeu_partial_collision_facts:** **0**.
**Evidência de domínio único:** NILTON SANTOS (pt.wikipedia.org) · JAIRZINHO (`rsssfbrasil.com/sel/jogclub.htm`).
**Classificação secundária:** `BLOCKED_048_10I_NO_THIRD_SOURCE`.
**Próximo passo:** retomar **#048.10H** após o redeploy do Space; DEFENDEU aguarda **#055** (licença) ou 3ª fonte.

- Script read-only: `scripts/audit_defendeu_botafogo_rsssf_atlas.py` → `reports/defendeu_botafogo_rsssf_atlas_048_10I.json`.
- A citação "Source: RSSSF Brasil – Botafogo" **não** é fonte independente por si só; sem URL dedicada acessível.

## #048.10H.1 — Hard telemetry gate + GEO expected-fact validator

**Status:** DONE
**Space preflight:** STALE (`check_space_telemetry` → `BLOCKED_SPACE_STALE_TELEMETRY`)
**Worker executado:** NÃO
**Gate duro implementado:** SIM — `src/ops/space_telemetry.py` + enforcement em `scripts/worker_cycle.py`
(fail-fast **antes** de fetch/miner/ingest; nenhuma escrita tentada)
**Validador GEO implementado:** SIM — `scripts/validate_geo_expected_facts.py` + registry
`reports/geo_expected_facts_048_10H.json` (offline, sem rede)
**Pronto para #048.10H:** true (após redeploy do Space)

- Gate valida: `concept_count`, `fact_count`, `run_scoped_gap`, `graph_scoped_gap`, `unaccounted_raw=0`,
  `quorum=3`, `fallback_promoted_to_graph=0`, `top_invalid_predicates=[]`; razões:
  `BLOCKED_SPACE_STALE_TELEMETRY` / `BLOCKED_QUORUM_MISMATCH` / `BLOCKED_FALLBACK_PROMOTED` /
  `BLOCKED_INVALID_PREDICATES` / `BLOCKED_UNACCOUNTED_RAW` / `MISSING_SPACE_CREDENTIALS` / `MISSING_SPACE_URL`.
- Escape offline/local: `--allow-unverified-local` / `NEXUS_ALLOW_UNVERIFIED_LOCAL=true` (nunca em produção).

> Este ciclo **não executou worker**. **Não escreveu** em Neo4j/Qdrant. **Não treinou.**
> O worker agora **se recusa a abrir a porta sozinho** em Space stale. O #048.10H real permanece
> dependente do redeploy do Space pelo Operador.

## #048.10K — GEO expansion read-only atlas

**Status:** DONE
**Space preflight:** STALE (worker não executado)
**Novos full_collision GEO candidatos:** 5
**Next batch registry:** `reports/geo_expected_facts_next_batch_048_10k.json`
**Pronto para #048.10L:** true (após #048.10H real)

Lote candidato (atlas #048.10K; pt+en+Nominatim/ODbL):

```text
ESTÁDIO OLÍMPICO NILTON SANTOS --LOCALIZADO_EM--> RIO DE JANEIRO
MARACANÃ --LOCALIZADO_EM--> RIO DE JANEIRO
BEIRA-RIO --LOCALIZADO_EM--> PORTO ALEGRE
MINEIRÃO --LOCALIZADO_EM--> BELO HORIZONTE
ARENA FONTE NOVA --LOCALIZADO_EM--> SALVADOR
```

- Script read-only: `scripts/audit_geo_expansion_atlas_048_10k.py` → `reports/geo_expansion_atlas_048_10k.json`
  (10 estádios; 30 requests ≤ orçamento 80; `junk=0`; `forbidden=0`; `ambiguous=0`).
- Runbook: `reports/RUNBOOK_048_10L_GEO_EXPANSION.md`.
- `pytest = 578 passed, 39 skipped`.

> Este ciclo **não executou worker**. **Não escreveu** em Neo4j/Qdrant. **Não alterou seeds.**
> **Não alterou runtime GEO.** **Não treinou.** O #048.10H real permanece dependente do redeploy do Space.
> A expansão GEO futura depende deste atlas e de novo dry-run/runtime em **#048.10L**.

## #052.4 — Safe HF Space source synchronization

**Status:** BLOCKED (histórico divergente) + fallback local pronto
**Space sync tentado:** SIM
**Push permitido:** NÃO (`space/main` não é ancestral de `HEAD`)
**Push executado:** NÃO
**Build resultado:** N/A
**Telemetria após sync:** ainda ausente
**Worker executado:** NÃO
**Pronto para #048.10H:** false (aguarda redeploy do Space pelo Operador)

- Diagnóstico: Space `sha=85355c6d…` (`2026-09-25`), `private=true`, `stage=RUNNING`; git remoto
  acessível; backup clonado (sha `85355c6d…`).
- Causa: o repo do Space é **snapshot de deploy** com histórico próprio → sem fast-forward.
  Caminho correto = `scripts/deploy_hf_space.py` (upload de subconjunto).
- Classificação: **`BLOCKED_052_4_SPACE_HISTORY_DIVERGED`**.

### Fallback local (executado)

- Validador GEO **multi-lote** (`--expected-next`) com status por lote
  (`PENDING_WORKER` / `FUTURE_BATCH_NOT_SEEDED` / `OK` / `FAIL`) e agregação.
- Next batch dry-run offline: `reports/geo_next_batch_dry_run_052_4.json`
  (`next_batch_full_collision_facts=5`, `junk=0`, `forbidden=0`, `eligible=true`).
- Seeds **não** alteradas; runtime GEO **não** alterado; espaço **não** redeployado.

> Este ciclo **não executou worker**. **Não escreveu** em Neo4j/Qdrant. **Não treinou.**
> **Não fez force-push.** **Não alterou quórum.**

## #052.5 — Safe HF Space redeploy

**Status:** DONE
**Deploy automático tentado:** SIM (upload allowlisted; **não** git push)
**Dry-run:** `DRY_RUN_OK` (79 arquivos, 499417 bytes, sem segredos)
**Upload:** `UPLOAD_OK`
**Build:** `RUNNING` (novo `sha=3aa1ad22…`, `lastModified=2026-09-28T22:30:33Z`)
**Telemetria após deploy:** **READY** (`ok=true`) — `concept_count=1894`, `fact_count=335`,
`run_scoped_gap=0`, `graph_scoped_gap=-335`, `unaccounted_raw=0`, `quorum=3`,
`fallback_promoted_to_graph=0`, `top_invalid_predicates=[]`
**Worker executado:** NÃO
**Pronto para #048.10H:** **true**

- Wrapper endurecido: `scripts/deploy_hf_space_safe.py` (dry-run padrão, scan anti-leak, manifest
  path/size/sha256, `--execute` explícito; nunca imprime/embute token).
- Venv isolado `.autonomous/deploy/deploy_venv` (`huggingface_hub==2.0.0`) — não instalado no `.venv` principal.
- O repo do Space é **snapshot divergente**; deploy correto é **upload allowlisted**, não fast-forward git.

> Este ciclo **não executou worker**. **Não escreveu** em Neo4j/Qdrant. **Não treinou.**
> **Não fez force-push.** **Não alterou quórum.**
> Próximo: **#048.10H real** (worker GEO lote atual), com snapshot/baseline/worker/post/audits e
> `validate_geo_expected_facts`.

## #048.10H real — GEO worker incremental

**Status:** **BLOCKED** (GEO persistiu, mas não verificou por 3 domínios)
**Space preflight:** **OK** (`ok=true`)
**Snapshot:** read-only AuraDB (`nodes=4538`, `rels=3785`; não commitado)
**Worker runs:** `36498263682` (422 confidence) · `36499101812` (após fix, GEO 200) — ambos `success`
**Fix aplicado:** `ca351aa` `fix(worker): add confidence to GEO entities for Space ingest contract`
**Cron:** `disabled_manually` antes e depois

### Métricas

| Métrica | Antes | Depois | Delta |
|---|---:|---:|---:|
| verified_facts_domain_independent | 11 | 11 | 0 |
| records_total | 11 | 11 | 0 |
| fact_count | 335 | 403 | +68 |
| concept_count | 1894 | 2008 | +114 |
| unique_predicates | 2 | 2 | 0 |
| non_VENCEU_ratio | 0.09 | 0.09 | 0 |
| publisher_family_count | 2 | 2 | 0 |
| geo_triples_canonical | 0 | 3 | +3 |
| unaccounted_raw | 0 | 0 | 0 |
| top_invalid_predicates | [] | [] | 0 |
| fallback_promoted_to_graph | 0 | 0 | 0 |

### Classificação

**`BLOCKED_048_10H_GEO_EXTRACTION`** — os 3 fatos GEO canônicos persistiram (Nominatim, 1 domínio),
mas a narrativa wiki PT/EN **não** gerou a mesma chave canônica → sem corroboracão de 3 domínios.
`validate_geo_expected_facts`: `expected_facts_verified=0/4`, `junk=0`, `regression=false`.

### Dívida observacional

`graph_scoped_gap negativo` (`-403`) registrado como **#052.3.1**, não bloqueante.

### Treino

`training_gate_evaluation`: `records_total=11`, `unique_predicates=2`, `diversity_gate=false`,
`training_recommended=false`, `training_allowed=false`. **Treino não executado.**

### Próximo passo

**#048.10H.2** (debug do caminho GEO: canonicalização/predicado/cap) e **#052.3.1** (contabilidade).
Não escalar next batch (#048.10L) antes de entender o bloqueio.

> Este ciclo executou **2 workers** (autorizado, diagnóstico entre tentativas), **não treinou**,
> **não alterou seeds nem runtime cognitivo**, **não fez force-push**.

## #048.10H.2 — GEO canonicalization parity debug

**Status:** **DIAGNOSED / BLOCKED por escopo**
**Worker executado:** NÃO
**Causa-raiz GEO:** a narrativa wiki **não** produz `ESTÁDIO --LOCALIZADO_EM--> CIDADE`
  - R1/R2: o extrator narrativo gera `LOCALIZADO_EM` com sujeito/objeto **invertidos ou ausentes**
    (ex.: `SÃO PAULO FUTEBOL CLUBE --> ESTADIO DO MORUMBI`; `PALMEIRAS… --> SANTOS FUTEBOL CLUBE`);
  - R3: a página PT do Allianz Parque **não contém** verbo de localização útil;
  - ambiguidade: `extract_geo_localizado_from_wiki_html` resolve o estádio pelo **texto inteiro**
    e fica ambíguo quando a página cita estádios irmãos → `[]`;
  - ruído: infobox/JSON/template no HTML limpo.
**Patch mínimo aplicado:** SIM (menor): `geo_extractor` passou a aceitar o padrão `located in`;
  **não** resolve a ambiguidade de página inteira (não atinge 4/4).
**Dry-run pós-patch:** `reports/geo_canonical_fix_dry_run_048_10h_2.json` → `full_collision_facts=0`, `junk=0`
**Pronto para #048.10H.3:** **false**

- Diagnóstico: `scripts/audit_geo_canonical_parity.py` → `reports/geo_canonical_parity_048_10h_2.json`.
- Bloqueio: `reports/BLOCKED_048_10H_2_GEO_PARITY.md`.
- Dívida observacional: `reports/observability_graph_scoped_gap_052_3_1_diagnosis.md` (#052.3.1).

> Este ciclo **não executou worker**. **Não escreveu** em Neo4j/Qdrant. **Não alterou seeds.**
> **Não treinou.** O next batch **#048.10L permanece congelado** até o lote atual verificar.
> Próximo: **#048.10H.2.1** — parser wiki GEO dedicado (subject pinado por URL + mesma frase + lead/infobox + rejeição de bairro/owner), com dry-run exigido 4/4 e zero junk.

## #048.10H.2.1 — Dedicated GEO wiki parser + OSM fallback

**Status:** **DONE**
**Worker executado:** NÃO
**Parser wiki GEO implementado:** **SIM** (`src/cognition/geo_wiki_parser.py`, subject pinado por URL, cidade só na mesma frase/infobox, allowlist estrita)
**OSM fallback implementado:** **SIM** (`display_name_expected_context` source-scoped + retry 5xx em `fetch_nominatim_json`)
**Wiring:** URLs wiki GEO roteadas ao parser dedicado; narrativa genérica **suprimida** para essas URLs
**Dry-run 4/4:** **true** (`reports/geo_wiki_parser_dry_run_048_10h_2_1.json`):
`osm=4`, `wiki_pt=4`, `wiki_en=4`, `full_collision=4`, `canonical_key_mismatches=0`, `junk=0`, `negatives 8/8 rejeitadas`
**Pronto para #048.10H.3:** **true** (`reports/RUNBOOK_048_10H_3_GEO_RETRY.md`)

- Reconciliação OSM Neo Química: `reports/osm_neo_quimica_failure_reconciliation_048_10h_2_1.md`
  (`no_clean_city_evidence` = Allianz/parse; `502` = Neo Química/rede).
- Matriz de paridade: `reports/geo_canonical_parity_048_10h_2_1.json`.

> Este ciclo **não executou worker**. **Não escreveu** em Neo4j/Qdrant. **Não alterou seeds.**
> **Não alterou** canonicalizer/predicate_mapper/span_validator/entity_aliases. **Não treinou.**
> #048.10L permanece congelado; #052.3.1 permanece separado.
> Próximo: **#048.10H.3** — retry do worker GEO (snapshot/baseline/worker/post/validate).

## #048.10H.3 — GEO worker retry com validação fact-level

**Status:** **PARTIAL**
**Space preflight:** OK · **Snapshot:** read-only (nodes=5107, rels=4057)
**Worker run:** `36506930895` (success) · **cron:** `disabled_manually` antes/depois · **dispatches:** 1
**Worker executado:** SIM (1)

### Fatos GEO
- **Verificados (inferidos):** PACAEMBU → SÃO PAULO · NEO QUÍMICA ARENA → SÃO PAULO (pt+en+osm)
- **Parciais:** ALLIANZ (OSM `no_clean_city_evidence`) · MORUMBI (OSM POST `502`) → pt+en
- Parser wiki dedicado: **8/8** triplas, `generic_wiki_noise_suppressed=true`

### Métricas

| Métrica | Antes | Depois | Delta |
|---|---:|---:|---:|
| verified_facts_domain_independent | 11 | **13** | +2 |
| records_total | 11 | **13** | +2 |
| fact_count | 403 | 404 | +1 |
| concept_count | 2008 | 2009 | +1 |
| unique_predicates | 2 | **3** | +1 |
| non_VENCEU_ratio | 0.09 | >0.09 | + |
| top_predicate_share | ~0.91 | <0.91 | - |
| publisher_family_count | 2 | 2 | 0 |
| facts_with_multi_domain | 12 | 16 | +4 |
| duplicate_cross_domain | 23 | 29 | +6 |
| graph_scoped_gap | -403 | -404 | (dívida #052.3.1) |
| unaccounted_raw | 0 | 0 | 0 |
| top_invalid_predicates | [] | [] | 0 |
| fallback_promoted_to_graph | 0 | 0 | 0 |

### Classificação

**`PARTIAL_048_10H_3_GEO_PROGRESS`** — o terceiro predicado (`LOCALIZADO_EM`) **nasceu** no grafo
verificado (`unique_predicates = 3`), com 2/4 fatos GEO verificados e **zero junk/regressão**.

### Análise de falha real

`reports/geo_real_page_failure_analysis_048_10H_3.md` — ALLIANZ (R10/R11 OSM sem cidade estruturada) ·
MORUMBI (R9 502 transitório no POST). Próximo: **#048.10H.4**.

### Dívida observacional

`graph_scoped_gap negativo` (`-404`) — **#052.3.1**, não bloqueante.

### Treino

`training_gate_evaluation`: `records_total=13`, `unique_predicates=3`, `diversity_gate=false`,
`training_recommended=false`, `training_allowed=false`. **Treino não executado.**

> Este ciclo executou **1 worker** (autorizado), **não escalou #048.10L**, **não alterou seeds**,
> **não treinou**, **não fez force-push**. Próximo: **#048.10H.4** (corrigir ALLIANZ/MORUMBI).

## #048.10H.4 — GEO batch closure + fact-level evidence

**Status:** **DONE** · **GEO batch:** **4/4** · **Fact-level evidence:** **strong**
**Space preflight:** OK · **Snapshot:** read-only (nodes=5393, rels=4075, Fato=404)
**Worker run:** `36509850003` (success) · **cron:** `disabled_manually` antes/depois · **dispatches:** 1
**Dry-run 4/4:** true (`reports/geo_batch_closure_dry_run_048_10h_4.json`)

### Fatos GEO verificados (strong — Neo4j read-only)

```text
ALLIANZ PARQUE --LOCALIZADO_EM--> SÃO PAULO     (pt + en + nominatim)
MORUMBI --LOCALIZADO_EM--> SÃO PAULO            (pt + en + nominatim)
PACAEMBU --LOCALIZADO_EM--> SÃO PAULO           (pt + en + nominatim)
NEO QUÍMICA ARENA --LOCALIZADO_EM--> SÃO PAULO  (pt + en + nominatim)
```

### Métricas

| Métrica | Antes | Depois | Delta |
|---|---:|---:|---:|
| verified_facts_domain_independent | 13 | **15** | +2 |
| records_total | 13 | **15** | +2 |
| unique_predicates | 3 | 3 | 0 |
| fact_count | 404 | 404 | 0 |
| concept_count | 2009 | 2009 | 0 |
| facts_with_multi_domain | 16 | 16 | 0 |
| duplicate_cross_domain | 29 | 31 | +2 |
| unaccounted_raw | 0 | 0 | 0 |
| top_invalid_predicates | [] | [] | 0 |
| fallback_promoted_to_graph | 0 | 0 | 0 |
| graph_scoped_gap | -403 | -404 | (dívida #052.3.1) |

### Correções aplicadas

- `fix(cognition)`: alias `nubank parque -> ALLIANZ PARQUE` + exceção homônimo estado/cidade
  **strict source-scoped (só SÃO PAULO)** com `confidence<=0.85`.
- `fix(operational)`: retry limitado (2x, 5xx) no POST de ingest, **idempotente por MERGE** (teste).
- `feat(observability)`: `scripts/export_geo_fact_domains.py` (Neo4j **read-only**) +
  `validate_geo_expected_facts --fact-domains` → evidência **fact-level strong**.

### Classificação

**`SUCCESS_048_10H_4_GEO_BATCH_4_OF_4`** — lote GEO fechado com evidência forte.
Secundárias: `OBSERVABILITY_DEBT_GRAPH_SCOPED_GAP_NEGATIVE` (#052.3.1) ·
`TELEMETRY_DEBT_PUBLISHER_FAMILY_OSM_LIVE` (#053.2).

### Treino

`training_gate_evaluation`: `records_total=15`, `unique_predicates=3`, `diversity_gate=false`
(monoculture_object), `training_recommended=false`, `training_allowed=false`. **Treino não executado.**

> Este ciclo executou **1 worker** (autorizado), **não treinou**, **não escalou #048.10L**,
> **não alterou seeds do next batch**, **não fez force-push**.
> Próximo: **#048.10L** (runtime/seeds do next batch) — planejável, **não executado** aqui.

## #053.2 — Publisher-family telemetry for OpenStreetMap

**Status:** **PARTIAL** (`PARTIAL_053_2_LOCAL_READY_LIVE_PENDING`)
**Local `publisher_family_count`:** **3** · **Effective:** **3**
**Live `publisher_family_count`:** **ausente** (sem alteração de runtime/deploy)
**OpenStreetMap reconhecido:** **SIM** (local) · **Wikimedia colapsada:** **SIM** · **RSSSF warning:** **SIM**
**Deploy do Space:** **NÃO** (não houve mudança em `app.py`/`graph_connector.py`)
**Worker executado:** NÃO · **#048.10L:** congelado · **Treino:** bloqueado

- Helper read-only: `scripts/publisher_family_telemetry.py` (`classify_publisher_family`, `summarize_families`).
- `evaluate_training_gate.py`: famílias agora `{Wikimedia:30, OpenStreetMap:4, RSSSF:11}` +
  `effective_publisher_count=3` + `publisher_independence_warnings`.
- Dívida **#053.2.1**: expor `publisher_family_*` no `/api/metrics` vivo (runtime + redeploy seguro).
- Dívida **#052.3.1**: `graph_scoped_gap=-404` (separada).

> Este ciclo não executou worker; não escreveu em Neo4j/Qdrant via ingest; não alterou seeds/quórum;
> não treinou; não escalou #048.10L.

## #053.2.1 — Publisher-family telemetry viva

**Status:** **DONE** (`SUCCESS_053_2_1_LIVE_PUBLISHER_FAMILY_READY`)
**Local `publisher_family_count`:** 3 · **Live `publisher_family_count`:** **3**
**OpenStreetMap reconhecido vivo:** **SIM** · **Wikimedia colapsada vivo:** **SIM** · **RSSSF warning vivo:** **SIM**
**Deploy do Space:** **OK** (`sha 3aa1ad22 -> 8ff50d4d`, build `RUNNING`)
**Worker executado:** NÃO · **#048.10L:** congelado · **Treino:** bloqueado

- Helper compartilhado `src/ops/publisher_family.py`; `scripts/publisher_family_telemetry.py` delega a ele.
- `/api/metrics` vivo agora expõe `publisher_family_count=3`, `effective_publisher_count=3`,
  `publisher_family_distribution={OpenStreetMap:4, RSSSF:11, Wikimedia:31}` e `publisher_independence_warnings`
  — preservando todos os campos legados (`verified=15`, `fact_count=404`, `concept_count=2009`, `quorum=3`).
- `graph_connector.verified_fact_domain_counts()` (read-only) alimenta a telemetria; `metric_glossary` ganhou notas.
- Deploy via `scripts/deploy_hf_space_safe.py` (main: `58dab28`), venv isolado, 81 arquivos, sem segredos.
- Dívida **#052.3.1** (`graph_scoped_gap=-404`) permanece separada.

> Este ciclo não executou worker; não escreveu em Neo4j/Qdrant via ingest; não alterou seeds/quórum;
> não treinou; não escalou #048.10L.

## #052.3.1 — Fact accounting / graph_scoped_gap correction

**Status:** **DONE** (`SUCCESS_052_3_1_GRAPH_ACCOUNTING_READY`)
**Causa raiz:** `graph_snapshot()` omitia `distinct_fact_hashes` no retorno → `.get(...,0)=0` → gap falso `-404`.
**Helper criado:** SIM (`src/ops/fact_accounting.py`) · **Graph connector read-only:** SIM
(`get_fact_accounting_counts`) · **App metrics:** SIM (campos aditivos + nova fórmula)
**Deploy do Space:** **OK** (`sha 8ff50d4d -> 79413cf2`, build `RUNNING`)
**Live `graph_scoped_gap`:** **0** · **`distinct_fact_node_keys`:** 404 · **`missing_fact_hash_count`:** 0 ·
**`duplicate_fact_hash_group_count`:** 0 · **`fact_accounting_status`:** **ok**
**Worker executado:** NÃO · **Backfill:** NÃO · **#048.10L:** congelado · **Treino:** bloqueado

- Nova fórmula: `graph_scoped_gap = distinct_fact_node_keys - persisted_facts` (usa `f.chave`, fallback `id(f)` só p/ contagem).
- Campos vivos adicionais: `distinct_non_null_fact_hashes`, `missing_fact_hash_count`, `distinct_fact_node_keys`,
  `duplicate_fact_hash_group_count`, `fact_accounting_status` — **sem** alterar verificação/quórum/fact_count/concept_count.
- Métricas cognitivas estáveis: `verified=15`, `quorum=3`, `fact_count=404`, `concept_count=2009`,
  `publisher_family_count=3`, `run_scoped_gap=0`, `unaccounted_raw=0`, `top_invalid_predicates=[]`, `fallback=0`.

> Este ciclo não executou worker; não escreveu em Neo4j/Qdrant via ingest; **não fez backfill**;
> não alterou seeds/quórum; não treinou; não escalou #048.10L.

## #048.10L — Next batch GEO controlled implementation (dry-run, sem worker)

**Status:** **DONE (dry-run)** · **Classificação:** **`SUCCESS_048_10L_NEXT_BATCH_READY_FOR_WORKER`**
**Worker executado:** NÃO · **Deploy do Space:** NÃO · **Neo4j/Qdrant write:** NÃO · **Treino:** bloqueado
**Dry-run 5/5:** true (`reports/geo_next_batch_implementation_dry_run_048_10L.json`):
`osm=5`, `wiki_pt=5`, `wiki_en=5`, `wiki_infobox=5`, `full_collision=5`, `canonical_key_mismatches=0`,
`junk=0`, `forbidden=0`, `negatives 10/10 rejeitadas`, **regressão lote atual 4/4**.
**Pronto para #048.10L.2:** true (`reports/RUNBOOK_048_10L_2_GEO_NEXT_BATCH_WORKER.md`)

Lote implementado (pt + en + Nominatim/ODbL; registry `reports/geo_expected_facts_048_10L.json`):

```text
ESTÁDIO OLÍMPICO NILTON SANTOS --LOCALIZADO_EM--> RIO DE JANEIRO
MARACANÃ --LOCALIZADO_EM--> RIO DE JANEIRO
BEIRA-RIO --LOCALIZADO_EM--> PORTO ALEGRE
MINEIRÃO --LOCALIZADO_EM--> BELO HORIZONTE
ARENA FONTE NOVA --LOCALIZADO_EM--> SALVADOR
```

### Mudanças (controladas)
- `feat(cognition)`: `geo_wiki_parser` generalizado — `ALLOWED_CITIES` + aliases para as 5 cidades,
  subject pin por URL das 5 páginas, cues `localizado no/na` e rejeição de `estado/state`/`club`/`home of`
  em qualquer posição.
- `feat(cognition)`: `geo_extractor` — aliases dos 5 estádios, cidade `SALVADOR`, exceção homônima
  `RIO DE JANEIRO` **strict source-scoped** (`{country: BR, state: RIO DE JANEIRO}`), sem generalizar a regra.
- `feat(config)`: 5 clusters `*_localization` em `config/seed_clusters.yaml` (3 domínios, 2 publishers,
  1 não-Wikipedia, `productivity: productive`).
- `feat(tests)`: `tests/test_geo_next_batch_implementation.py` + fixtures
  `tests/fixtures/geo_next_batch_parity_cases.json` (5 positivos, 10 negativos).
- `feat(reports)`: dry-run `scripts/audit_geo_next_batch_implementation_dry_run.py` +
  `reports/geo_expected_facts_048_10L.json`.

### Invariantes preservadas
- Worker **não** executado; **sem** ingest em Neo4j/Qdrant; **sem** backfill; **sem** deploy.
- **Não alterou** `span_validator`/`predicate_mapper`/`canonicalizer`/`triple_refiner`/`table_extractor`/
  `entity_aliases.yaml`/workflows/requirements; quórum **3**; lote atual (`reports/geo_expected_facts_048_10H.json`) intacto.
- Suíte completa: **638 passed, 39 skipped**; `ruff check` limpo nos arquivos alterados.

> Próximo: **#048.10L.2** — worker GEO do next batch (snapshot/baseline/worker/post/validate,
> 1 dispatch, cron `disabled_manually`). Não treinar; quórum 3.

## #048.10L.2 — Worker GEO do next batch

**Status:** **PARTIAL** · **Classificação:** **`PARTIAL_048_10L_2_GEO_PROGRESS`**
**Space preflight:** OK (200, online, telemetria viva) · **Vercel:** non-required (429 rate-limit) · **GitHub status HEAD:** success
**Snapshot:** OK (`scripts/aura_snapshot.py`, read-only; nodes=5425, rels=4080, Fato=404)
**Worker run:** `36617910895` (success, 4m45s) · **cron:** `disabled_manually` antes/depois · **dispatches:** 1
**Fact-level evidence:** **inferred** (3/5 com ≥3 domínios) · **Junk:** 0 · **Regressão lote atual:** false
**Campo `LOCALIZADO_EM` fortes:** NILTON SANTOS→RJ · MARACANÃ→RJ · ARENA FONTE NOVA→SALVADOR
**Parciais:** BEIRA-RIO→PORTO ALEGRE (2/3) · MINEIRÃO→BELO HORIZONTE (1/3) → `reports/geo_next_batch_real_failure_analysis_048_10L_2.md`
**Treino:** bloqueado · **Next-next batch:** congelado

| Métrica | Antes | Depois | Delta |
|---|---:|---:|---:|
| verified_facts_domain_independent | 15 | **18** | +3 |
| records_total | 15 | **18** | +3 |
| fact_count | 404 | **413** | +9 |
| concept_count | 2009 | **2023** | +14 |
| unique_predicates | 3 | 3 | 0 |
| non_VENCEU_ratio | ~0.33 | **0.4444** | + |
| top_predicate_share | ~0.67 | **0.5556** | - |
| publisher_family_count | 3 | 3 | 0 |
| graph_scoped_gap | 0 | 0 | 0 |
| fact_accounting_status | ok | ok | 0 |
| unaccounted_raw | 0 | 0 | 0 |
| top_invalid_predicates | [] | [] | 0 |
| fallback_promoted_to_graph | 0 | 0 | 0 |

### Causas reais (2 fatos parciais)

- **Wiring OSM:** `scripts/worker_cycle.py::_load_expected_geo_city()` usa cidade única do registry 048_10H
  (SÃO PAULO) como fallback de todo o run → `no_clean_city_evidence` para POA/BH.
- **Infobox HTML cru:** worker chama `parser(url, "", html)`; na página PT do Mineirão a janela do infobox
  capturou "Rio de Janeiro" (objeto falso, unverified).
- **Canonical mismatch:** grafo canoniza `BEIRA RIO` (hífen→espaço) vs registry `BEIRA-RIO`.

### Correções aplicadas (mínimas, testadas)

- `feat(reports)`: `scripts/export_geo_fact_domains.py` agora aceita `--expected` e `--audit-id` e popula
  `publisher_families` (usado para o registry do next batch). Teste estendido em `tests/test_export_geo_fact_domains.py`.
- **Não houve hotfix de parser/extractor nem retry de worker** (worker não falhou; desfecho mapeia para #048.10L.3).

> Este ciclo executou **1 worker** (autorizado), **não treinou**, **não escalou next-next batch**,
> **não baixou quórum**, **não alterou validators cognitivos centrais**, **não fez force-push**.
> **Não** houve restore/backfill. Próximo: **#048.10L.3** (fallback OSM source-scoped por fato + endurecer
> infobox HTML cru + alinhar chave `BEIRA RIO`/`BEIRA-RIO`), apenas com dry-run e autorização.

## #048.10L.3 — Fechamento seguro do next batch GEO + higiene observacional

**Status:** **DONE** · **Classificação:** **`SUCCESS_048_10L_3_NEXT_BATCH_DRY_RUN_5_OF_5_READY_FOR_WORKER`**
**Space preflight:** OK (200, online) · **Vercel:** non-required · **GitHub status HEAD:** success
**Worker executado:** NÃO · **Neo4j/Qdrant write:** NÃO · **Backfill:** NÃO · **Treino:** NÃO
**Dry-run 5/5:** true (`reports/geo_next_batch_closure_dry_run_048_10l_3.json`) · **Pronto para #048.10L.4:** true

### Causas e correções
- **Causa Beira-Rio:** `expected_city` fixo em SÃO PAULO (`worker_cycle`) → fallback OSM bloqueado (B1+B2) + mismatch `BEIRA RIO`/`BEIRA-RIO` (B4).
- **Causa Mineirão:** infobox de HTML cru capturou "Rio de Janeiro" (B3) + mesmo wiring (B1/B2).
- **expected city wiring corrigido:** SIM (`resolve_expected_geo_city` por URL; wiki por subject pinado, Nominatim por `q`).
- **OSM fallback source-scoped corrigido:** SIM (só a cidade esperada; rejeita conflito/estado/road/`address.city` divergente).
- **Infobox hardening:** SIM (`expected_city` no parser wiki; labels/tokens proibidos; cross-city rejeitado).
- **BEIRA-RIO normalization:** SIM (alias `beira rio`→`BEIRA-RIO` + teste hífen×espaço).
- **Audit stale corrigido:** SIM (`audit_geo_worker_dry_run` → contrato 3-vias; `gate_passed=true`).
- **canonical_to_fact_gap:** `SCOPE_MISMATCH` documentado como **não bloqueante** (`reports/canonical_to_fact_gap_diagnosis_048_10l_3.md`); sem escrita/backfill.
- **Validação offline (`..._048_10l_3_offline.json`):** `not_applicable_live` — reflete o grafo **pré-fix** (3/5, mesmos parciais do #048.10L.2). A prontidão é provada pelo **closure dry-run 5/5** (offline, fixtures+registry).

> Este ciclo **não executou worker**, **não escreveu em Neo4j/Qdrant**, **não fez backfill**, **não alterou
> quórum**, **não alterou validators cognitivos centrais** (span/predicate/canonicalizer/refiner/table/entity_aliases),
> **não escalou next-next batch**, **não treinou**, **não fez force-push**. O lote atual GEO **permanece intacto**.
> Próximo: **#048.10L.4** (worker GEO do next batch, retry condicionado) via `reports/RUNBOOK_048_10L_4_GEO_NEXT_BATCH_WORKER_RETRY.md`.

## #048.10L.4 — Worker GEO do next batch retry

**Status:** **DONE** · **Classificação:** **`SUCCESS_048_10L_4_GEO_NEXT_BATCH_5_OF_5`**
**Space preflight:** OK · **Redeploy necessário:** SIM (app.py mudou em L.3) · **Redeploy executado:** SIM (sha `d59e8957`, RUNNING)
**Snapshot:** OK (nodes=5470, rels=4137, Fato=413) · **Worker run:** `36653154613` (dispatch #1) + `36654148767` (retry #2) · **cron:** `disabled_manually` antes/depois
**Fact-level evidence:** **strong** · **Next batch GEO:** **5/5** · **Junk:** 0 · **Forbidden:** 0 · **Regressão lote atual:** false
**Treino:** bloqueado · **Next-next batch:** congelado

| Métrica | Antes | Depois | Delta |
|---|---:|---:|---:|
| verified_facts_domain_independent | 18 | **20** | +2 |
| records_total | 18 | **20** | +2 |
| fact_count | 413 | 413 | 0 (fatos já existiam; +domínios) |
| concept_count | 2023 | 2023 | 0 |
| unique_predicates | 3 | 3 | 0 |
| non_VENCEU_ratio | ~0.44 | **0.50** | + |
| top_predicate_share | ~0.56 | **0.50** | - |
| publisher_family_count | 3 | 3 | 0 |
| graph_scoped_gap | 0 | 0 | 0 |
| fact_accounting_status | ok | ok | 0 |
| canonical_to_fact_gap | scope_mismatch_non_blocking | -93 | (não bloqueante) |
| unaccounted_raw | 0 | 0 | 0 |
| top_invalid_predicates | [] | [] | 0 |
| fallback_promoted_to_graph | 0 | 0 | 0 |

Fatos do next batch verificados (pt+en+nominatim, strong):
`NILTON SANTOS→RIO DE JANEIRO` · `MARACANÃ→RIO DE JANEIRO` · `BEIRA-RIO→PORTO ALEGRE` · `MINEIRÃO→BELO HORIZONTE` · `ARENA FONTE NOVA→SALVADOR`.

### Hotfix mínimo aplicado (evidência do probe read-only)
- `fix(cognition)` `5435220`: infobox PT do Mineirão usa label **"Município"** (não casado) → adicionado
  `município/municipio/localidade`; **duas queries Nominatim desambiguadas por cidade**
  (`Estádio Beira-Rio, Porto Alegre` e `Mineirão, Belo Horizonte`) — sem elas, o Nominatim retornava
  features erradas em MG (probe `.autonomous/048_10l_4/real_page_probe/`).
- `fix(operational)` `24c8ff6`: casamento de chave tolerante a hífen/espaço (`BEIRA RIO` == `BEIRA-RIO`) no export/validate.
- Retry único autorizado (dispatch #2) após CI verde.

> Este ciclo executou **2 workers** (1 + 1 retry com diagnóstico), **não treinou**, **não escalou next-next batch**,
> **não baixou quórum**, **não alterou validators cognitivos centrais** (canonicalizer/predicate_mapper/span_validator/
> triple_refiner/table_extractor/entity_aliases intactos), **não fez force-push**, **sem backfill/restore**.
> Treino segue **fechado** (`records_total=20 < 50`, `environment_gate=false`), apesar de `diversity_ok=true`.
> Residual: `MINEIRAO --LOCALIZADO_EM--> RIO DE JANEIRO` (legado de L.2, **unverified**, dc=1, não promovido) —
> ver `reports/geo_next_batch_residual_048_10L_4.md`; limpeza em #048.10L.5.
> Próximo: **#048.10M** (planejamento read-only de expansão não-VENCEU / DEFENDEU-DISPUTOU). Não treinar.

## #048.10L.5 — Residual GEO hygiene + canonical accounting scope

**Status:** **DONE** · **Classificação:** **`SUCCESS_048_10L_5_RESIDUAL_HYGIENE_AND_ACCOUNTING_READY`**
**Worker executado:** NÃO · **/api/ingest:** NÃO · **Treino:** NÃO · **Qdrant:** não tocado
**Space preflight:** OK · **Deploy do Space:** OK (sha `08bcd7b6`, RUNNING)
**Resíduo `MINEIRAO->RIO DE JANEIRO`:** **removido** (1 `:Fato` unverified, sob snapshot+dry-run)
**Verified após higiene:** **20** · **fact_count:** 413 → **412** · **graph_scoped_gap:** 0 · **fact_accounting_status:** ok
**canonical_to_fact_gap:** -412 (`scope_mismatch_non_blocking`, explicitado na telemetria)
**Next-next batch:** congelado

### Higiene (estrita)
- Inventário read-only: `scripts/audit_geo_residual_hygiene.py` → `reports/geo_residual_hygiene_048_10l_5.json`
  (11 resíduos unverified; alvo `MINEIRAO->RIO` com `safe_to_remove=true`).
- Prevenção de recriação provada: `tests/test_geo_residual_prevention.py` (infobox/sentença Rio → rejeitado com expected `BELO HORIZONTE`).
- Snapshot imediato: `.autonomous/048_10l_5/aura_snapshot_pre_hygiene.json` (nodes=5790, rels=4145, Fato=413).
- Dry-run + execute: `scripts/hygiene_geo_residual_048_10l_5.py` (`deleted=1`, `still_present=false`).
- Pós-delete: verified **20** preservado, lote atual 4/4 e next batch 5/5 intactos, zero perda.

### Contabilidade (aditiva, read-only)
- `app.py`: campos novos em `ingestion_accounting` — `canonical_to_fact_gap_status`,
  `canonical_to_fact_gap_interpretation`, `canonical_to_fact_gap_same_scope`,
  `canonical_occurrences_count`, `persisted_fact_nodes_count` + `metric_glossary`.

> Este ciclo **não executou worker**, **não chamou /api/ingest**, **não treinou**, **não alterou quórum/validators
> cognitivos centrais**, **não escalou next-next batch**, **não fez force-push**, **não tocou Qdrant**, **sem backfill**.
> A única escrita em Neo4j foi a remoção escopada de **1** `:Fato` unverified, sob snapshot+dry-run.
> Próximo: **#048.10M** (planejamento read-only) via `reports/RUNBOOK_048_10M_EXPANSION_PLANNING.md`. Treino fechado.

## #048.10M — Planejamento read-only de expansão não-VENCEU

**Status:** **DONE** · **Classificação:** **`SUCCESS_048_10M_READ_ONLY_EXPANSION_PLAN_READY`**
**Worker executado:** NÃO · **Seeds ativadas:** NÃO · **Treino:** NÃO · **Escrita Neo4j/Qdrant:** NÃO · **/api/ingest:** NÃO · **Deploy:** NÃO
**CI:** required checks verdes neste push (Quality & Security Gate)

### Inventário read-only (20 fatos verificados)
- `facts_by_predicate`: `VENCEU=10`, `LOCALIZADO_EM=9`, `DEFENDEU=1`.
- `facts_by_publisher_family`: `Wikimedia=40`, `RSSSF=11`, `OpenStreetMap=9`.
- `non_VENCEU_ratio=0.50`, `top_predicate_share=0.50`, `publisher_family_count=3`.
- `reports/expansion_fact_inventory_048_10m.json`

### DEFENDEU candidates
- **Atlas:** `reports/expansion_defendeu_atlas_048_10m.json` — **12 candidatos** (7 low / 5 medium), todos `candidate_unverified`, `eligible_for_future_worker=false` (exigem dry-run próprio).
- **Suportado agora:** SIM (`predicate_mapper` + target-aware extractor #048.10B + club-context #059C).
- **DISPUTOU supported:** **NÃO** (mapeado, mas **sem frame de extração**).
- **POSSUIR supported:** **NÃO** (alto risco semântico de posse genérica).
- `BLOCKED_048_10M_REQUIRES_GLOBAL_ONTOLOGY_CHANGE` registrado para DISPUTOU/POSSUIR (sem alterar ontologia).

### Política de fontes / risco / plano
- `reports/expansion_source_policy_048_10m.md` (+ `scripts/audit_expansion_source_policy_048_10m.py` testável).
- `reports/expansion_risk_matrix_048_10m.json` · `reports/expansion_batch_plan_048_10m.md`.
- **Próximo batch recomendado:** **#048.10M.1** (DEFENDEU piloto, 6–10 low-risk) via
  `reports/RUNBOOK_048_10M_1_DEFENDEU_BATCH.md`; `reports/RUNBOOK_048_10M_2_FUTURE_BATCH.md`.

> Este ciclo **não executou worker**, **não chamou /api/ingest**, **não escreveu em Neo4j/Qdrant**,
> **não ativou seeds**, **não treinou**, **não alterou quórum/validators centrais**, **não fez force-push**.
> Apenas planejou expansão futura com evidência read-only. Treino segue **fechado** (`records_total=20<50`, `environment_gate=false`).

---

## #054.1 — Rate limiter hardening seguro

**Status:** DONE (deployado e validado ao vivo) · **Data:** 2026-09-30
**Commits:** `82aa3cc` (código+testes) · `4f40775` (docs API) · `5b3e8b4` (docs contagem)
**CI:** success nos 3 pushes (`Quality & Security Gate`)
**Space deploy:** OK — `scripts/deploy_hf_space_safe.py` dry-run + upload único (82 arquivos);
Space `RUNNING` @ `7ebdcec` (antes `08bcd7b6...`)
**Live publisher/cognitive state:** preservado (ALL_CRITERIA_OK — ver abaixo)

### O que mudou
- `src/security/rate_limiter.py`: sliding window por **identidade opaca**
  (`ip:<host>` / `token:<sha256-prefixo>`), `check() → RateLimitDecision`
  com **Retry-After** (ceil do oldest na janela, mín. 1s), **memória bounded**
  (`max_keys=10k`: purge de expiradas no teto + despejo LRU por último hit),
  `fingerprint_secret()` não-reversível.
- `app.py`: limites diferenciados — chat 5/min por IP; extract **balde duplo**
  (10/min anônimo por IP, 120/min por token); simulate 10/min por IP;
  ingest **120/min por token**. Todos os 429 com header `Retry-After`.
- Calibração pelo worker legítimo (#054.1): o worker posta extract+ingest em
  rajada sem delay (~60/min estrutural pior-caso, retry não cobre 429) —
  margem 2x adotada. Evidência: `reports/rate_limiter_worker_compatibility_054_1.md`.
- Testes: `tests/test_rate_limiter.py` (bound/purge/LRU/fingerprint/caplog),
  `tests/test_ingest_rate_limit.py` (novo), `tests/test_extract_simulate_rate_limit.py`
  (novo). Suíte: **721 passed / 20 skipped**.
- Docs: API/PRD/ARCHITECTURE/SECURITY_REVIEW/COMPLIANCE/PERFORMANCE/
  ERROR_HANDLING/QA_TESTING + correção de contagens stale de testes.

### Validação viva (pré/pós-deploy)
```text
ANTES : verified=20 fact=412 concept=2023 quorum=3 graph_scoped_gap=0 accounting=ok
DEPOIS: verified=20 fact=412 concept=2023 quorum=3 graph_scoped_gap=0 accounting=ok
        hebbian_consistency_check=True  top_invalid=[]  fallback_promoted=0
```
- Primeira leitura pós-deploy pegou o grafo frio (AuraDB hibernado; corrida de
  boot) — `hebbian_consistency_check=false`, counters 0. Recuperou sozinho na
  re-poll em 20s (comportamento durável esperado, DR-1). Nenhuma perda.

### Declarações de invariante
```text
Este ciclo não executou worker.
Este ciclo não chamou /api/ingest ao vivo.
Este ciclo não escreveu em Neo4j/Qdrant.
Este ciclo não ativou seeds.  Este ciclo não treinou.
Este ciclo não alterou quórum, validators centrais, requirements ou workflows.
Este ciclo não fez force-push nem git add -A.
Artefatos .autonomous/ e reports/*.json não relacionados ficaram unstaged.
```

**Próximo passo liberado:** `#048.10M.1 — DEFENDEU pilot dry-run, sem worker`.

---

## #048.10M.1 — DEFENDEU pilot dry-run e worker readiness

**Status:** DONE (`SUCCESS_048_10M_1_DEFENDEU_PILOT_DRY_RUN_READY_FOR_WORKER`) · **Data:** 2026-10-01
**Commits:** feat(planning) seletor+probes · feat(planning) dry-run+risk matrix · docs(planning) runbook+SPRINT
**CI:** success · **Space preflight:** OK (verified=20, fact=412, concept=2023, hebbian=True, gaps=0 — warm-up 1ª tentativa)
**Worker executado:** NÃO · **Seeds ativadas:** NÃO · **Treino:** NÃO · **Escrita em Neo4j/Qdrant:** NÃO

### O que foi feito
- **Seletor determinístico** (`scripts/select_defendeu_pilot_candidates_048_10m_1.py`):
  12 candidatos do atlas → **7 selecionados** (6 low + 1 medium Ceni) + **5 excluídos
  com causa** — destaque: **Rivelino→Flamengo excluído por evidência** (probe 0/2
  nas páginas canônicas 200 OK sem menção ao objeto — possível erro fático no
  atlas; Cenário E, atlas não corrigido).
- **Probes read-only orçados** (`scripts/probe_defendue_candidates_readonly_048_10m_1.py`):
  26/45 requests (pt 8, en 8, rsssfbrasil 8+descoberta), delay 2s, timeout 15s,
  sem retry em 403/429, UA fixo, só domínios permitidos, resumo sanitizado.
- **Limitação honesta:** RSSSF não confirmado por probe (paths 404 + raiz sem
  índice parseável) → 3º domínio permanece plausível pela política do atlas;
  todos os candidatos com LOCAL_EXISTING_EVIDENCE (atlas + fatos unverified no
  grafo + fixtures de extração).
- **Registry de expected facts** (`reports/defendeu_pilot_expected_facts_048_10m_1.json`):
  7 fatos esperados `SUBJECT --DEFENDEU--> OBJECT`, min_domain_count=3,
  status `planned_not_active` (não injeta nada no grafo).
- **Dry-run offline** (`scripts/audit_defendeu_pilot_dry_run_048_10m_1.py`):
  full_collision 7/7, junk=0, forbidden=0, regressões=false, source_policy_
  violations=0, ontology_changes=0 → **ready_for_worker=true** (gate rígido).
- **Matriz de risco** + **runbook futuro** (`RUNBOOK_048_10M_1_2_DEFENDEU_PILOT_WORKER.md`)
  com 21 pré-condições e expectativa conservadora verified 20→26-30.
- **Testes:** 26 novos (seletor/dry-run/probe, todos offline com fixtures);
  suíte completa **747 passed / 20 skipped**; ruff limpo nos arquivos novos
  (venv isolado).

### Declarações de invariante
```text
Este ciclo não executou worker.  Este ciclo não chamou /api/ingest ao vivo.
Este ciclo não escreveu em Neo4j/Qdrant.  Este ciclo não ativou seeds.
Este ciclo não treinou.  Este ciclo não alterou quórum nem validators centrais.
Este ciclo não alterou rate limiter nem requirements/workflows.
Este ciclo apenas preparou o piloto DEFENDEU com evidência read-only.
```

**Próximo passo:** revisão do Operador; se aprovado, `#048.10M.1_2 — worker
DEFENDEU piloto` (único, com snapshot/baseline/pós/fact-level validation).
Dívidas: probes RSSSF alternativos, #054.2, #054.3, #054.4.

---

## #048.10M.1.2 — DEFENDEU pilot worker

**Status:** BLOCKED (`BLOCKED_048_10M_1_2_WORKER_FAILED` — fact-level FAIL 0/7) · **Data:** 2026-10-03
**Commits:** feat(pilot) worker único + validação fact-level + relatórios · **CI:** (verificar no push)
**Snapshot AuraDB:** SIM (`defendeu_pilot_worker_aurasnapshot_048_10m_1_2.json`, 5789 nós/4144 rels, restore NÃO)
**Worker executado:** UMA VEZ (`worker_cycle.py`, 72 fontes 200 OK, consolidação 200)
**Fact-level validation:** 0/7 (Garrincha presente c/ 2 domínios não-verificado; Jairzinho c/ 1 domínio não-Wikimedia não-verificado; 5 ausentes do grafo)
**Junk objects:** 0 · **Forbidden objects:** 0 · **Source policy violations:** 0 · **Regressões:** nenhuma (verified=20 preservado; fact 412→598; concept 2023→2136; gsg=0; fas=ok; ss=0; unacc=0; hebbian=True)
**Treino:** NÃO · **Seeds ativadas:** NÃO · **Deploy:** NÃO · **Contaminação cross-project:** 0

### Causa raiz (incidente `defendeu_pilot_worker_incident_048_10m_1_2.md`)
Seeds do worker miram clubes/GEO/IA — as páginas dos 7 jogadores não são mineradas
(5/7 nem chegaram ao grafo) e quórum 3 não fecha em ciclo único (corroboração é
cumulativa entre ciclos). Garrincha +2 domínios e Jairzinho +1 não-Wikimedia (RSSSF
corroborou de fato neste ciclo, ao contrário do probe T160-era).

### Opções devolvidas ao Operador
1. Novo GO para adicionar páginas dos 7 jogadores às seeds (altera seed_clusters.yaml — proibido neste ciclo).
2. Aceitar acumulação natural multi-ciclo com seeds atuais (RSSSF de jogadores não está nas seeds).
3. Reavaliar o critério do piloto (quórum em ciclo único era irrealista para candidatos fora do escopo de seeds).

### Declarações de invariante
Este ciclo executou worker piloto DEFENDEU uma única vez. Não executou treino.
Não ativou seeds. Não alterou quórum. Não alterou cognição central. Não usou
projeto paralelo como evidência. Não restaurou snapshot automaticamente.

### #048.10M.1.2.R1 — Diagnóstico read-only concluído (2026-10-03)
`SUCCESS_048_10M_1_2_R1_ROOT_CAUSE_AND_CRITERIA_PACKET_READY`. Sem worker, sem seeds,
sem escrita em grafo, sem treino, sem deploy. Evidência: `reports/defendeu_r1_graph_state_048_10m_1_2.json`
(read-only, Neo4j vivo) + packet `reports/defendeu_r1_decision_packet_048_10m_1_2.md` (15 perguntas
respondidas · CV por candidato · recomendação A+C). Estado do grafo re-verificado: Garrincha 2/3,
Jairzinho 1/3 (persistentes), 5 ausentes, zero mutação desde o incidente. Aguardando decisão do
Operador (A+C recomendado: critério multi-ciclo + lotes direcionados, lote 1 = Garrincha gate G1).

### #048.10M.1.2.R2 — Garrincha G1 read-only readiness (2026-10-03)

**Status:** PARTIAL
**Commits:** (ver log)
**CI:** (verificar pós-push)
**Worker executado:** NÃO
**Ingest executado:** NÃO
**Escrita em Neo4j/Qdrant:** NÃO
**Seeds alteradas:** NÃO
**Aliases alteradas:** NÃO
**Cognição central alterada:** NÃO
**Treino:** NÃO
**Deploy:** NÃO
**Garrincha estado atual:** fato canônico presente (elementId 4:3b5e8459-...:3749), não verificado, spans limpos, homonímia baixa
**Domínios já confirmados:** pt.wikipedia.org + en.wikipedia.org (2/3, mesma tripla)
**Domínio não-Wikimedia plausível:** NÃO confirmado neste ciclo — probe budget 6/6 esgotado em caminhos 404; caminhos REAIS do piloto (brazchamp/copalib/jogclub) documentados no PARTIAL para probe futuro
**Ready for future G1:** false
**Contaminação cross-project:** 0

### #048.10M.1.2.R3 — Garrincha surgical read-only probe (2026-10-03)

**Status:** PARTIAL
**Commits:** (ver log)
**CI:** (verificar pós-push)
**Worker executado:** NÃO
**Ingest executado:** NÃO
**Escrita em Neo4j/Qdrant:** NÃO
**Seeds alteradas:** NÃO
**Aliases alteradas:** NÃO
**Cognição central alterada:** NÃO
**Treino:** NÃO
**Deploy:** NÃO
**Probe HTTP:** 3 requisições (jogclub/brazchamp/copalib — ordem do task)
**Domínio não-Wikimedia confirmado:** NÃO — os 3 caminhos corretos responderam 200 OK e NENHUM menciona Garrincha/Manuel Francisco (o jogador está ausente das fontes tabulares permitidas alcançáveis)
**Ready for future G1:** false
**Runbook G1 criado:** false (bloqueado por ready=false)
**Contaminação cross-project:** 0

---

## #048.10M.1.2.R4 — DEFENDEU source/seed viability read-only

**Status:** DONE (`SUCCESS_048_10M_1_2_R4_DEFENDEU_VIABILITY_PACKET_READY`) · **Data:** 2026-10-03
**HTTP externo:** NÃO · **Worker:** NÃO · **Ingest:** NÃO · **Escrita em grafo:** NÃO · **Seeds/aliases/núcleo:** NÃO alterados · **Treino/Deploy:** NÃO

### Diagnóstico central
Os 7 candidatos DEFENDEU estão **estruturalmente bloqueados por cobertura de seeds**:
nenhum possui página de jogador nas seeds do worker (apenas Garrincha tem a própria).
Resultado do worker #048.10M.1.2: 0/7 verificados, +186 fatos não-verificados
acumulados (fact 412→598; concept 2023→2136), zero junk/forbidden/regressão.
- Garrincha: 2/3, **FREEZE** (probe R3 provou 3 páginas rsssf sem menção)
- Jairzinho: 1/3 com não-Wikimedia (rsssfbrasil corroborou no worker)
- Zito/Sócrates/Romário/CAT/Ceni: 0 domínios (páginas de jogador fora das seeds)

### Artefatos (commitados)
- `reports/defendeu_r4_graph_candidates_048_10m_1_2.json` (script MATCH/RETURN read-only)
- `reports/defendeu_r4_source_matrix_048_10m_1_2.json` (baldes: confirmado/probe-200-sem-menção/404/só-reports/bloqueado/proibido)
- `reports/defendeu_r4_seed_extension_design_048_10m_1_2.md` (NÃO APLICADO)
- `reports/defendeu_r4_decision_packet_048_10m_1_2.md` (5 opções)
- testes offline: 18 (3 arquivos) · suíte total **798 passed / 20 skipped**

### Opções devolvidas ao Operador
A) Congelar DEFENDEU · B) R5 probes cirúrgicos com URLs de origem governada (≤3/candidato) ·
C) Seed extension governada (design pronto, não aplicado) · D) Reduzir piloto (não resolve) ·
**E) Pivotar para #054.2 primeiro (recomendada)** — boot-race recorrente (R3) e confiabilidade
de sinal antes de qualquer expansão.

### Declarações de invariante
Este ciclo não fez requisição HTTP externa. Não executou worker. Não chamou /api/ingest.
Não escreveu em Neo4j/Qdrant. Não ativou seeds. Não alterou aliases nem cognição central.
Não treinou. Não deployou. Apenas produziu diagnóstico read-only e packet de decisão.

---

## Reestruturação — monorepo `apps/api` + `apps/web` (2026-10-03)

**Status:** DONE · **Commits:** chore(repo) split + docs · **CI:** (verificar no push)

### O que mudou
- **`apps/api/`**: `app.py`, `src/` (Python), `config/`, `tests/`, `scripts/`, `dashboard/`,
  `requirements*.txt`, `Dockerfile`, `Dockerfile.hf`, `README_HF.md`, `.env.example`, `reports/`, `data/`.
- **`apps/web/`**: `package.json`, `package-lock.json`, `next.config.js`, `tsconfig.json`,
  `tailwind.config.ts`, `postcss.config.js`, `vercel.json`, `public/`, `src/app/` (App Router
  + proxy `/api/nexus` + policy), `src/frontend/` (componentes), `Dockerfile.web`.
- `mock_server.py` movido de `src/frontend/` → `apps/api/scripts/` (intruso Python no frontend).
- `docker-compose.yml`: `nexus-core` (context `apps/api`) + **novo `nexus-web`** (`Dockerfile.web`) + neo4j.
- Workflows: `ai-validation.yml` (pytest de `apps/api` com PYTHONPATH próprio; anti-leak em
  `apps/api/src`; `node --test` de `apps/web`) e `ai-cron.yml` (worker de `apps/api`).
- Raiz limpa: sem `.venv`/`node_modules`/`.next` compartilhados; venv novo = `apps/api/.venv`.
- `.env` do backend → `apps/api/.env` (local); `.env.local` do proxy → `apps/web/.env.local` (local).

### Validação
pytest: **798 passed / 20 skipped** a partir de `apps/api` E da raiz (via `conftest.py`);
`tsc --noEmit` e `node --test` policy: verdes de `apps/web`; `docker compose config`: OK.

### Ação do Operador (Vercel)
Project Settings → **Root Directory = `apps/web`** (o site segue no último deploy bom até lá).

### Declarações
Nenhum comportamento de aplicação alterado — apenas layout físico + referências de
build/CI. Todos os imports `from src.x` preservados (PYTHONPATH/CWD = apps/api).

---

## #054.2.R1 — Space boot graph readiness: root-cause read-only

**Status:** DONE (`SUCCESS_054_2_R1_BOOT_READINESS_ROOT_CAUSE_AND_PATCH_PLAN_READY`) · **Data:** 2026-10-03
**Runtime alterado:** NÃO · **Worker/Ingest/Escrita em grafo:** NÃO · **Deploy:** NÃO · **Treino:** NÃO
**Boot-race reproduzido:** SIM (sampler dedicado — amostra 1 zeros/hebbian=False → amostra 2 baseline, 15s)

### Root cause (confirmada por código + reprodução)
AuraDB free **pausa por inatividade** → no wake-up, a 1ª `session.run` falha transitória →
`graph_snapshot` engole (2 retries de 0,5s — curto p/ wake-up de dezenas de segundos) →
`/api/metrics` serve **zeros + hebbian=False com HTTP 200** → consumidor interpreta como
drift. **Nenhum estado inconsistente real** — janela transitória sem gate de readiness
(`/health` estático; payload sem flag de boot).

### Artefatos
`reports/054_2_r1_boot_sequence_map.md` · `054_2_r1_log_evidence.md` · `054_2_r1_root_cause_hypotheses.md`
· `054_2_r1_readiness_patch_options.md` · `054_2_r1_test_plan.md` · `054_2_r1_decision_packet.md`
· `scripts/diagnose_054_2_r1_boot_readiness.py` + 11 testes offline (classify/summarize/budget/D11).

### Opções propostas (NÃO implementadas)
R1 `/api/ready` · **R2 `graph_ready` aditivo em /api/metrics (recomendada)** · R3 warm-up interno ·
R4 cliente com backoff (padrão já informal) · R5 cache stale (rejeitada). Recomendação:
**R2 + R4 formalizado** num único task futuro `#054.2.R2`, com PR, testes T1-T6, CI, sem deploy automático.

### Declarações de invariante
Este ciclo não alterou runtime. Não deployou. Não executou worker. Não chamou /api/ingest.
Não escreveu em Neo4j/Qdrant. Não ativou seeds. Não alterou aliases nem cognição central.
Não treinou. Zero HTTP a terceiros. Zero projeto paralelo como evidência.

## [2026-10-03] Backup final Neo4j Aura (pré-cancelamento do serviço)

- **Contexto:** Operador informou que o serviço AuraDB (85cd4c04.databases.neo4j.io) será cancelado.
- **Export (read-only):** `backups/neo4j_aura_final_20261003/` — 6461 nós (Conceito 2136 / Episodio 3651 / Fato 598 / FonteWeb 76) e 4526 rels (MINERADO_DE 2426 / RELACIONA 1449 / CONFIRMA 651); schema (constraints/índices/versão) em `schema.json`; SHA256 e contagens em `manifest.json`; baseline viva confere (concept=2136, fact=598).
- **Verificação:** restore provado em Neo4j 5 local (container efêmero) — comparação byte-a-byte 6461/6461 nós + 4526/4526 rels OK; alvo final sem `_eid`/`__TMP_EID`, contagens idênticas.
- **Ferramenta:** `apps/api/scripts/aura_final_backup.py` (export read-only / restore / verify / cleanup).
- **Nota:** o workflow semanal `db-backup.yml` gera payload simulado, não dump real — o backup desta seção é o export real de referência.


---

## #054.2.R2 — Readiness patch aditivo implementado (PR, sem merge/deploy)

**Status:** PR aberta (draft) — `fix/054-2-readiness-graph-ready-field` · **Data:** 2026-10-03
**Arquivos:** `apps/api/app.py` (aditivo: `graph_ready`, `boot_reason`, `status` booting/online) ·
`apps/api/scripts/check_space_telemetry.py` (`--wait-ready` com backoff determinístico 8×5-30s,
distingue COLD_BOOT de DRIFT_REAL) · `tests/test_readiness_graph_ready_054_2_r2.py` (T1-T6)
**CI:** (verificar no push da PR) · **Deploy:** NÃO · **Worker:** NÃO · **Ingest:** NÃO
**Escrita em Neo4j/Qdrant:** NÃO · **Treino:** NÃO · **Contaminação cross-project:** 0

### Contrato (aditivo, nada removido)
- `status`: "online" (grafo OK) | "booting" (cold boot/wake-up) — novo valor aditivo.
- `graph_ready`: bool sempre presente.
- `boot_reason`: "neo4j_not_ready" quando não pronto.
- Cold boot NUNCA é declarado como drift cognitivo pelo cliente.

## [2026-10-05] Migração do grafo: Neo4j Aura → Railway Neo4j CE (#054.7)

- **Contexto:** cancelamento iminente do AuraDB. Fonte: backup verificado `8ed58ea`.
- **Destino:** Railway (plano HOBBY existente, custo marginal ~$2,65/mês dentro do uso inclusivo): projeto `nexus-alpha-graph`, serviço `nexus-graph` (imagem neo4j:5, heap 128–192m), volume persistente em `/data`, TCP proxy `zephyr.proxy.rlwy.net:40107` → 7687.
- **Dados:** restore byte-a-byte (6461 nós / 4526 rels) via `aura_final_backup.py` (restore → verify → cleanup); constraints `conceito_nome`/`fonte_url` recriadas; senha rotacionada após provisionamento.
- **Código (#054.7, commit `c734eea`):** forçamento `bolt://→neo4j+s://` agora restrito a hosts `*.databases.neo4j.io` (Aura); scheme explícito do operador prevalece em self-hosted standalone. Suite 812 passed / 20 skipped; CI success.
- **Space:** NEO4J_URI (variable) / NEO4J_PASSWORD, NEO4J_USER (secrets) migrados; colisão variable×secret resolvida (causava CONFIG_ERROR); Space refeito **público** (estava privado — 404 anônimo quebraria site Vercel e worker do cron); deploy via `deploy_hf_space_safe.py` (67 arquivos).
- **Prova E2E:** `/api/metrics` público → `status online | concept 2136 | fact 598 | verified 20 | hebbian True | vectors 1679`.
- **Trade-off registrado:** tramo Space→Railway usa `bolt://` sem TLS (senha forte; mitigação futura: túnel TLS). O AuraDB pode ser cancelado a qualquer momento.

## [2026-10-07] Pós-migração: backup semanal REAL + auditoria #054.6

- **Backup semanal real (`5d08659`):** db-backup.yml agora executa `aura_final_backup.py export` contra o Railway (antes: payload simulado, nunca foi dump). Prova: run `37688323561` SUCCESS → `backups/auto_weekly/` commitado (`5ae17e2`), gzip 413 KB, integridade SHA256 OK, 6461 nós/4526 rels, fonte `zephyr.proxy.rlwy.net:40107`. Secrets GH `NEO4J_URI`/`NEO4J_PASSWORD` criados.
- **#054.6 (read-only, relatório `apps/api/reports/audit_054_6_monorepo_paths.md`):** nenhum consumidor de caminho quebrado pós-split — workflows, deploy scripts (allowlist provada UPLOAD_OK 67 arquivos), worker, compose, tests, README todos consistentes. Divergências: apenas 4 docs de design com caminhos pré-split (`src/frontend/…`) — plano docs-only proposto, não aplicado.
- **Housekeeping:** `AGENTS.md` (política Terminal & CLI First) commitado — existia só no disco.

## [2026-10-07] Go: TLS no tramo Space→Railway + docs #054.6 aplicados + PR #1 destravada

- **TLS (`bolt+ssc://`):** cert self-signed (CN `zephyr.proxy.rlwy.net`, 825d) em `/data/certs/bolt/` do volume Railway; envs `NEO4J_dbms_ssl_policy_bolt_enabled=true`, `NEO4J_dbms_ssl_policy_bolt_base__directory=/data/certs/bolt`, `NEO4J_server_bolt_tls__level=REQUIRED` (nomes `server.ssl.policy.*` rejeitados pela validação estrita; doc 5 confirma `dbms.ssl.policy.*`). Space variable `NEO4J_URI`, GH secret e `.env` local migrados para `bolt+ssc://`; plaintext `bolt://` recusado (tls REQUIRED). E2E público: 2136/598/20 no canal cifrado. Trade-off: self-signed cifra sem autenticar o servidor (evolução futura: CA privada).
- **Docs #054.6 aplicados:** 12 referências pré-split corrigidas em 8 arquivos (`dca4999` + `690016f`); README (caminhos relativos sob `apps/web/`), SPRINT e relatórios históricos intocados por design.
- **PR #1 destravada:** conflito em SPRINT.md resolvido via merge main→branch (`3ba70bd`), cronologia preservada (seção R2 de 03/10 antes das de 05–07/10) — PR MERGEABLE, aguardando Ready for review + merge do Operador.
- **AuraDB:** cancelado pelo Operador — encerrado. Fonte canônica de restauração: `backups/` (`8ed58ea`) + backup semanal real (`5d08659`).

## [2026-10-07] #054.2.R3 — Space com patch de readiness em produção (SUCCESS)

- **Deploy:** `deploy_hf_space_safe.py --execute` → UPLOAD_OK 67 arquivos (main `d81bd26`, merge da PR #1; CI success no merge).
- **Contrato novo no ar:** `/api/metrics` público → `status: "online" | graph_ready: true | boot_reason: null | 2136/598/20`.
- **Gate oficial:** `check_space_telemetry.py --wait-ready` → `{"attempt": 1, "verdict": "READY"}`, exit 0.
- **Bugfix de produção (`--wait-ready`):** o loop da R2 chamava `_fetch_metrics_payload`, nunca definida no wrapper (NameError; T1-T6 cobriam só funções puras). Fix: função implementada reusando `_fetch_metrics` de `src.ops.space_telemetry` (dotenv lazy, D11) + teste de regressão (sem env → `{}` → INDETERMINATE).
- **#054.2 CLOSED** (R1 root-cause + R2 patch + R3 deploy/validação). Dívidas restantes citadas no SPRINT: #054.3, #054.4 (sem task emitida).
