# #048.10L.5 — Execução da higiene residual GEO

**Alvo:** `MINEIRAO --LOCALIZADO_EM--> RIO DE JANEIRO` (unverified, dc=1).
**Snapshot (Fase D):** `.autonomous/048_10l_5/aura_snapshot_pre_hygiene.json`
(nodes=5790, rels=4145, Fato=413, verified=20) — imediatamente antes do delete.
**Dry-run:** `.autonomous/048_10l_5/hygiene_dry_run.json` → 1 candidato, `safe_to_remove=true`,
`abort_reasons=[]`, `would_delete_fact_count=1`, `would_change_verified_count=0`, `would_touch_qdrant=false`.

**Gate de execute:** passou (snapshot flag, 1 candidato, safe, sem abort).
**Execute:** `{"status":"DELETED","deleted_fact_count":1,"still_present":false}`.

## Pós-delete (read-only)

| Verificação | Antes | Depois |
|---|---:|---:|
| resíduo MINEIRAO->RJ presente | sim | **não** |
| verified_facts_domain_independent | 20 | **20** |
| facts_with_multi_domain | 21 | **21** |
| fact_count | 413 | **412** |
| lote atual 4/4 | preserved | **preserved** |
| next batch 5/5 | preserved | **preserved** |
| graph_scoped_gap | 0 | **0** |
| fact_accounting_status | ok | **ok** |
| unaccounted_raw | 0 | **0** |
| top_invalid_predicates | [] | **[]** |
| fallback_promoted_to_graph | 0 | **0** |

**Nenhum fato verificado foi perdido. Nenhuma entidade compartilhada foi tocada**
(DETACH DELETE removeu apenas as arestas do próprio `:Fato`).

**Rollback manual (se autorizado):** recriar o `:Fato {chave:'mineirao|LOCALIZADO_EM|rio de janeiro'}`
a partir do snapshot + religar `CONFIRMA`/`MINERADO_DE`. Não executado.
