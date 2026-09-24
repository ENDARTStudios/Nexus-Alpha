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

