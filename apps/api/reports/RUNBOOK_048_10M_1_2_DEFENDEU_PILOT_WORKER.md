# RUNBOOK_048_10M_1_2_DEFENDEU_PILOT_WORKER

## Objetivo
Executar futuramente o worker piloto DEFENDEU, **apenas após aprovação
explícita do Operador**. Este runbook NÃO autoriza execução — #048.10M.1
apenas preparou o terreno (dry-run `ready_for_worker=true`).

## Pré-condições (checklist obrigatório antes do worker)
1. #048.10M.1 dry-run prevê full_collision para todos os 7 candidatos selecionados.
2. junk_objects = 0 (provado no dry-run).
3. forbidden_objects = 0 (provado no dry-run).
4. evidence_strength = REAL_PAGE_READONLY ou LOCAL_EXISTING_EVIDENCE para todos
   (`reports/defendeu_pilot_expected_facts_048_10m_1.json`).
5. Nenhuma seed ativa foi alterada (`config/seed_clusters.yaml` intocado).
6. Nenhum expected fact foi injetado no grafo (registry é planejamento).
7. `check_space_telemetry` OK.
8. verified_facts_domain_independent = 20.
9. fact_count = 412.
10. concept_count = 2023.
11. graph_scoped_gap = 0.
12. fact_accounting_status = ok.
13. publisher_family_count = 3.
14. **Snapshot AuraDB** (backup real, não o simulado — ver `docs/BACKUP_DR.md`).
15. Baseline capturado (metrics_pre).
16. Worker manual **único** (`gh workflow run`), sem cron concorrente.
17. Pós-métricas capturadas (metrics_post).
18. Export fact-level strong.
19. Validar expected facts contra
    `reports/defendeu_pilot_expected_facts_048_10m_1.json`
    (cada candidato deve virar `:Fato` verificado com 3 domínios).
20. Não treinar (gate de treino segue fechado: records 20+7=27 < 50).
21. Não escalar próximo lote se houver junk ou regressão.

## Expectativa conservadora (pós-worker)
```text
verified_facts_domain_independent: 20 -> 26-30
records_total: 20 -> 26-30
unique_predicates: 3
non_VENCEU_ratio: sobe acima de 0.50 (0.67 previsto no dry-run)
top_predicate_share: cai abaixo de 0.50 (0.33 previsto no dry-run)
publisher_family_count: 3
graph_scoped_gap: 0
fact_accounting_status: ok
```

## Bloqueios automáticos
- Treino continua **false** se `records_total < 50` ou `environment_gate=false`.
- Next-next batch **congelado** até validação fact-level deste piloto.
- Se qualquer expected fact não virar fato verificado: registrar por candidato
  (motivo: página não corrobora / extração falhou / quórum insuficiente) e
  NÃO reverter para tentativa manual — o conhecimento entra só pelo pipeline.

## Rollback
- Último SHA conhecido bom do Space: `7ebdcec` (pós-#054.1).
- Dados: snapshot AuraDB pré-worker (pré-condição 14). Sem reset automático.
- Sem force-push; correções em commit novo.
