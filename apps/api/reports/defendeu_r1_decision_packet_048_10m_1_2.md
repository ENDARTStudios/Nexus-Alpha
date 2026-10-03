# #048.10M.1.2.R1 — Packet de decisão: diagnóstico read-only do piloto DEFENDEU

**Data:** 2026-10-03 · **Modo:** read-only (nenhum worker, nenhuma escrita, nenhuma seed, nenhum treino, nenhum deploy)
**Meta:** `SUCCESS_048_10M_1_2_R1_ROOT_CAUSE_AND_CRITERIA_PACKET_READY`
**Evidência:** `reports/defendeu_r1_graph_state_048_10m_1_2.json` (regenerado agora, read-only, Neo4j vivo via MATCH/RETURN — script `scripts/diagnose_defendeu_r1_graph_state_048_10m_1_2.py`) · `reports/defendeu_pilot_worker_fact_validation_048_10m_1_2.json` · `reports/defendeu_pilot_dry_run_048_10m_1.json` · probes `.autonomous/048_10m_1/probes/` · `config/seed_clusters.yaml`

## 0. Estado atual do grafo (re-verificado read-only NESTE ciclo)

| Candidato | Presente | Confirmações | Domínios | Faltam |
|---|---|---|---|---|
| Garrincha → Botafogo | **sim** | 2 | pt.wikipedia.org, en.wikipedia.org | 1 domínio (não-wiki) |
| Jairzinho → Botafogo | **sim** | 1 | rsssfbrasil.com | 2 domínios |
| C. A. Torres → Santos | não | 0 | — | 3 |
| Zito → Santos | não | 0 | — | 3 |
| Romário → Vasco | não | 0 | — | 3 |
| Sócrates → Corinthians | não | 0 | — | 3 |
| Ceni → São Paulo | não | 0 | — | 3 |

Nota de correção de instrumento: o script R1 inicialmente usou `w.dominio` (propriedade inexistente no `FonteWeb` — a correta é `w.domain`); corrigido antes da análise. O estado bate 1:1 com a validação fact-level do piloto (02:08 UTC) — **nenhuma mutação do grafo desde o incidente**.

## 1. Os 15 minutos das 15 perguntas (com evidência)

**Q1 — candidatos semanticamente válidos sob a ontologia atual?** Sim, os 7. Todos já passaram pela seleção (risks D1/D2/D3 mapeados, `requires_ontology_change: false` em 7/7, `source_policy: allowed` em 7/7) e o predicado DEFENDEU→clube é o padrão consolidado do grafo (ex.: Pelé→Santos, verificado, 3 confirmações — visto na vizinhança do Santos).

**Q2 — evidência read-only suficiente em fontes permitidas?** Sim, com granularidade variável: probes reais read-only (HTTP 200, infobox) confirmaram pt+en para 6/7 e pt para Zito. Evidência RSSSF tabular é plausível para todos (RSSSF já provou extração tabular em `copalib.html`/`brazchamp.html`).

**Q3 — causa da não-verificação:** **f) combinação**, dominada por **(a) + (b) + (d)**:
- (a) `seed_clusters.yaml` tem 22 clusters mirando **clubes/estádios/honras**; único cluster de jogador é `garrincha_botafogo`. Nenhum cluster mira Jairzinho, Zito, Romário, Sócrates, Ceni ou C.A. Torres → **5/7 nem entraram no stream de candidatos**;
- (b) extração de carreira individual: o pipeline extrai DEFENDEU de páginas de clube/honras quando o jogador aparece (Jairzinho via tabela RSSSF do Botafogo; Garrincha via wiki do Botafogo/Garrincha) — mas não há varredura de carreira individual;
- (d) quórum 3 é **cumulativo multi-ciclo** (consolidação server-side acumula confirmações de domínios distintos) — "colisão plena em ciclo único" nunca foi o desenho;
- (c) canonicalização/alias: **descartada para 6/7** (Garrincha e Jairzinho casaram limpo; Ceni casou como "ROGERIO CENI" sem acento). Caso (c)-adjacente só no Zito: a evidência local era um fato **span-quebrado** ("ZITO --DEFENDEU--> PELO SANTOS") que não canônica para "SANTOS FUTEBOL CLUBE" — ver Q4;
- (e) nenhum candidato exige mudança ontológica.

