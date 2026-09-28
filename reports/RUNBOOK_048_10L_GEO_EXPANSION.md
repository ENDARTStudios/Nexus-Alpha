# RUNBOOK_048_10L_GEO_EXPANSION

## Pré-condições

1. **#048.10H real** foi executado com sucesso e validado (telemetria viva).
2. O HF Space está no HEAD atual e os campos de telemetria estão presentes
   (`concept_count`, `fact_count`, `run_scoped_gap`, `graph_scoped_gap`).
3. O atlas **#048.10K** encontrou **>= 4** novos `full_collision` GEO
   (`reports/geo_expansion_atlas_048_10k.json`).
4. O next batch registry foi revisado (`reports/geo_expected_facts_next_batch_048_10k.json`).

## Lote candidato (atlas #048.10K)

```text
ESTÁDIO OLÍMPICO NILTON SANTOS --LOCALIZADO_EM--> RIO DE JANEIRO
MARACANÃ --LOCALIZADO_EM--> RIO DE JANEIRO
BEIRA-RIO --LOCALIZADO_EM--> PORTO ALEGRE
MINEIRÃO --LOCALIZADO_EM--> BELO HORIZONTE
ARENA FONTE NOVA --LOCALIZADO_EM--> SALVADOR
```

## Escopo futuro (#048.10L)

- adicionar allowlist/runtime **apenas** para candidatos `full_collision`;
- adicionar seeds pt/en/OSM (Nominatim, ODbL);
- rodar dry-run integrado;
- snapshot AuraDB;
- worker incremental com o gate de telemetria;
- validar expected facts do next batch (`scripts/validate_geo_expected_facts.py` com o registry next);
- **não** treinar.

## Proibições

- **não** aceitar bairro/endereço/país/estado/coordenada/cláusula/genérico como cidade;
- **não** alterar quórum;
- **não** usar Almanaque sem licença;
- **não** rodar worker sem o telemetry gate `OK`;
- WARNING: RSSSF/RSSSF Brasil não participam deste lote; aqui as famílias são Wikimedia + OpenStreetMap.
