# ✅ Tasks — Backlog e Rastreio (Nexus-Alpha)

> Espelho operacional dos issues GitHub. A sprint vigente é sempre a fonte da
> verdade de escopo (`SPRINT.md`); esta página mantém o mapa consolidado
> #036→#056 e o estado do backlog.

**Atualizado em:** 2026-09-24

---

## 1. Sprint vigente

**Freeze de infraestrutura `v1.13.0`** (2–3 ciclos): nenhuma mudança de infra;
foco em qualidade semântica. A última evidência de produção (#048) indicou que
o gargalo é **equivalência semântica entre fontes** — ver [`RESEARCH.md`](./RESEARCH.md).

### Prioridade máxima (próximo ciclo)
| # | Tarefa | Justificativa (evidência) |
|---|---|---|
| — | Re-ingest controlado via worker pós-**#047** | ✅ **Cenário C** — 124 fatos; `duplicate_cross_domain=0`; gate de treino ainda fechado |
| — | **#058.3** parity audit | ✅ **concluída** — relatório PT/EN; prioridade `#058.4` (demo-memory mascarado); `#047.1` ×4, `#045.2` ×1 |
| — | **#058.4** fallback transparency | ✅ **concluída** — status `degraded`/`failed` nunca `partial_success` com `entities=0`; `fallback_health`; flag default false |
| — | **#047.1** Expand curated entity aliases | ✅ **concluída** — `evidence` em toda entrada; alvos `entity_divergence` ×4; cidade≠clube SP; negativos rigorosos |
| — | **#045.2** Expand predicate mapper (Pelé) | ✅ **concluída** — `play for`→`DEFENDEU`; golden `fact_hash` PT/EN Pelé; modais rejeitados |
| — | Tríade pós-#058.4 (re-ingest + rerun parity) | ✅ **Cenário B** — 266 fatos; `predicate_divergence 1→0`; near_collision 1→4; exact 0; `verified=0` (gate fechado); hint `#047.1`×6 |
| #047 | Aliasing curado de entidades | ✅ **concluída** — dicionário bilíngue + boundary fix extractor; goldens cross-lingual verdes |
| item 2 | Entity linking **diagnóstico** (sem promover fato) | medir `potential_verified_if_linking` antes de qualquer promoção |
| — | ~~Validador de span v2~~ | ✅ **#058.2** — fragmentos H3 rejeitados; residual boundary fechado em **#047** |

### Observabilidade (continuar monitorando)
- `ingestion_accounting.*` — gap `canonical_to_fact_gap ≤ 5` deve se manter.
- `verification.facts_with_two_or_more_domains` — alvo > 0 após resolver equivalência.
- `top_unmapped_predicates` / `top_invalid_predicates` — devem permanecer vazios de lixo (#043/#044 ok).

## 2. Mapa consolidado de issues

| Issue | Título | Sprint | Estado |
|---|---|---|---|
| #036 | Modelo `:Episodio` + persistência idempotente (`fact_hash+day`) | v1.12.0-beta | ✅ concluída |
| #037 | Leitura durável, índices e retenção (30d/10k) | v1.12.0-beta | ✅ concluída |
| #038 | Export de fatos verificados → Alpaca/JSONL | v1.14.0 | ✅ concluída |
| #039 | Config LoRA/SFT para LlamaFactory | v1.14.0 | ✅ concluída |
| #040 | CLI opt-in `train_lora.py` + testes sem torch | v1.14.0 | ✅ concluída |
| #041 | Canonicalizer (fold NFKD + artigos + hífen) | v1.13.0 3-lite | ✅ concluída |
| #042 | Refiner via `map_predicate` + golden cross-extractor | v1.13.0 3-lite | ✅ concluída |
| #043 | Guard `validate_predicate` no EntityExtractor | v1.13.0 3.1 | ✅ concluída |
| #044 | Expansão conservadora de aliases PT (modal/ambiguous) | v1.13.0 | ✅ concluída |
| #046 | Auditoria near-match cross-source (metric-only) | v1.13.0 | ✅ concluída |
| #049 | Corroboração por domínio distinto | v1.13.0 | ✅ concluída |
| #050 | Validador determinístico de span de entidade | v1.13.0 | ✅ concluída (v1 conservador) |
| #051 | Auditoria read-only pós-limpeza | v1.13.0 | ✅ concluída |
| #052 | Contabilidade de ingest (`IngestAccounting`) | v1.13.0 | ✅ concluída |
| #056 | Domain reputation determinística (allowlist curada) | v1.13.0 | ✅ concluída |
| #048 | Clusters curados de domínios independentes (futebol) | v1.13.0 | ✅ concluída — resultado: gargalo é semântico |
| #057 | Qualidade de extração: Cenário 3 medido | v1.13.0 | ✅ concluída |
| #058 | Source productivity audit + URLs improdutivas | v1.13.0 | ✅ concluída — `invalid_predicate=303` dominante |
| #045.1 | Expand Sport Predicate Vocabulary (lista fechada) | v1.13.0 | ✅ concluída — `invalid_predicate 303→0`, 279 testes |
| #058.2 | Span quality v2 (rejeição H3 de fragmentos PT/EN) | v1.13.0 | ✅ concluída — 285 testes; Inspeção 2: H3 dominante, não H1 |
| #047 | Aliasing curado de entidades + boundary fix | v1.13.0 | ✅ concluída — 310 testes; YAML curado + helpers no extractor/nlp |
| #058.3 | Cross-lingual extraction parity audit (read-only) | v1.13.0 | ✅ concluída — 325 testes; 6 alvos; prioridade `high_#058.4` (2 demo-memory mascarados, não gravados) |
| #058.4 | Fallback transparency (status honesto + `fallback_health`) | v1.13.0 | ✅ concluída — nunca `partial_success` com `entities=0`; flag `NEXUS_ALLOW_DEMO_FALLBACK` default false; métricas #058.4 |
| #047.1 | Expand curated entity aliases (evidência parity) | v1.13.0 | ✅ concluída — `evidence` + variantes dos 4 alvos `entity_divergence`; cidade/clube SP separados |
| #045.2 | Expand predicate mapper (Pelé PT/EN) | v1.13.0 | ✅ concluída — `play for`→`DEFENDEU`; golden `fact_hash` Pelé; sem `represented` (conflito `representa`→`SER`) |
| — | Tríade re-ingest + parity rerun + cenário | v1.13.0 | ✅ **Cenário B** — 266 fatos; #045.2 fechou predicate; #058.4 fechou masked; entity_divergence 6/6 → decisão `#047.2` vs outra via |
| #064 | Concept reconciliation (dívida pós-#058.3) | dívida | 📌 backlog — registrar; **não executar** até evidência adicional |
| #045 | (implícito) predicate mapper — reabrir só se `top_unmapped` voltar a ter verbos claros ≥3 | — | 🧊 aguardando métrica |
| #053 | Independência editorial por publisher/eTLD+1 | dívida | 📌 backlog |
| #054 | Ontologia temporal (`:Ano`/`:Periodo`, `OCORREU_EM`) | dívida | 📌 backlog |
| #055 | Integração API REST do Almanaque | dívida | 📌 backlog |

## 3. Template de tarefa (padrão do repositório)

Toda issue/tarefa deve declarar:

```markdown
#### [Issue #NNN] — Título
- **Descrição:** o que e por quê (com evidência de métrica).
- **Arquivos Afetados:** lista explícita (nada fora disso).
- **Critérios:** critérios verificáveis + DoD de testes.
- **Fora de escopo:** o que esta tarefa NÃO faz.
```

Regras de decomposição detalhadas: [`TASK_BREAKING_DOWN.md`](./TASK_BREAKING_DOWN.md).

## 4. Regras de fluxo

1. Tarefa só entra em execução se estiver mapeada na sprint vigente.
2. 1 tarefa = 1 commit (staging explícito; sem `git add -A`).
3. Métrica flat **não** invalida código quando a causa é documentada
   (ex.: fragmentação histórica exige re-ingest controlado).
4. Ao concluir, registrar resultado (números reais) em `SPRINT.md`.
