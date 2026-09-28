# BLOCKED_052_3_SPACE_REDEPLOY

**Data:** 2026-09-28
**Repo:** `ENDARTStudios/Nexus-Alpha`
**HEAD:** `9e495db` (após o patch #052.3)
**Motivo do bloqueio:** não há ferramenta de deploy do Space disponível localmente.

## Problema

O HF Space (`endartstudios/nexus-alpha` → `endartstudios-nexus-alpha.hf.space`) está em **build antigo**,
anterior ao #052.2. Por isso `ingestion_accounting.run_scoped_gap` e `graph_scoped_gap` **não aparecem**
no `/api/metrics`, embora **existam no código**.

Além disso, o build antigo **não conhece** os novos campos de clareza (`concept_count`, `fact_count`) do #052.3.

## Evidência

- HEAD do repo: `9e495db` (patch #052.3 aplicado; CI/estado).
- Código com `run_scoped_gap` / `graph_scoped_gap`: **sim** (`app.py::IngestAccounting.snapshot`, linhas ~249-280;
  adicionados em `503e6a3` — `#052.2`).
- `/api/metrics` em execução sem `run_scoped_gap` / `graph_scoped_gap`: **true** (captura `metrics_before.json`).
- Space build observado: `0b5bc32` (2026-09-24) — ancestral de `#052.2`.
- Deploy automático do Space: **inexistente** — nenhum workflow chama `deploy_hf_space.py`; o Space é atualizado
  manualmente via `scripts/deploy_hf_space.py` (`HfApi.upload_folder`).
- Ferramentas locais: `huggingface_hub` = **ausente**; `hf` / `huggingface-cli` = **ausentes**.
  (Não instaladas por política desta task.)

## Classificação

`PARTIAL_052_3_CODE_READY_SPACE_STALE` — o patch de código está pronto, testado e commitado; falta o redeploy do Space.

## Ação manual do Operador

1. Abrir o HF Space `endartstudios/nexus-alpha`.
2. Ir em **Settings → Factory rebuild** (ou **Restart this Space** / **Redeploy**).
3. Confirmar que o Space está apontando para o repositório/branch corretos e para o **HEAD atual**.
4. Do diretório do repo, com `HF_TOKEN` e `HF_SPACE_URL` (ou `HF_SPACE_ID`) definidos:
   ```powershell
   python scripts/deploy_hf_space.py
   ```
   (ou `Factory Reboot`/`Redeploy` se o Space já espelhar o repositório do core).
5. Aguardar build verde.
6. Validar `GET /api/metrics`.

## Validação esperada (após redeploy)

- `status: online`
- `ingestion_accounting.run_scoped_gap` **presente**
- `ingestion_accounting.graph_scoped_gap` **presente**
- `concept_count` **presente** = 1894
- `fact_count` **presente** = 335
- `verified_facts_domain_independent` = 11
- `duplicate_cross_domain` = 23
- `top_invalid_predicates` = []
- `fallback_promoted_to_graph` = 0
- `unaccounted_raw` = 0
- `quorum` = 3

> Nenhum worker deve ser executado nesta task; nenhuma seed alterada; nenhum treino.
