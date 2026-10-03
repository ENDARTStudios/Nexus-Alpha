# 054.2.R1 — Evidência de logs/histórico (boot-race)

**Classificação: L1 — BOOT_RACE_CONFIRMED (por telemetria documentada em 3+ ciclos e reprodução controlada neste ciclo)**

## Ocorrências documentadas (todas com o mesmo padrão)

| Ciclo | Observação | Recuperação |
|---|---|---|
| **#048.10M.1.2** (worker incident, 2026-10-02) | 1ª leitura pós-restart do Space: `verified=0, fact=0, concept=0, hebbian=False` | re-leitura em ~20s: baseline íntegra (`defendeu_pilot_worker_incident_048_10m_1_2.md`) |
| **R4** (#048.10M.1.2.R4, 2026-10-02) | 1ª leitura pós-boot-race idem | warm-up restaurou; registrado como risco operacional |
| **R3** (#048.10M.1.2.R3, 2026-10-03) | primeira leitura retornou zeros/hebbian=False | warm-up read-only restaurou baseline |
| **Este ciclo (R1)** | reprodução controlada com sampler: **amostra 1 = `cold_boot_zeros` (verified=0, hebbian=False); amostras 2-12 = baseline íntegra** (15s entre amostras) | `.autonomous/054_2_r1/metrics_timeline.json` |

## Padrões procurados nos logs (§5 do packet)
- `ServiceUnavailable`/`TransientError` do Neo4j: **não observados nos logs locais** (o Space não expõe logs ao Doer; a evidência é a telemetria).
- A assinatura consistente em todos os ciclos: `status: online` + contadores zerados + `hebbian_consistency_check: false` → depois baseline completa.

## Leitura
- O Space **nunca fica indisponível**: HTTP 200 em todos os ciclos.
- O que falha é a **conexão/query com o AuraDB** durante a janela de wake-up do cluster pausado (free tier pausa por inatividade).
- `graph_snapshot` absorve a falha (2 retries de 0,5s — insuficiente para o wake-up de dezenas de segundos) e retorna zeros silenciosos.

## Conclusão
`L1 — BOOT_RACE_CONFIRMED`: reproduzido empiricamente neste ciclo com o sampler dedicado (`diagnose_054_2_r1_boot_readiness.py`), consistente com as 3 ocorrências históricas. Não há evidência de state inconsistente real — apenas janela transitória sem sinalização de readiness.
