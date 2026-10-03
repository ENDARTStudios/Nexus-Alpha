# 054.2.R1 decision packet — Space boot graph readiness

## Resumo executivo
O boot-race está **confirmado empiricamente e com código**: o Space atende `/api/metrics`
com HTTP 200 e contadores zerados + `hebbian=False` durante o wake-up do AuraDB pausado
(15-20s), porque `graph_snapshot()` engole falhas (2 retries de 0,5s) e o endpoint não
possui gate de readiness. Nenhum dano real — a baseline volta sozinha — mas o falso
diagnóstico ("grafo perdido") já custou ciclos e gerou a dívida #054.2.

## Sintoma
1ª leitura pós-restart/inatividade: `status=online`, contadores zerados,
`hebbian_consistency_check=false`. 15-20s depois: baseline íntegra, sem intervenção.

## Evidência
- Telemetria: sampler dedicado (`diagnose_054_2_r1_boot_readiness.py`) capturou a
  transição (amostra 1 = zeros; amostras 2+ = baseline) — `.autonomous/054_2_r1/metrics_timeline.json`.
- Logs/histórico: 3+ ocorrências documentadas (worker incident #048.10M.1.2, ciclos R3/R4/R1).
- Código: `graph_connector.graph_snapshot` → `except Exception → empty(ok:False)`;
  `ensure_schema` → engole; `/health` estático — nenhum gate.

## Root cause mais provável
**H4+H5+H2+H6 combinadas**: AuraDB free pausa por inatividade → wake-up transitório →
fallback silencioso de disponibilidade → zeros servidos como métrica válida sem flag de boot.

## Opções de correção (ver `054_2_r1_readiness_patch_options.md`)
- **A — Cliente-side warm-up apenas**: já em prática; formalizar no `check_space_telemetry`.
- **B — Readiness endpoint `/api/ready`**: gate formal; altera runtime.
- **C — Metrics booting state (`graph_ready: false`)**: aditivo; recomendada.
- **D — Startup warm-up**: reduz janela; risco de boot fail se Neo4j fora.
- **E — Cache stale explícito**: rejeitada para o tamanho do problema.
- **F — Congelar e escalar incidente de infra**: se o wake-up passar a falhar de verdade.

## Recomendação conservadora
**C (aditivo) + A (formalizado)** em um task futuro único `#054.2.R2`:
1. `graph_ready` no payload de `/api/metrics` quando `snapshot["ok"]=False`;
2. `check_space_telemetry.py` com backoff (3×15s) antes de declarar drift;
3. testes T1-T6 do plano anexo. Sem deploy automático — PR + CI + GO.

## Riscos
- Não corrigir: falso diagnóstico recursivo (já custou investigações em R3/R4/R1).
- Corrigir (R2): risco mínimo — campo aditivo.

## Próximo task, se aprovado
`#054.2.R2` — implementação governada (R2+A), com PR, testes T1-T6, CI, **sem deploy automático** (o Space só recebe no deploy autorizado seguinte).

## Não executado
Nenhuma alteração de código; nenhum deploy; nenhum worker; nenhum ingest;
nenhuma escrita em grafo; nenhum treino.
