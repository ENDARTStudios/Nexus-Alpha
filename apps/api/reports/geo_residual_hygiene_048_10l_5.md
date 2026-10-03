# #048.10L.5 — Inventário de resíduos GEO (read-only)

Fonte: `scripts/audit_geo_residual_hygiene.py` → `reports/geo_residual_hygiene_048_10l_5.json`.

## Resíduos não verificados (`LOCALIZADO_EM`, verified=false)

```text
11 resíduos não verificados; 4 com objeto proibido (club/address/neighborhood);
1 wrong-city conhecido: MINEIRAO -> RIO DE JANEIRO (alvo da higiene).
```

### Alvo removido

```text
MINEIRAO --LOCALIZADO_EM--> RIO DE JANEIRO
chave: mineirao|LOCALIZADO_EM|rio de janeiro
verified=false · confirmacoes=1 (pt.wikipedia.org) · esperado=BELO HORIZONTE
not_in_expected_registry · no_verified_relationships · safe_to_remove=true
```

### Outros resíduos (NÃO removidos neste ciclo — fora da meta primária)

Ruído narrativo legado (ex.: `BOTAFOGO ... -> NEIGHBORHOOD OF BOTAFOGO`,
`SANTOS FUTEBOL CLUBE -> MONTE SERRAT`, `SAO PAULO COMPROU -> RUA ...`), todos
unverified (dc=1). Ficam documentados para higiene opcional futura.

## Auditoria dos verificados

```text
verified_geo_facts_total = 9 (4 lote atual + 5 next batch)
lote_atual_4_preserved = true
next_batch_5_preserved = true
junk_verified_objects = 0
forbidden_verified_objects = 0
```
