# PARTIAL_048_10M_1_2_R3_GARRINCHA_EVIDENCE_INSUFFICIENT

**Data:** 2026-10-03 · **Modo:** read-only (nenhum worker/ingest/escrita/seed/treino/deploy)

## Resultado do probe cirúrgico (orçamento 3/3 respeitado, ordem exata do task)

| # | URL | Status | Garrincha/Manuel | Botafogo | Contexto | Confirmado p/ G1 |
|---|---|---|---|---|---|---|
| 1 | rsssfbrasil.com/sel/jogclub.htm | **200 OK** | não | sim | sim | **não** |
| 2 | rsssf.org/tablesb/brazchamp.html | **200 OK** | não | sim | sim | **não** |
| 3 | rsssf.org/sacups/copalib.html | **200 OK** | não | sim | sim | **não** |

## Conclusão

Os 3 caminhos estavam **corretos e vivos** (200 OK — ao contrário do R2, cujos 404 foram caminhos supostos). Mas **nenhum menciona Garrincha nem Manuel Francisco dos Santos**: as fontes tabulares permitidas atualmente alcançáveis cobrem Botafogo (VENCEU/tables) sem citar o jogador.

**Garrincha permanece 2/3 na mesma tripla canônica** (pt+en wikipedia, fato elementId `4:3b5e8459-...:3749`, spans limpos) — re-verificado read-only neste ciclo. O terceiro domínio não-Wikimedia **não existe nas fontes atualmente alcançáveis**.

## Implicação (§7 do task)

`ready_for_future_g1 = false` → **G1 não preparado, Garrincha congelado**. Os próximos caminhos possíveis exigiriam decisão do Operador (fora deste ciclo):

1. **D8 (governed seed extension design)** — incluir páginas de jogadores (ex.: páginas wiki do Garrincha já confirmam 2/3; estender seeds para minerá-las de forma recorrente acumularia o 3º domínio... mas pt/en wiki já são os 2 confirmados — o 3º precisaria de outra fonte permitida);
2. **Nova fonte permitida** — localizar (com probe único futuro) uma página não-Wiki que mencione Garrincha+Botafogo (biografias RSSSF de jogadores, se existirem em rsssfbrasil.com/players/*);
3. **Congelar DEFENDEU piloto** e focar nas dívidas observacionais já aceitas (D6/D7, O1–O4).

Nenhuma dessas opções é executável sem GO explícito.

## Invariantes preservadas

verified=20 · fact=598 · concept=2136 · quorum=3 · gsg=0 · fas=ok · unaccounted=0 · top_invalid=[] · fpg=0 · publishers=3 · hebbian=True. Nenhuma outra mutação no grafo.
