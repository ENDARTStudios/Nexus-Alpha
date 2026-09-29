# #048.10L.2 — Análise de falha real (next batch GEO)

**Worker:** run `36617910895` (success, 1 dispatch) · **Pós:** `verified=18` (15→18, +3), `fact_count=413`,
`concept_count=2023`, `graph_scoped_gap=0`, `fact_accounting_status=ok`, `top_invalid_predicates=[]`,
`fallback_promoted_to_graph=0`.
**Resultado fact-level:** 3/5 fortes · 0 junk · sem regressão do lote atual (4/4 mantidos).

## Fatos fortes (3/5 — pt + en + nominatim)

```text
ESTÁDIO OLÍMPICO NILTON SANTOS --LOCALIZADO_EM--> RIO DE JANEIRO   (3 domínios, verified)
MARACANÃ                        --LOCALIZADO_EM--> RIO DE JANEIRO   (3 domínios, verified)
ARENA FONTE NOVA                --LOCALIZADO_EM--> SALVADOR        (3 domínios, verified)
```

## Fatos parciais (2/5)

### BEIRA-RIO → PORTO ALEGRE

```text
Grafo (read-only): sujeito "BEIRA RIO" --LOCALIZADO_EM--> "PORTO ALEGRE"
domínios: pt.wikipedia.org, en.wikipedia.org   (2/3)   verificado=false
```

- **Causa principal — R10_OSM_NO_STRUCTURED_CITY:** o Nominatim de "Estádio Beira-Rio" não trouxe `address.city`
  estruturado; o fallback `display_name_expected_context` foi avaliado com `expected_city` **errado**.
- **Causa contribuinte — wiring:** `scripts/worker_cycle.py::_load_expected_geo_city()` lê apenas
  `reports/geo_expected_facts_048_10H.json` (cidade única = SÃO PAULO) e o usa como fallback OSM para **todo**
  o run. Para o next batch (PORTO ALEGRE/BELO HORIZONTE) o fallback nunca casa → `no_clean_city_evidence`.
- **Causa de medição — R13_CANONICAL_KEY_MISMATCH:** o grafo canoniza o sujeito como `BEIRA RIO` (hífen→espaço),
  mas o registry espera `BEIRA-RIO`; o casamento exato do export fact-level não reconhece o fato (dc exibido 0).
  O fato, porém, existe com 2 domínios.

### MINEIRÃO → BELO HORIZONTE

```text
Grafo (read-only):
  "MINEIRAO" --LOCALIZADO_EM--> "BELO HORIZONTE"   domínios: en.wikipedia.org (1/3)  verificado=false
  "MINEIRAO" --LOCALIZADO_EM--> "RIO DE JANEIRO"   domínios: pt.wikipedia.org (1/3)  verificado=false  (OBJETO ERRADO)
```

- **Causa principal — R1/R3 (infobox em HTML cru):** o worker chama `parser(url, "", html)` — extração **somente**
  via infobox no HTML bruto. Na página PT "Estádio Governador Magalhães Pinto", a janela do label de localização
  capturou **"Rio de Janeiro"** (menção correlata na página), produzindo objeto **errado**.
- **Causa — R10_OSM_NO_STRUCTURED_CITY:** mesma falha de fallback OSM do BEIRA-RIO (expected_city = SÃO PAULO).
- O objeto "RIO DE JANEIRO" não é junk pelo critério literal (Rio é cidade válida), mas é **falso positivo
  semântico unverified** (não promovido, sem CONFIRMA por 3 domínios).

## Fora do escopo GEO (pré-existentes, não causados por este run)

Fatos `LOCALIZADO_EM` narrativos unverified já presentes (ex.: `BOTAFOGO ... --> NEIGHBORHOOD OF BOTAFOGO`,
`SÃO PAULO FUTEBOL CLUBE --> ESTADIO DO MORUMBI`). Nenhum é do caminho GEO dedicado e nenhum é verificado.

## Insumos para #048.10L.3 (não executado aqui)

1. Tornar o fallback OSM **source-scoped por URL/fato** (não usar cidade única do lote atual) — `worker_cycle.py`
   + `geo_extractor.py`, com testes offline.
2. Endurecer a extração por infobox no HTML cru (limitar ao bloco de infobox real / desambiguar "Localização"
   por contexto do sujeito), evitando o falso "RIO DE JANEIRO" no Mineirão.
3. Alinhar a chave canônica do sujeito `BEIRA RIO`/`BEIRA-RIO` (comparação normalizada de hífen) no export/registry.
