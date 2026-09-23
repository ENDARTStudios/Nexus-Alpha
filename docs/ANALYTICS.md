# 📊 Analytics e Métricas — `/api/metrics` (Nexus-Alpha)

A observabilidade do sistema é **de produto, não de marketing**: cada métrica
existe para responder uma pergunta de decisão. Fonte única: `GET /api/metrics`
no Space (via proxy para o frontend).

---

## 1. `cognitive_health` — a memória está sadia?

| Métrica | Definição | Alvo |
|---|---|---|
| `episodic_persistence_rate` | fração de episódios que sobrevivem (durável/total) | ≥ 0.95 |
| `hebbian_consistency_check` | consistência da consolidação vs grafo | `true` (false ⇒ Neo4j caiu) |
| `retention_pressure` | ocupação do teto de 10k episódios: low <50%, medium <80%, high ≥80% | low/medium |

**Decisão associada:** `high` ⇒ investigar poda (`prune_episodes`) e volume
de ingest; nunca "resolver" desligando a retenção.

## 2. `ingestion_accounting` — o pipeline não perde nem infla nada

Introduzida no #052 para separar **ocorrência** de **chave distinta**:

| Métrica | Definição |
|---|---|
| `raw_triples` | triplas brutas recebidas |
| `canonical_triples` | ocorrências refinadas (conta duplicatas) |
| `distinct_canonical_keys` | chaves canônicas distintas |
| `duplicate_canonical_occurrences` | `canonical_triples − distinct_canonical_keys` |
| `duplicate_same_source_url` / `duplicate_same_domain` / `duplicate_cross_domain` | classificação da duplicação — **só cross_domain aumenta verificação** |
| `persisted_facts` | fatos persistidos |
| `canonical_to_fact_gap` | `distinct_canonical_keys − persisted_facts` (alvo ≤ 5) |
| `unaccounted_raw` | matéria-prima não reconciliada (alvo = 0) |
| `merged_into_existing_fact` / `new_facts_created` | destino do ingest |
| `accounting_mode` | `exact` ou `approximate_overflow` (set > 10k) |
| `process_started_at` / `last_ingest_at` | janelas temporais |

Regras de leitura: `verified_facts` sobe **só** por
`duplicate_cross_domain`; gap alto com chaves distintas indica MERGE reusando
`FonteWeb` sem nova confirmação (mesma `source_url`).

## 3. `verification` — o contrato anti-fake-news

| Métrica | Definição | Estado |
|---|---|---|
| `quorum` | quórum vigente (deve ser **3**) | fixo |
| `facts_with_multi_domain` / `facts_with_two_or_more_domains` | fatos com ≥2/≥3 **domínios** distintos | alvo > 0 (bloqueado por R1, ver [`RESEARCH.md`](./RESEARCH.md)) |
| `max_domain_confirmations` | maior contagem de domínio distinto por fato | produção: 1 |
| `verified_facts_domain_independent` | fatos verificados por domínio independente (#049) | métrica honesta — pode ser menor que o legado |

Histórico: antes do #049, `confirmacoes` contava **URLs** (4 URLs da
Wikipedia = 4) — métrica corrigida para host/distrito.

## 4. `extraction_quality` — o refino está sano?

| Métrica | Uso |
|---|---|
| `rejection_reasons` | contadores por motivo tipado (`unmapped_predicate`, `nonverbal_predicate`, `modal_predicate`, `ambiguous_predicate`, `object_date_like`, …) — **dinâmico** |
| `top_unmapped_predicates` | verbos legítimos fora do vocabulário — alimenta #044/#045 |
| `top_invalid_predicates` | lixo não-verbal — deve tender a vazio (guard #043) |
| `duplicate_canonical_triples` | dedup intra-payload (legado, preservado) |

Interpretação (histórico): `top_invalid` vazio + rejeitados verbos legítimos ⇒
gargalo não é vocabulário; `top_unmapped` sem verbo recorrente (≥3) ⇒ não é
predicate mapper.

## 5. `quarantine`

Tamanho/estado da quarentena de rejeitados (volátil, 10k rotativo) e da
fila de fatos sem quórum. **Quarentena cheia não é erro** — é sinal de
qualidade de entrada; investiga-se os motivos, não se esvazia à força.

## 6. Como consumir

```bash
curl -s "$NEXUS_SPACE_URL/api/metrics" -H "Authorization: Bearer $HF_TOKEN" | python -m json.tool
```

No frontend, os painéis consomem via proxy (`/api/nexus/api/metrics`) —
nunca direto ao Space.

## 7. Rotinas de leitura (cadência)

| Quando | O que olhar | Onde registrar |
|---|---|---|
| Todo ciclo do worker (6h) | job do Actions verde + `ingestion_accounting.unaccounted_raw = 0` | — |
| Semanal | `cognitive_health` + `retention_pressure` | `SPRINT.md` quando fora do padrão |
| Por sprint | auditorias read-only (`scripts/audit_post_clean.py`, `audit_cross_source.py`) | resultado em `SPRINT.md` (padrão #046/#051) |
| Ao abrir métrica nova | definição neste doc + teste (`tests/test_ingest_accounting.py` é o exemplo) | PR única |

## 8. O que NÃO é métrica deste projeto

Não medimos: sessões de usuário, pageviews, CTR — o produto é o cérebro, não
o site. Métricas de superfície pública não existem de propósito (ver
[`COMPLIANCE.md`](./COMPLIANCE.md) §1: sem rastreio de usuários).