**Q4 — confirmações parciais persistentes de Jairzinho/Garrincha?** Sim, re-verificadas NESTE ciclo: Garrincha 2 confirmações (pt+en wikipedia) e Jairzinho 1 (rsssfbrasil.com), ambas `verificado: false`, persistentes desde o run.

**Q5 — acumulam naturalmente em ciclos futuros?** **Não é esperado.** Quórum conta **domínios distintos**; os seeds atuais não reminejam páginas novas que produziriam esses fatos: o domínio rsssfbrasil do Jairzinho repete a cada ciclo (confirmações crescem, domínios não), e o Garrincha precisaria de 1 domínio **não-wiki** que os seeds do cluster não entregam com o fato DEFENDEU (o gazetadoparana entregou SER, não DEFENDEU). Acúmulo natural ≈ estagnado sem intervenção direcionada.

**Q6 — os 5 ausentes chegariam sem mudança de seeds/extração direcionada?** **Não.** Nenhum seed mira as páginas deles; a vizinhança DEFENDEU dos clubes-alvo está vazia para Vasco (0 fatos) e Corinthians (0 fatos) — não existe no grafo nenhum fato DEFENDEU para esses clubes que pudesse acumular. Nuance do Zito: `santosfc.com.br/institucional/historia` redireciona para a página do Zito mas está auditado `unproductive` (JS/redirect) — não entrega tripla.

**Q7 — o dry-run do #048.10M.1 estava errado em quê exatamente?** Em **uma suposição de modelagem**: `local_existing_covered` contou os domínios da **evidência de grafo pré-existente** como se o ciclo do worker fosse **reminejar** esses domínios para cada candidato. O gate `predicted_full_collision_facts: 7` presumia que cada fato seria re-extraído de ≥3 domínios distintos **numa única passada**. O que o dry-run validou corretamente: risco, ontologia, source policy, spans, contabilidade — tudo passou; só a **previsão de colisão** estava errada.

**Q8 — "full collision em ciclo único" é realista para o worker atual?** **Não.** O sistema é de **convergência multi-ciclo**: cada ciclo mined seeds fixas e a consolidação acumula confirmações por domínio distinto. Colisão plena em ciclo único só ocorreria se os seeds já mirassem ≥3 domínios por candidato — ou seja, é meta de **batch direcionado**, não de worker genérico.

**Q9 — modelo correto:** híbrido em 3 estágios — (i) **reclassificar o critério do piloto** como multi-ciclo/direcionado (nunca "7/7 em 1 ciclo"); (ii) **batch direcionado read-only→ingest** por subconjunto, usando as páginas já probeadas (fontes permitidas, sem tocar núcleo); (iii) opcionalmente, **extensão governada de seeds** depois, para os fatos verificados permanecerem corroboráveis em ciclos futuros.

**Q10 — algum candidato exige alias/ontologia/seed?** Alias/ontologia: **nenhum** (7/7 `ontology_change_required: false`; matches canônicos confirmados). Seeds: **todos dependem de seeds ou de extração direcionada** para chegar ao grafo — isso os torna CV2/CV3, não CV4 (CV4 é para alias/ontologia, e nenhum precisa). Os fatos span-quebrados pré-existentes ("ZITO→PELO SANTOS", "GARRINCHA→PRIMEIRA PARTIDA DO TORNEIO", "CENI→CONTRATADO COMO TECNICO") são **casos de span validator**, pré-existentes ao piloto (junk do piloto = 0) — anotados, não bloqueiam.

**Q11 — risco de junk se repetirmos o worker sem correção?** Sim, moderado: a vizinhança DEFENDEU dos clubes já contém fatos span-quebrados de origem narrativa ("CRAQUE CONSOLIDADO POR PRATICAMENTE TODA→Botafogo" etc.). Repetir o worker genérico não gera os 7 (Q5) e continua expondo o extrator a texto narrativo que já produziu objetos malformados.

**Q12 — risco de poluir o grafo com fatos não verificáveis?** Fatos não-verificados **por design** permanecem no grafo até quórum — isso é contabilidade sadia (`fact_accounting_status: ok`, `unaccounted_raw: 0`). O risco real é **span-quebrado** (Q11); mitigação: batch direcionado em páginas probeadas (infobox) + span validator existente + gate fact-level por ciclo.

