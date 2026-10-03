# #053.2 — Publisher-family telemetry for OpenStreetMap

**Status:** `PARTIAL_053_2_LOCAL_READY_LIVE_PENDING`
**Worker executado:** NÃO · **Deploy do Space:** NÃO (sem mudança de runtime) · **Treino:** bloqueado

## Contrato de famílias

- **Wikimedia:** `*.wikipedia.org` (pt/en/outros) → **mesma família** `Wikimedia`.
- **RSSSF:** `rsssf.org`/`www.rsssf.org`/`rsssfbrasil.com`/`www.rsssfbrasil.com` → família `RSSSF`
  **com warning** `RSSSF_AND_RSSSF_BRASIL_SAME_FAMILY_SUSPECTED`.
- **OpenStreetMap:** `openstreetmap.org`/`nominatim.openstreetmap.org`/`overpass-api.de`/`overpass.kumi.systems`
  → família independente **geográfica/open data** `OpenStreetMap`.
- **Unknown:** qualquer outro domínio **não** conta como família independente.
- Warning `OPENSTREETMAP_IS_GEOGRAPHIC_OPEN_DATA_NOT_NEWS_EDITORIAL` registra a natureza geográfica.
- Warning `WIKIMEDIA_MULTIPLE_LANGUAGES_NOT_INDEPENDENT` registra que idiomas não são independência editorial.

## Onde era derivado antes

`scripts/evaluate_training_gate.py::_publisher_family` — mapa `_PUBLISHER_FAMILY` tinha só RSSSF
(e um fallback por substring Wikimedia). Domínios OSM caíam no **nome bruto do domínio**
(`nominatim.openstreetmap.org`), inflando/rotulando errado a família.

## Resultado local

```text
publisher_family_count      = 3
effective_publisher_count   = 3
publisher_family_distribution = { "Wikimedia": 30, "OpenStreetMap": 4, "RSSSF": 11 }
publisher_independence_warnings = [
  "OPENSTREETMAP_IS_GEOGRAPHIC_OPEN_DATA_NOT_NEWS_EDITORIAL",
  "RSSSF_AND_RSSSF_BRASIL_SAME_FAMILY_SUSPECTED",
  "WIKIMEDIA_MULTIPLE_LANGUAGES_NOT_INDEPENDENT"
]
```

Fonte: helper `scripts/publisher_family_telemetry.py` (read-only, sem cognição) +
`evaluate_training_gate.py` (agora emite `effective_publisher_count` e `publisher_independence_warnings`).

## Resultado vivo

- **deploy tentado:** não (não houve alteração de `app.py`/`graph_connector.py`).
- **`/api/metrics` vivo:** **não expõe** `publisher_family_count`/`distribution` (`LOCAL_TELEMETRY_READY_LIVE_NOT_UPDATED`).
- Para expor no vivo seria necessário alterar `app.py`/`src/database/graph_connector.py` (calcular famílias
  a partir de `FonteWeb.domain` do grafo) e **redeploy** do Space — **fora do escopo mínimo** deste ciclo.

## Impacto no gate

- `publisher_independence_gate`: **true** (publishers distintos ≥ 3 / família ≥ 3).
- `diversity_gate`: **false** (monoculture_object; records < 50).
- `training_allowed` / `training_recommended`: **false** (inalterados).

## Dívidas

- **#052.3.1** — `graph_scoped_gap = -404` (telemetria contábil), separada.
- **#053.2.1** — expor `publisher_family_*` no `/api/metrics` vivo (requer alteração de runtime + redeploy seguro).
- **#048.10L** permanece **congelado** até telemetria estável + dry-run do next batch.

## Segurança

Nenhum worker; nenhuma escrita em Neo4j/Qdrant/ingest; nenhuma seed; quórum 3; sem force-push;
anti-leak clean. `.autonomous/053_2/**` não commitado.
