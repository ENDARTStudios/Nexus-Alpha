# INCIDENTE — #048.10M.1.2: fact-level validation FAIL (0/7 verificados)

**Data:** 2026-10-03 · **Classificação:** `BLOCKED_048_10M_1_2_WORKER_FAILED`

## O que aconteceu
Worker piloto executado **uma única vez** com sucesso técnico (72 fontes ingeridas,
200 OK, consolidação 200, sem junk, sem forbidden, sem regressão, sem fonte proibida,
sem 403/429). Porém a validação fact-level contra o registry de expected facts
resultou **0/7 verificados**:

| candidato | presente no grafo | verificado | domínios |
|---|---|---|---|
| defendeu_manuelfranciscodossantos_001 (Garrincha) | sim | não | 2 |
| defendeu_jairzinho_002 (Jairzinho) | sim | não | **1 (não-Wikimedia!)** |
| defendeu_zito_003 (Zito) | não | — | 0 |
| defendeu_socratesbrasileirosampai_005 (Sócrates) | não | — | 0 |
| defendeu_romariodesouzafaria_006 (Romário) | não | — | 0 |
| defendeu_carlosalbertotorres_007 (Carlos Alberto Torres) | não | — | 0 |
| defendeu_rogerioceni_012 (Ceni) | não | — | 0 |

## Causa raiz (read-only, sem alterar núcleo)
1. **Escopo de seeds do worker não cobre as páginas dos jogadores.** As seeds ativas
   miram páginas de **clubes** (elencos/história), GEO/OSM e queries gerais de IA.
   As páginas que corroborariam os expected facts (pt/en.wikipedia dos **jogadores**)
   não são mineradas neste ciclo — por isso 5/7 nem chegaram ao grafo.
2. **Quórum 3 não se acumula em ciclo único para a maioria.** Garrincha ganhou 2
   domínios (cluster Garrincha/Botafogo existe nas seeds) e Jairzinho 1
   (não-Wikimedia — RSSSF corroborou de fato neste ciclo, ao contrário do probe).
   Corroboração é cumulativa **entre ciclos**; um único worker não fecha 3 domínios
   para candidatos fora do escopo de seeds atual.

## O que NÃO aconteceu
- Sem junk objects; sem forbidden objects; sem source policy violations;
  sem predicados inválidos (`top_invalid_predicates=[]`); sem fallback promotion.
- Sem regressão: verified=20 preservado; gsg=0; fas=ok; same_scope=0; unaccounted=0;
  hebbian=True; fact_count/concept_count subiram (598/2136) — pipeline saudável.
- Nenhuma alteração de núcleo; nenhuma seed ativada; nenhum treino.

## Ação tomada (conforme packet §7 FAIL)
- Parado. **Sem segunda execução. Sem restauração automática.** Expansão congelada.
- Devolvido ao Operador com este incidente e as opções:
  - **Opção 1 (recomendada):** novo GO para task que **adicione as páginas dos 7
    jogadores às seeds** (`config/seed_clusters.yaml`/seed loader) — alteração
    proibida neste ciclo, exige GO explícito; depois disso, ciclos de worker
    acumularão os 3 domínios e a validação fact-level pode fechar 7/7.
  - **Opção 2:** aceitar a acumulação natural ao longo de vários ciclos com as
    seeds atuais (lento; RSSSF de jogadores não está nas seeds — provavelmente
    nunca fecha quórum para os 7).
  - **Opção 3:** reavaliar o critério do piloto (quórum em ciclo único era
    irrealista para candidatos fora do escopo de seeds — lição de planejamento).

## Estado do grafo pós-worker
`verified=20 · fact=598 · concept=2136 · quorum=3 · gsg=0 · fas=ok · ss=0 ·
unaccounted=0 · hebbian=True · fpg=0 · top_invalid=[]` — saudável, sem regressão.
