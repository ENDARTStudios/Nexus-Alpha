# GEO failure reconciliation #048.10H.4

**Run novo:** `36509850003` (success) · **Run reconciliado:** `36506930895`
**Resultado:** 4/4 GEO verificados com **strong evidence** (`reports/geo_fact_level_domains_048_10h_4.json`).

## Allianz Parque

- **causa definitiva:** `A3_OSM_NAME_MISMATCH` — o OSM renomeou o estádio para **"Nubank Parque"**
  (sponsor). O extrator resolvia o estádio pelo nome → falhava → `no_clean_city_evidence`.
- **evidência:** probe read-only Nominatim `q=Allianz Parque` → `name="Nubank Parque"`,
  `type=stadium`, `address.city=São Paulo`, `state=São Paulo`, `country=Brasil`.
- **OSM structured city ausente?** Não — havia `address.city=São Paulo`.
- **display_name continha São Paulo?** Sim.
- **ambiguidade?** Não.
- **ação corretiva permitida (aplicada):** alias estrito `"nubank parque" -> ALLIANZ PARQUE`
  (`geo_extractor.STADIUM_ALIASES`).

## Morumbi

- **causa definitiva:** `A6_INGEST_TRANSIENT_5XX_POST`.
- **502 foi GET OSM ou POST ingest?** **POST `/api/ingest`** — a linha
  `Resposta [https://nominatim...Estadio%20do%20Morumbi]: 502` é a resposta do POST de ingest
  (não do GET Nominatim, cujo parse havia retornado 3 triplas).
- **evidência sanitizada:** log run `36506930895` — `Resposta [...Morumbi...]: 502` e
  `Resposta [...Morumbi_Stadium]: 502`.
- **retry seguro?** Sim — o grafo persiste por **MERGE** na chave canônica (`app.py` → `graph_connector`),
  logo reenviar o mesmo payload é idempotente.
- **idempotência verificada?** Sim (MERGE por `chave`; teste `tests/test_geo_retry_safety.py`).
- **ação corretiva permitida (aplicada):** retry limitado (2 tentativas, sleep 5/10s) em `worker_cycle`
  para POST `/api/ingest` apenas em 502/503/504.

## Pacaembu

- **status:** verificado (pt+en+osm) — sem falha.

## Neo Química Arena

- **status:** verificado (pt+en+osm) — sem falha.

## Resultado final (fact-level strong, Neo4j read-only)

```text
ALLIANZ PARQUE --LOCALIZADO_EM--> SÃO PAULO     dc=3  (pt, en, nominatim)
MORUMBI --LOCALIZADO_EM--> SÃO PAULO            dc=3  (pt, en, nominatim)
PACAEMBU --LOCALIZADO_EM--> SÃO PAULO           dc=3  (pt, en, nominatim)
NEO QUÍMICA ARENA --LOCALIZADO_EM--> SÃO PAULO  dc=3  (pt, en, nominatim)
```

Sem junk, sem regressão. `verified 13 -> 15`.
