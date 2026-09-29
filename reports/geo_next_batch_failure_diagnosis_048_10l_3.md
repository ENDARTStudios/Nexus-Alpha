# #048.10L.3 — Diagnóstico determinístico (Beira-Rio e Mineirão)

Fontes: log sanitizado do worker `36617910895` (`.autonomous/048_10l_2/logs`), dump read-only
(`.autonomous/048_10l_2/geo_facts_dump_post.json`), código + fixtures. Sem rede.

## Causas-raiz (taxonomia)

```text
B1_EXPECTED_CITY_HARD_CODED            -> SIM (fixo SÃO PAULO em worker_cycle)
B2_OSM_NO_STRUCTURED_CITY_FOR_POA_OR_BH -> SIM (fallback bloqueado pelo B1)
B3_INFOBOX_CROSS_CONTAMINATION          -> SIM (Mineirão PT capturou "Rio de Janeiro")
B4_SUBJECT_HYPHEN_NORMALIZATION_MISMATCH-> SIM (grafo "BEIRA RIO" vs registry "BEIRA-RIO")
B7_AUDIT_STALE_SPLIT_GEO_URLS           -> SIM (audit antigo com unpack de 2)
B8_CANONICAL_TO_FACT_GAP_FORMULA        -> SIM (scope mismatch, ver doc dedicado)
```

## BEIRA-RIO → PORTO ALEGRE

| Pergunta | Resposta |
|---|---|
| wiki PT produziu tripla? | SIM (`BEIRA RIO\|LOCALIZADO_EM\|PORTO ALEGRE`) |
| wiki EN produziu tripla? | SIM (idem) |
| OSM produziu tripla? | **NÃO** (`no_clean_city_evidence`) |
| chave canônica emitida | `BEIRA RIO\|LOCALIZADO_EM\|PORTO ALEGRE` (grafo) |
| mismatch `BEIRA RIO` vs `BEIRA-RIO`? | **SIM** → export fact-level casou 0 (dc=0 exibido) |
| OSM teve `address.city`? | **NÃO** |
| `display_name` tinha Porto Alegre? | Provável SIM, mas fallback avaliado com `expected_city=SÃO PAULO` (homônimo) → pulado |
| `expected_city` correto? | **NÃO** (B1: cidade única SÃO PAULO para todo o run) |
| **causa definitiva** | **B1 + B2** (dominante) e **B4** (medição) |

## MINEIRÃO → BELO HORIZONTE

| Pergunta | Resposta |
|---|---|
| wiki PT produziu tripla? | SIM, porém **objeto ERRADO** `RIO DE JANEIRO` |
| wiki EN produziu tripla? | SIM (`MINEIRAO\|LOCALIZADO_EM\|BELO HORIZONTE`) |
| OSM produziu tripla? | **NÃO** (`no_clean_city_evidence`) |
| por que PT capturou "Rio de Janeiro"? | worker chama `parser(url, "", html)` → extração **só de infobox em HTML cru**; janela do label de localização pegou menção correlata |
| infobox/link/tabela/redirect/frase? | **infobox em HTML cru** (B3) |
| `expected_city` correto? | **NÃO** (B1) |
| OSM teve `address.city`? | **NÃO** |
| **causa definitiva** | **B3 + B1/B2** |

## Correções aplicadas (#048.10L.3)

1. **B1:** `resolve_expected_geo_city(url)` source-scoped (wiki por subject pinado; Nominatim por `q`
   resolvido na allowlist) → `worker_cycle` resolve **por URL/fato**; nunca herda cidade.
2. **B2:** fallback OSM `display_name_expected_context` agora só aceita a cidade esperada, rejeita
   conflito (segunda cidade/estado/road type/`address.city` divergente).
3. **B3:** parser wiki aceita `expected_city`; infobox/sentença só emitem a cidade esperada; labels e
   tokens proibidos (owner/address/estado/capacity/...) rejeitados; infobox cross-city rejeitado.
4. **B4:** alias `beira rio`→`BEIRA-RIO` + teste de paridade de chave (hífen vs espaço).
5. **B7:** `audit_geo_worker_dry_run` atualizado ao contrato 3-vias + fetcher `(url, allowlist, expected_city)`.
6. **B8:** diagnosticado como scope mismatch (ver `reports/canonical_to_fact_gap_diagnosis_048_10l_3.md`).

Dry-run de fechamento: `reports/geo_next_batch_closure_dry_run_048_10l_3.json` → **5/5 full collision**.
