# O3 — Política de custódia de snapshots do grafo

## Artefatos e guarda

| Artefato | Onde vive | Retenção | Commitado? |
|---|---|---|---|
| Backup de referência | `backups/neo4j_aura_final_20261003/` (8ed58ea) | permanente | ✅ sim (gzip não; JSON canônico) |
| Backup semanal | `backups/auto_weekly/` (workflow `db-backup.yml`, domingo 00:00 UTC) | sobrescrito a cada execução; histórico no git | ✅ sim, comprimido (`graph_export.json.gz`, ~413 KB) |
| Snapshots de janela (pré/pós-worker) | `backups/snapshot_pre_*` / `snapshot_post_*` **locais, não commitados** | descartáveis — são redundantes com o backup semanal + backup de referência | ❌ não (payload grande; ~4-6 MB/cópia) |
| Manifest | sempre junto do export (`manifest.json` com SHA256 e contagens) | igual ao pai | ✅ |

## Ferramenta e autoridade

- **Ferramenta única:** `apps/api/scripts/aura_final_backup.py` (`export` read-only / `restore --keep-eid` / `verify` / `cleanup`).
- **Executar restore é decisão do Operador** (nunca automático): `restore → verify (OK obrigatório) → cleanup`.
- **Prova de integridade:** `gunzip -c graph_export.json.gz | sha256sum` deve bater com `manifest.json → files["graph_export.json"]`.

## Proibições

1. **Nenhum payload de snapshot grande não comprimido commitado** (JSON cru de export completo vai para o repo somente como backup de referência deliberado, com registro no SPRINT).
2. **Nenhum restore automático** por worker/CI/cron.
3. **Nenhuma escrita no grafo de origem** durante export (todas as queries do modo `export` são MATCH/RETURN).

## Drill de verificação (recomendado: trimestral)

1. Baixar o último `backups/auto_weekly/`.
2. `restore` num Neo4j efêmero local (`neo4j:5` docker).
3. `verify` — deve ser OK/OK.
4. `cleanup` + destruir o container.