**Q13 — próximo gate mínimo seguro antes de qualquer escrita?** **Gate G1 (1 candidato, 1 domínio novo):** Garrincha (2/3) — batch direcionado em 1 fonte não-wiki permitida (ex.: página do Botafogo em RSSSF ou gazetadoparana revisada para DEFENDEU), **dry-run read-only** da tripla prevista (gate: ≥1 domínio novo não-wiki + span válido + sem regression), depois **1 ingest única**, gate: `verified_expected_facts ≥ 1` (prova incremental 1/7 sem tocar núcleo).

**Q14 — provar 1/7 ou 2/7 incremental sem mudar núcleo?** **Sim.** Garrincha falta 1 domínio → 1/7 é o caminho mais curto (Q13). Jairzinho precisa de 2 novos domínios → 2/7 num segundo batch direcionado (pt.wikipedia Jairzinho já probeado). Nenhum exige alias/ontologia/seeds.

**Q15 — recomendação conservadora:** **Recomendação A + C** (detalhada na §3): reclassificar o critério do piloto como **multi-ciclo + direcionado**; congelar worker genérico para DEFENDEU; desenhar batch direcionado começando por Garrincha→1/7; adiar Romário/Sócrates (risco D3-empréstimo) e Zito (domínio único probeado) para lotes posteriores; extensão de seeds (B) só depois de 1/7 provado; treino segue fechado.

## 2. Classificação CV por candidato

| Candidato | CV | Justificativa com evidência |
|---|---|---|
| Garrincha → Botafogo | **CV2** (CV1-fraco) | 2/3 no grafo; falta 1 domínio não-wiki; seeds atuais não entregam DEFENDEU de novo domínio (gazetadoparana rendeu SER) → direcionado resolve sem núcleo |
| Jairzinho → Botafogo | **CV2** | 1/3 (rsssfbrasil); repetição do mesmo domínio não cresce quórum → precisa de ≥2 novos domínios via direcionado (pt/en wiki já probeados) |
| C. A. Torres → Santos | **CV2** | probe pt+en ✓ (infobox); sem seed; direcionado em 3 domínios probeados fecha |
| Ceni → São Paulo | **CV2** | probe pt+en ✓; carreira de clube único (D3 mitigado); sem cluster de jogador do São Paulo |
| Romário → Vasco | **CV2** (adiar: D3) | probe pt+en ✓; múltiplas passagens/loans (D3) — span validator decide; lote 2 |
| Sócrates → Corinthians | **CV2** (adiar: D3) | probe pt+en ✓; loan Fiorentina (D3) — lote 2 |
| Zito → Santos | **CV3** (com CV2 parcial) | probe **apenas pt** (1 página); precisa de ≥3 fontes mapeadas antes do batch; sem seed |

**Nenhum CV1** (acúmulo natural estagnado — Q5) · **Nenhum CV4** (Q10) · **Nenhum CV5** (probes existem) · **Nenhum CV7** (fontes permitidas) · **CV6 latente**: fatos span-quebrados pré-existentes na vizinhança (não produzidos pelo piloto) — mitigados por span validator + páginas probeadas.

## 3. Recomendação final do packet

**A + C**: **corrigir o critério do piloto** (multi-ciclo + direcionado; nunca "7/7 em 1 ciclo") e **reduzir o escopo** ao subconjunto com melhor evidência read-only — lote 1 = Garrincha (gate G1, prova 1/7), lote 2 = Jairzinho + C.A. Torres + Ceni, lote 3 = Romário + Sócrates (D3) + Zito (após mapear ≥3 fontes). **B** (extensão governada de seeds) só depois de 1/7 provado, para permanência da corroborabilidade. **D** não se justifica: há caminho seguro sem tocar núcleo.

## 4. Dívidas operacionais (O1–O4 do despacho permanecem; +1 anotação)

O1 supervision de worker · O2 canonical env loader · O3 snapshot custody · O4 telemetry field clarity — **+ 1 nova**: a propriedade do `FonteWeb` é `domain` (não `dominio`); scripts de leitura devem padronizar (reforça O4).
