# GEO-3 planning — atlas read-only do próximo lote GEO (sem worker)

**Data:** 2026-10-07 · **Status:** PLANNING DRAFT — nenhuma seed/registro alterado, nenhum worker executado.

## Estado atual do caminho GEO (telemetria dos ciclos 048.10M/R5-R7)

- Fontes GEO ativas: Maracanã, Neo Química Arena, Estádio Olímpico Nilton Santos,
  Beira-Rio, Mineirão, Arena Fonte Nova (pt/en) + Vila Belmiro (cluster `estadio_urbano_caldeira`).
- **Telemetria honesta:** as páginas wiki pt/en dos estádios grandes reportaram
  `quality: unproductive` ("texto limpo insuficiente — provavelmente JS/listing") no
  parser de narrativa; o caminho dedicado `geo_wiki_parser` (LOCALIZADO_EM) existe e
  roteia, mas ainda não demonstrou triplas produtivas acumuladas no grafo.
- Vila Belmiro é o único estádio com cluster histórico produtivo (ORIGINAL_ESTADIO).

## Lote GEO-3 proposto (candidatos + política de fontes)

| Candidato (estádio → cidade) | Fontes planejadas | Nota |
|---|---|---|
| Arena Corinthians (Itaquera) → São Paulo | pt/en wiki + artigo oficial do clube | infobox rica |
| Allianz Parque → São Paulo | pt/en wiki | — |
| Estádio Couto Pereira → Curitiba | pt wiki + gazetadoparana (domínio já produtivo no projeto) | sinergia com fonte validada |
| Estádio São Januário → Rio de Janeiro | pt/en wiki | história longa em prosa |
| Arena da Baixada → Curitiba | pt/en wiki | — |

**Política:** pt/en.wikipedia + no máximo 1-2 fontes não-Wiki validadas por probe
(D9) por estádio; `expected_predicate: LOCALIZADO_EM`; sem OSM/Nominatim neste lote.

## Pré-condições para o dry-run (GEO-3 dry-run, item 22)

1. Evidência de produtividade do `geo_wiki_parser` (ao menos 1 tripla
   `LOCALIZADO_EM` de estádio existente confirmada no grafo) — **ainda não demonstrado**.
2. Probes 200+menção das fontes não-Wiki do lote.
3. GO-5 do Operador para o worker do lote.

**Veredicto:** atlas DRAFT pronto; `ready_for_worker = false` até a pré-condição 1.
Alternativa honesta: pular GEO-3 e acumular diversidade pela linha DEFENDEU
(Jairzinho ✓ verificado; Zito a 1 domínio) que já usa fontes produtivas comprovadas.
