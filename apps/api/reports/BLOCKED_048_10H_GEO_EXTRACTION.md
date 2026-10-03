# BLOCKED_048_10H_GEO_EXTRACTION

**Data:** 2026-09-28
**Classificação:** `BLOCKED_048_10H_GEO_EXTRACTION`
**Dívida secundária:** `OBSERVABILITY_DEBT_GRAPH_SCOPED_GAP_NEGATIVE`

## Resumo

O worker GEO incremental foi executado (2 dispatches `workflow_dispatch`, ambos `success`), com
snapshot read-only e telemetria viva. Os fatos GEO **persistiram**, mas **não** atingiram
verificação por 3 domínios: `verified_facts_domain_independent` permaneceu **11**.

## Evidência

- Baseline: `concept=1894`, `fact=335`, `verified=11`, `unaccounted=0`, `invalid=[]`, `fallback=0`.
- Pós-run: `concept=2008`, `fact=403`, `verified=11`, `multi_domain=12`, `unaccounted=0`, `invalid=[]`, `fallback=0`.
- Telemetria GEO do worker: `osm_urls_seen=4`, `geo_triples_canonical=3`, `rejection={no_clean_city_evidence:1}`.
- **1º dispatch**: payloads GEO → `422` — `extracted_entities.0.confidence: Field required` (bug real no caminho GEO).
- **Fix** (`ca351aa`): `_build_geo_payloads` passou a incluir `confidence` (0..1). CI verde.
- **2º dispatch**: payloads GEO → `200` (`entities_processed=1`); 1 fonte com `502` transitório.
- Ainda assim, `verified` não subiu: a narrativa wiki PT/EN **não** produziu triplas canônicas
  `ESTÁDIO --LOCALIZADO_EM--> CIDADE` correspondentes → sem corroboracão de 3 domínios.

## Sem regressão / sem junk

- `unaccounted_raw=0`, `top_invalid_predicates=[]`, `fallback_promoted_to_graph=0`, `verified` estável.
- Nenhum objeto bairro/endereço/país/estado/coordenada como cidade.
- Nenhum fato VENCEU/DEFENDEU regrediu (verified estável).

## Dívida observacional (não bloqueante)

`graph_scoped_gap = -403` (≈ `distinct_fact_hashes(0) - persisted(403)`), sugerindo que
`distinct_fact_hashes` não está populando. Registrado como **#052.3.1**; **não** bloqueia
(`unaccounted_raw=0`). Não alterar código/validadores/quórum neste ciclo.

## Próximo passo

1. **#048.10H.2** — debug do caminho GEO: por que a narrativa wiki PT/EN não gera a mesma chave
   canônica do fato GEO (canonicalização de sujeito/objeto, mapeamento de predicado, cap de extração).
2. **#052.3.1** — corrigir contabilidade de `distinct_fact_hashes` (sem tocar quórum/verificação).
3. Não escalar next batch (#048.10L) antes de entender o bloqueio do lote atual.

## Segurança

- Snapshot AuraDB read-only antes do worker: **sim** (`.autonomous/048_10h_real/aura_snapshot_pre_048_10H_real.json`,
  ~3,4 MB, nodes=4538 / rels=3785; **não commitado**).
- Nenhum treino; nenhuma seed alterada; nenhum runtime cognitivo alterado; nenhum force-push.
- Cron `ai-cron.yml` re-disabilitado (`disabled_manually`) após cada dispatch.
