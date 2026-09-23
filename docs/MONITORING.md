# 📈 Monitoring — Saúde Contínua (Nexus-Alpha)

Sem stack de alerta pago: o monitoramento combina **endpoints de saúde**,
**GitHub Actions** e **métricas de produto** (`/api/metrics`). Este doc é o
runbook de observação diária/semanal.

---

## 1. Sinais vitais (o que vigiar)

| Sinal | Onde | Saudável |
|---|---|---|
| Liveness do core | `GET /health` | 200 (mesmo degradado, corpo explica) |
| Consistência do grafo | `/api/metrics → cognitive_health.hebbian_consistency_check` | `true` |
| Persistência episódica | `episodic_persistence_rate` | ≥ 0.95 |
| Pressão de retenção | `retention_pressure` | low/medium (high = investigar poda) |
| Contabilidade de ingest | `unaccounted_raw` | 0 (constante) |
| Gap canônico | `canonical_to_fact_gap` | ≤ 5 |
| Verificação real | `facts_with_two_or_more_domains`, `duplicate_cross_domain` | monitorar evolução (alvo > 0) |
| Qualidade de extração | `top_invalid_predicates` | vazio |
| Quarentena | bloco `quarantine` | crescendo com motivos legítimos |
| Worker | `Actions → ai-cron.yml` | verde a cada 6h |
| Backups | `Actions → db-backup.yml` + `backups/` | 1 snapshot/semana |

## 2. Rotinas

### Diária (ou a cada ciclo 6h, automatizável)
1. Último run do cron verde? (e-mail do GitHub já notifica falha.)
2. `GET /health` e olhada rápida em `/api/metrics`.

### Semanal
1. `retention_pressure` e crescimento da quarentena.
2. Backup do domingo presente e JSON válido.
3. AuraDB ativo (free tier pausa por inatividade —DR-1).

### Por sprint
1. Auditorias read-only: `scripts/audit_post_clean.py`,
   `scripts/audit_cross_source.py`.
2. Comparação baseline/post quando houver mudança de pipeline; registrar em
   `SPRINT.md`.

## 3. Alertas de baixo custo (opcional)

- **Actions:** ativar notificações de falha (padrão) — é o alerta principal
  do worker e dos backups.
- **Uptime externo:** cron próprio no Actions ou serviço free batendo em
  `/health` a cada N minutos e abrindo issue em falha.
- **Limiar de métrica:** script simples que consulta `/api/metrics` e falha
  (issue/e-mail) quando `hebbian_consistency_check=false` ou
  `unaccounted_raw > 0` persistente.

## 4. Troubleshooting guiado

| Sintoma | Diagnóstico | Ação |
|---|---|---|
| `episodes = 0` pós-restart | Neo4j fora | DR-1 ([`BACKUP_DR.md`](./BACKUP_DR.md)) |
| `hebbian_consistency_check = false` | queda do grafo durante consolidação | verificar AuraDB; reabrir conexão; contadores se re-derivam do grafo |
| `retention_pressure: high` | ingest alto/poda falhou | checar `prune_episodes` no ciclo; volume de seeds |
| `unaccounted_raw > 0` | payload não reconciliado | inspecionar log do worker + contadores; abrir issue com número |
| Chat lento | grafo frio/Qdrant fora | verificar Qdrant; fallback in-memory é mais lento; considerar smoke L3 |
| Worker vermelho seguido | fonte bloqueando ou refino rejeitando tudo | ler motivos (`rejection_reasons`); validar seeds (URLs 200) |
| Space "acordando" lento | free tier hiberna | aceitável; proxy retorna erro temporário → frontend já cobre com retry |

## 5. Contratos de resposta para suporte (auto-diagnóstico)

1. **"O site está sem dados":** primeiro `db_status`/`source` no payload —
   se `volatile`/`demo-memory`, é grafo fora; siga DR-1.
2. **"A métrica caiu":** checar se foi correção de honestidade (#049: URL→domínio)
   — história em [`RESEARCH.md`](./RESEARCH.md) antes de abrir incidente.
3. **"Ingest falhou":** token/payload/tamanho → §3 de [`ERROR_HANDLING.md`](./ERROR_HANDLING.md).

## 6. Registro

Incidentes e achados de monitoramento relevantes viram apêndice em
`SPRINT.md`; padrões recorrentes viram itens em [`TASKS.md`](./TASKS.md).
