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
- `SPRINT.md`, `docs/TASKS.md` — registro

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
- `SPRINT.md`, `docs/TASKS.md` — registro

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
- `docs/TESTING.md` — índice de teste
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
- `SPRINT.md`, `docs/TASKS.md`, `docs/TESTING.md` — registro

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
- `SPRINT.md`, `docs/TASKS.md`, `docs/TESTING.md` — registro

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
