# #048.10M — Plano de lotes futuros (apenas planejamento)

> Nada aqui é executado neste ciclo. Cada lote exige aprovação do Operador + gates.

## Sequência recomendada

```text
#048.10M.1 — DEFENDEU batch piloto
  tamanho: 6-10 candidatos low-risk (recomendado 10)
  meta: verified 20 -> 26-30, se todos verificarem
  gates: registry próprio, dry-run offline full_collision, source policy, snapshot,
         worker único, export fact-level strong, validate, auditorias, gate de treino

#048.10M.2 — DEFENDEU batch extensão
  tamanho: 8-12 candidatos
  meta: verified -> ~35-42, se seguro

#048.10M.3 — DEFENDEU/GEO híbrido ou nova família ontológica
  apenas se M.1/M.2 fecharem sem junk

#048.10N — eventual DISPUTOU/POSSUIR
  somente após issue separado de predicate_mapper/extractor/span_validator
  NÃO executar neste plano
```

## Gates obrigatórios por lote
1. registry `expected_facts` separado; 2. dry-run offline prevendo full_collision e 0 junk;
3. `check_space_telemetry` OK; 4. `graph_scoped_gap=0`; 5. `fact_accounting_status=ok`;
6. snapshot; 7. baseline; 8. worker manual único; 9. pós-métricas; 10. export fact-level strong;
11. `validate_geo_expected_facts`/equivalente; 12. auditorias read-only; 13. gate de treino;
14. **não treinar**; 15. **não escalar** próximo lote se junk/regressão.

## Projeção conservadora para treino
```text
records_total = 20 < 50 -> treino continua fechado
DEFENDEU sozinho provavelmente NÃO atinge 50; serão necessários múltiplos lotes e talvez famílias futuras.
environment_gate=false permanece bloqueante mesmo com volume.
```
