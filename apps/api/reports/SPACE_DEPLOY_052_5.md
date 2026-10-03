# SPACE_DEPLOY_052_5

**Data:** 2026-09-28
**Objetivo:** redeploy seguro do HF Space para o código do `main` (upload allowlisted, sem git push).

## Resultado

**`SUCCESS_052_5_SPACE_REDEPLOYED_TELEMETRY_READY`**

| Item | Valor |
|---|---|
| HEAD GitHub (pré-task) | `d5a31eb` |
| Space ID | `endartstudios/nexus-alpha` |
| Space SHA **antes** | `85355c6d0e32651eebe4acdf1eb7c7103f6fc245` (`2026-09-25T03:03:55Z`) |
| Space SHA **depois** | `3aa1ad22…` (`lastModified=2026-09-28T22:30:33Z`) |
| Build stage | `RUNNING` |
| Upload | **OK** (79 arquivos allowlisted) |

## Método

O repo do Space é um **snapshot de deploy** com histórico próprio (ver `SPACE_SYNC_052_4.md`);
portanto o caminho correto é **upload de subconjunto**, não `git push`.

- Script existente `scripts/deploy_hf_space.py`: allowlist (`app.py`, `src/**`, `config/**`,
  `requirements*.txt`) — mas sem dry-run nem scan anti-leak → classificado **SAFE-ISH**.
- Criado wrapper endurecido **`scripts/deploy_hf_space_safe.py`** (dry-run por padrão, scan anti-leak,
  manifest path/size/sha256, `--execute` explícito, nunca imprime/embute token).
- Allowlist derivada do `Dockerfile.hf`/runtime: `app.py`, `requirements.txt`, `requirements-hf.txt`,
  `src/**`, `config/**` + `README_HF.md→README.md`, `Dockerfile.hf→Dockerfile`.

## Dry-run

- `status=DRY_RUN_OK`, `files_count=79`, `total_bytes=499417`, nenhum segredo.
- Excluídos por política: `.env`, `.autonomous/**`, `reports/**`, `node_modules/**`, `.venv/**`,
  `__pycache__/**`, `.git/**`, `*.log`, `*.sqlite`, backups.

## Execução

- Venv isolado `.autonomous/deploy/deploy_venv` com `huggingface_hub==2.0.0`
  (**não** instalado no `.venv` principal; `requirements` inalterados).
- `--execute` → `UPLOAD_OK` (`space_id=endartstudios/nexus-alpha`, 79 arquivos).

## Telemetria pós-deploy

`check_space_telemetry` (retries=8) → **`ok=true`**, `http_status=200`:

```text
status=online
concept_count=1894
fact_count=335
run_scoped_gap=0
graph_scoped_gap=-335
unaccounted_raw=0
verification.quorum=3
fallback_promoted_to_graph=0
top_invalid_predicates=[]
verified_facts_domain_independent=11
```

> Observação: `/api/metrics` respondeu **502 intermitente** durante o cold start (Neo4j);
> com retries o gate retorna `ok=true`. O hard gate do worker (`src/ops/space_telemetry.py`)
> já usa retries, então isso não bloqueia o #048.10H.

## Segurança

- Nenhum worker executado; nenhuma escrita em Neo4j/Qdrant; nenhum treino.
- Nenhum force-push (GitHub ou Space); nenhum restart factory; nenhum novo Space.
- `.autonomous/deploy/**` (venv, manifest, polls, métricas) **não commitado**.
