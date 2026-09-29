# OSM Neo Química failure reconciliation (#048.10H.2.1)

## Causa observada

Duas falhas **distintas e não conflitantes** no worker #048.10H (run `36499101812`):

- **`no_clean_city_evidence` = 1** → refere-se ao estádio **ALLIANZ PARQUE**: o resultado do
  Nominatim não trouxe `address.city` e o display_name não resolveu cidade allowlisted
  → `fetch_and_extract_geo` retornou 0 triplas para essa URL (`osm_json_parsed=1`, `geo_triples_raw=0`).
- **`502`** → refere-se a um POST `/api/ingest` do **NEO QUÍMICA ARENA** (`Resposta [...Neo%20Quimica%20Arena]: 502`)
  — erro **transitório** de gateway, não de parse.

Telemetria do worker: `{"osm_urls_seen":4,"osm_urls_fetched":4,"osm_json_parsed":4,"geo_triples_raw":3,"geo_triples_canonical":3,"rejection_reasons":{"no_clean_city_evidence":1}}`.

## Evidência

- log run `36499101812`: `telemetria GEO` acima; `Resposta [https://nominatim...Neo%20Quimica%20Arena]: 502`;
  respostas 200 com `entities_processed:1` para Morumbi/Pacaembu.
- Probe read-only (3 requisições, orçamento mínimo) em `.autonomous/048_10h_2_1/osm_neo_probe_summary.json`.

## Decisão

- **fallback seguro necessário:** **SIM** (implementado source-scoped:
  `display_name_expected_context` — só aceita a cidade já esperada pelo cluster; nunca infere bairro/estado/país).
- **retry 5xx necessário:** **SIM** (implementado: `fetch_nominatim_json(..., retries=2)`, sleep 5s, sem retry para 403/429).
- **candidato permanece elegível:** **SIM** (Neo Química Arena → SÃO PAULO).

> Legenda: `no_clean_city_evidence` = Allianz (parse); `502` = Neo Química (rede) — reconciliado.
