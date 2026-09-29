# GEO real-page failure analysis — #048.10H.3

**Run:** `36506930895` (success) · **Classificação:** `PARTIAL_048_10H_3_GEO_PROGRESS`
**Resultado:** `verified_facts_domain_independent 11 → 13`, `unique_predicates 2 → 3`, `facts_with_multi_domain 12 → 16`, `junk = 0`, regressão = false.

## Fatos verificados (inferidos)

| Fato | Domínios | Evidência |
|---|---|---|
| PACAEMBU → SÃO PAULO | pt + en + osm | OSM POST `200` + geo/wikis |
| NEO QUÍMICA ARENA → SÃO PAULO | pt + en + osm | OSM POST `200` + geo/wikis |

O parser dedicado produziu **8/8** triplas wiki (`geo_wiki_triples_canonical = 8`), com
`generic_wiki_noise_suppressed = true` — a página real **colaborou** para 2 fatos.

## Fatos parciais (2 domínios: wiki pt + en)

| Fato | Causa | Código |
|---|---|---|
| ALLIANZ PARQUE → SÃO PAULO | OSM sem tripla: `no_clean_city_evidence` (resultado Nominatim sem `address.city`; fallback `expected_city` não casou no `display_name`) → só pt+en | **R10/R11** (`OSM_NO_STRUCTURED_CITY` / `OSM_AMBIGUOUS_RESULT`) |
| MORUMBI → SÃO PAULO | OSM POST `/api/ingest` retornou `502` transitório → só pt+en | **R9** (`OSM_TRANSIENT_5XX`) |

> Observação honesta: o `validate_geo_expected_facts` reportou `expected_facts_verified = 0`
> porque o `/api/metrics` **não expõe domínios por fato** (evidência fact-level insuficiente) —
> a inferência acima usa `verified 11→13` + os `200`/rejeições por URL no log do worker.

## Não-junk / sem regressão

`unaccounted_raw=0`, `top_invalid_predicates=[]`, `fallback_promoted_to_graph=0`,
`duplicate_cross_domain` subiu (23→29, corroboração real), nenhum objeto proibido
(bairro/endereço/país/estado/coordenada/cláusula/genérico/clube/owner), `Engenho de Dentro` ausente.

## Próximo passo (#048.10H.4)

1. **ALLIANZ**: inspecionar o resultado real do Nominatim para o estádio e ajustar o fallback
   (ex.: aceitar `display_name`/`is_in` quando o estádio é allowlisted e a cidade esperada aparece
   de forma clara) — **sem** relaxar rejeições de bairro/estado/país.
2. **MORUMBI**: retry conservador de POST `/api/ingest` no worker (5xx transitório) para não perder o 3º domínio.
3. Re-run dry-run + #048.10H.4 após correções; **#048.10L permanece congelado**.
