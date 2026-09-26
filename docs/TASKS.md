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
| — | **#058.5** Botafogo EN extraction forensics | ✅ **concluída** — causa raiz `fetch` (seed EN HTTP 404); H1 supported; hint `#048.3`; candidatas EN 200; 364 testes |
| — | **#048.3** Replace stale Botafogo EN 404 audit target | ✅ **concluída** — URL 404 removida de 3 `DEFAULT_TARGETS`/`TARGETS`; canônica `Botafogo_de_Futebol_e_Regatas` (200, raw 15, canon 10); escopo corrigido (#058.5: era alvo de auditoria, não seed de produção) |
| — | **#048.4** Add productive EN Botafogo source to cluster | ✅ **concluída** — fonte EN canônica em `garrincha_botafogo` (HTTP 200, canon 10 offline); cluster 3 domínios / 2 publishers / 5 URLs; 366 testes |
| — | **#058.8** sparse merge do fallback regex | ✅ **concluída** — `SPACY_SPARSE_MIN=10`, merge fallback-lazy-primeiro; run `36064311931`; EN Pelé 1→25, gap `canonical_to_fact_gap` 7→0; 376 testes |
| — | **#058.9** triagem read-only dos 21 pares PT/EN | ✅ **concluída** — `predicate_mapper_gap=0`, `object_alias_missing=0`, `fix_both=21` (ruído); decisão: descartar #047.1/#045.3 → abrir **#058.10** |
| — | **#058.10** guard `object_predicate_complement` (SER × cláusula EN) | ✅ **concluída** — 5 camadas determinísticas no `span_validator` + call-site `predicate=`; dry-run: 45/141 SER rejeitados, 0 PT, 16/19 pares EN; 380 testes; **Fase B validada em produção** — run `36090364284`, `opc=43`, padrões banidos 0, EN share 85,6%→81,4%, PT gate não-vazado (gap 7 = pt-IA cold-start, `unaccounted=0`); **Cenário 2 parcial** (divergência editorial real) |
| — | **#048.5** Curated target-fact clusters (sem API Almanaque) | 🚧 **bloqueada por #058.11** — mecanismo entregue (`scripts/audit_cluster_productivity.py` + `reports/cluster_productivity_048_5.json`, Jev aplicado); 3 clusters inelegíveis (0/1/0 domínios aceitos); causa raiz: **gap de extração target-aware** — 15 URLs com `target_fact_sentences>0`, 0 triplas-alvo cruas/canônicas, Jev triplas ≤0.11, único hit UOL `SER`; `alias_missing=0`/`mapper_gap=0` → não é #047.2/#045.3; seeds intocadas |
| — | **#048.5a** Varredura read-only de fatos-alvo alternativos | ✅ **concluída** — `scripts/audit_target_fact_sweep.py` + `reports/target_fact_sweep_048_5a.json`; 5 fatos × 4–6 fontes, hit = estrutural OU Jev ≥0.65; **veredito `no_viable_target` (0/5)** — melhor caso: UOL 1/3 domínios no Brasileirão (Jev 0.94), pt-wiki Pelé 51 sentenças-alvo → 0 triplas; evidência negativa → passo 4 (#058.11); seeds intocadas |
| — | **#058.11** Target-aware extraction gap analysis | 🟡 **fase 1 concluída (diagnóstico)** — `scripts/audit_extraction_gap.py` + `reports/extraction_gap_058_11.json`: 10 casos/54 sentenças-alvo, `converted_in_probe=0`; dominante `no_relation_pattern` (37/54 root não-verbal — definições nominais) + `predicate_unmapped` (11/54, verbos não-fato); **refutados**: `max_triples_truncation` (0/10), score (49/54 ≥0.6), anáfora/data/frase-longa; causa-raiz: `extract` exige `ROOT ∈ (VERB,AUX)` (`extractor.py:196`); fase 2: **F3 aplicada (#058.11.1)** — filtro `is_propositional_sentence` + `NOISE_SELECTORS` infobox/figure + `pre_filter_rejections` (414 testes); **rerun pós-F3**: `reports/extraction_gap_058_11_post_f3.json` — junk doc-root 37→**5**, `NUM/PUNCT` roots →**0**, sentenças-alvo 54→47, 259 candidatas rejeitadas pelo filtro; `no_relation_pattern` **segue dominante (8/10)** e `converted=0` com sentenças limpas → **gargalo estrutural confirmado, GO p/ F1 (#058.11.2)**; fase 3: **F1 aplicada (#058.11.2)** — flag `enable_nominal_copular` + frames/gates/rescue/interleaved em `extractor.py`, `tests/test_nominal_copular_extraction.py` (40), `scripts/audit_nominal_copular_dry_run.py`; **dry-run 10/10 gates PASS** (`reports/nominal_copular_dry_run_058_11_2.json`): `new_triples=16`, `target_fact_hits=4` (C3/C6/C9/C10 = 3/4 fatos únicos), `ser_share_after=0.359` (−4.1 p.p.), `pt_regression=false`, `clause_like_residual=0`, zero garbage |
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
| — | Tríade re-ingest + parity rerun + cenário | v1.13.0 | ✅ **Cenário B** — 266 fatos; #045.2 fechou predicate; #058.4 fechou masked; entity_divergence 6/6 → decisão #058.5 |
| #058.5 | Botafogo EN extraction forensics | v1.13.0 | ✅ concluída — `diagnosis=fetch` (seed EN 404); `next=#048.3`; H1 supported; H2–H7 não; 364 testes |
| #048.3 | Replace stale Botafogo EN 404 audit target | v1.13.0 | ✅ concluída — 3 scripts corrigidos; canônica EN `Botafogo_de_Futebol_e_Regatas`; seeds intocadas |
| #048.4 | Add productive EN Botafogo source to cluster | v1.13.0 | ✅ concluída — `garrincha_botafogo` ganhou EN canônica (offline 200/canon 10); 2 testes novos; 366 testes |
| #058.8 | Sparse merge do regex fallback (spaCy sparse) | v1.13.0 | ✅ concluída — `SPACY_SPARSE_MIN=10`; run único `36064311931`; `Fato` 119→248; 376 testes |
| #058.9 | Triagem read-only dos 21 pares PT/EN | v1.13.0 | ✅ concluída — `root_cause=ruído/verdade (13/8)`, `gap_mapper=0`, `gap_alias=0`; #047.1/#045.3 descartados |
| #058.10 | Guard `object_predicate_complement` (SER × cláusula EN) | v1.13.0 | ✅ concluída — 5 camadas em `span_validator`; dry-run 45/141 SER rejeitados, 0 PT; 380 testes; **Fase B validada** (run `36090364284`; Cenário 2 parcial) |
| #048.5 | Curated target-fact clusters sem API Almanaque | v1.13.0 | 🚧 **bloqueada por #058.11** — auditoria entregue (3 clusters inelegíveis); gargalo = extração target-aware (sentença presente, tripla não nasce); seeds intocadas |
| #048.5a | Varredura read-only de fatos-alvo alternativos | v1.13.0 | ✅ concluída — 5 fatos, veredito **`no_viable_target` (0/5 elegíveis)**; melhor: UOL Brasileirão 1 domínio (Jev 0.94); pt-wiki Pelé 51 sentenças-alvo → 0 triplas; evidência negativa → #058.11 |
| #058.11 | Target-aware extraction gap analysis | v1.13.0 | ✅ **F1 aplicada + dry-run GO** — F3 (#058.11.1) + **F1 nominal/copular gateada (#058.11.2)**: `extractor.py` (flag, frames, dep-SER, gates `ser_share`/entidade-dupla, known-entity rescue, interleaved por sentença, dedup nominal) + 40 testes + `audit_nominal_copular_dry_run.py`; **10/10 gates PASS**: `new_triples=16`, `target_fact_hits=4`, `ser_share_after=0.359` (−4.1 p.p.), `pt_regression=false`, zero garbage; alvos 0 honestos: C1 (lead=`noise_marker` F3, `rio de janeiro` fora da whitelist), C4/C5/C7/C8 (frame/anti-genérico/sparse-band congelado); F2 só acessório; não abrir #047.2/#045.3 amplos; não aumentar `max_triples`; próximo: worker único + medir `duplicate_cross_domain`/`verified_facts` → cenários A/B/C |
| #064 | Concept reconciliation (dívida pós-#058.3) | dívida | 📌 backlog — registrar; **não executar** até evidência adicional |
| #045 | (implícito) predicate mapper — reabrir só se `top_unmapped` voltar a ter verbos claros ≥3 | — | 🧊 aguardando métrica |
| #053 | Independência editorial por publisher/eTLD+1 | dívida | 📌 backlog |
| #054 | Ontologia temporal (`:Ano`/`:Periodo`, `OCORREU_EM`) | dívida | 📌 backlog |
| #055 | Integração API REST do Almanaque | dívida | 🧊 **congelado por compliance** — API confirmada (OpenAPI 3.0.3 `/docs/json`, 87 paths, leituras públicas `/api/v1/clubs|players|competitions|rankings`); ToS: API incluída no plano **Elite** com chave individual + extração em escala/scraping proibidos → decisão/licença do operador; **não consumir `/api/v1/*`** (#058.11 tem prioridade) |

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
