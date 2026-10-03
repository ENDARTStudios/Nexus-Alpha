# DIAGNOSED_048_10H_2_GEO_PARITY_BLOCKED_BY_SCOPE

**Data:** 2026-09-28
**Classificação:** `DIAGNOSED_048_10H_2_GEO_PARITY_BLOCKED_BY_SCOPE`
**Worker executado:** NÃO · **Escrita em Neo4j/Qdrant:** NENHUMA · **Treino:** NÃO

## Pergunta

Por que os fatos GEO persistidos via OSM/Nominatim **não** colidem com os fatos extraídos
das páginas wiki PT/EN (logo, ficam com 1 domínio e não verificam)?

## Evidência determinística

Reprodução read-only (`scripts/audit_geo_canonical_parity.py` → `reports/geo_canonical_parity_048_10h_2.json`)
com o **mesmo** refinador do `/api/ingest` (`refine_triple_ex`):

| Fato esperado | Chave OSM (canônica) | Chave wiki PT | Chave wiki EN |
|---|---|---|---|
| ALLIANZ PARQUE → SÃO PAULO | `ALLIANZ PARQUE\|LOCALIZADO_EM\|SAO PAULO` | *(nenhuma)* | *(nenhuma)* |
| MORUMBI → SÃO PAULO | `MORUMBI\|LOCALIZADO_EM\|SAO PAULO` | `SÃO PAULO FUTEBOL CLUBE\|LOCALIZADO_EM\|ESTADIO DO MORUMBI` | *(nenhuma)* |
| PACAEMBU → SÃO PAULO | `PACAEMBU\|LOCALIZADO_EM\|SAO PAULO` | *(nenhuma)* | `PALMEIRAS AND SAO PAULO\|LOCALIZADO_EM\|SANTOS FUTEBOL CLUBE` |
| NEO QUÍMICA ARENA → SÃO PAULO | `NEO QUIMICA ARENA\|LOCALIZADO_EM\|SAO PAULO` | *(nenhuma)* | *(nenhuma)* |

Dry-run do fix proposto (rotear wiki GEO por `extract_geo_localizado_from_wiki_html`):
`reports/geo_canonical_fix_dry_run_048_10h_2.json` → **`full_collision_facts = 0`**, `junk = 0`.

## Causa-raiz

1. **R1/R2 — sujeito/objeto invertidos ou ausentes.** O extrator narrativo produz `LOCALIZADO_EM`
   mas com `SÃO PAULO FUTEBOL CLUBE → ESTADIO DO MORUMBI` (clube→estádio) ou
   `PALMEIRAS… → SANTOS FUTEBOL CLUBE`; e **não** produz `ESTÁDIO → CIDADE`.
2. **R3 — ausência de frase-alvo.** A página PT do **Allianz Parque não contém** verbo de localização
   útil (`localizado` ausente no texto limpo); logo não há como extrair `LOCALIZADO_EM → SÃO PAULO`.
3. **Ambiguidade de estádio (I relevante).** `extract_geo_localizado_from_wiki_html` usa
   `resolve_stadium(texto_inteiro)`; como as páginas citam **estádios irmãos** (Morumbi/Allianz/Neo Química),
   a resolução fica **ambígua → None**, mesmo quando a função é chamada (retorna `[]`).
4. **Ruído estrutural do HTML wiki.** O texto limpo contém artefatos de infobox/JSON/template
   (`"wt":"..."`, `{{#parsoid…}}`), dificultando um casamento limpo de frase.

## Por que não corrigir neste task

- Não há correção **mínima e segura** que atinja `4/4` sem um parser wiki dedicado
  (lead-sentence/infobox, subject pinado por URL, desambiguação de estádio, rejeição de bairro/owner),
  o que sai do escopo "patch mínimo" e reintroduz risco de junk.
- Qualquer atalho (ex.: casar "cidade de São Paulo" sem pinar o estádio) **violaria** o gate de junk
  (bairro/endereço/owner/estado como objeto).

## Proposta para issue dedicado (#048.10H.2.1)

1. `geo_extractor`: aceitar `subject_hint` (estádio do cluster) e exigir **mesma frase** com o sujeito pinado.
2. Preferir a **primeira seção/lead** da página (antes de seções homônimas/tabelas).
3. Desambiguar estádio por URL→sujeito (não pelo texto inteiro).
4. Rejeitar `neighborhood|bairro|district|owner|municipal prefecture|state` como objeto.
5. Dry-run exigido: `full_collision_facts >= 4`, `junk = 0`, antes de qualquer worker.

## Dívida observacional (não bloqueante)

`graph_scoped_gap = -403` (ver `reports/observability_graph_scoped_gap_052_3_1_diagnosis.md`);
`unaccounted_raw=0`, `top_invalid=[]`, `fallback=0`, `verified` estável → **não** é contaminação.

## Invariantes

Nenhum worker; nenhuma escrita em Neo4j/Qdrant; seeds/runtime cognitivo intactos; sem treino; sem force-push.
