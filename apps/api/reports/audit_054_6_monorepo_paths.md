# #054.6 — Auditoria de impacto do monorepo split (read-only)

Data: 2026-10-07 · Referência: main pós `5ae17e2` · Método: inspeção estática + provas de execução acumuladas na migração #054.7. Nenhuma reversão, nenhum patch aplicado.

## Resultado consolidado: SEM BLOQUEIOS RUNTIME

| Consumidor | Estado | Evidência |
|---|---|---|
| ai-validation.yml | OK | `working-directory: apps/api` (pytest + anti-leak) e `apps/web` (policy test); `PYTHONPATH: apps/api` |
| ai-cron.yml | OK | `working-directory: apps/api` (2 steps) + PYTHONPATH |
| db-backup.yml | OK (reescrito em `5d08659`) | `cd apps/api`; export real contra Railway — run `37688323561` SUCCESS, 6461 nós/4526 rels, SHA256 verificado |
| deploy_hf_space_safe.py | OK | `ROOT = file-anchored` → apps/api; ALLOW_PATTERNS relativos (`app.py`, `src/**`, `config/**`); **provado**: UPLOAD_OK 67 arquivos (migração); EXCLUDE_PATTERNS bloqueia `.env*` |
| deploy_hf_space.py | OK | mesmo ROOT; `folder_path=ROOT`, README_HF/Dockerfile.hf mapeados |
| worker_cycle.py | OK | paths file-anchored (`parent.parent / "reports"`) — CWD-independente |
| check_space_telemetry.py | OK | sem escrita CWD-relative; flag `--wait-ready` da PR #1 é additiva |
| dashboard (streamlit) | OK | sem caminhos problemáticos |
| docker-compose.yml | OK | `context: ./apps/api` + `./apps/web`; volumes `./apps/api/src`, `./apps/api/config` |
| tests (812 passed) | OK | âncoras `parents[1]` resolvem apps/api; suite verde local + CI success |
| config/settings.yaml | OK | CWD-relative de apps/api; fallback dev local (`neo4j-db`) intencional |
| README.md | OK | árvore + comandos pós-split corretos (`apps/api`, `apps/web`, Vercel Root Directory) |
| .env local | OK | `apps/api/.env` com NEO4J_* → Railway (#054.7) |

## Divergências encontradas (apenas docs descritivos — sem impacto runtime)

| Arquivo | Linhas | Problema | Correção proposta (não aplicada) |
|---|---|---|---|
| docs/03-development-process/SETUP.md | 77 | `python src/frontend/mock_server.py` (hoje: `apps/api/scripts/mock_server.py`) | atualizar caminho |
| docs/02-architecture-design/STYLE_GUIDE.md | 39, 42 | `src/frontend/`, `src/app/` | prefixar `apps/web/` |
| docs/02-architecture-design/DESIGN.md | 3, 41, 54–58 | idem | idem |
| docs/02-architecture-design/ARCHITECTURE_PIPELINE.md | 60, 62 | idem | idem |
| ARCHITECTURE.md (raiz) | — | movida para docs/02 no enforce root-as-temple (`1cae5d9`) | nada a fazer (README não a referencia) |

## Provas de execução acumuladas (#054.7)

- `deploy_hf_space_safe.py`: UPLOAD_OK ×2 (67 arquivos) — allowlist íntegra pós-split; Space servindo `/api/metrics` público 2136/598/20 no Railway.
- `db-backup.yml` real: run `37688323561` SUCCESS; `backups/auto_weekly/graph_export.json.gz` com integridade SHA256 OK contra o manifest.
- Space→Railway: leitura pelas queries exatas do `graph_connector` (2136/598/20).

## Conclusão

Nenhum consumidor de caminho quebrado pós-split. Divergências restritas a docs de design histórico (4 arquivos). **Plano de ajuste (baixa prioridade, docs-only):** uma task única atualizando SETUP.md + os 3 docs de design para os caminhos `apps/web/…` e `apps/api/scripts/mock_server.py`.
