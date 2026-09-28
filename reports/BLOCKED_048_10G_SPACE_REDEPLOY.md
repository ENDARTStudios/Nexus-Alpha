# BLOCKED_048_10G_SPACE_REDEPLOY

**Data:** 2026-09-28
**Repo:** `ENDARTStudios/Nexus-Alpha`

## Problema

O HF Space (`ENDARTStudios/Nexus-Alpha`) está compilando **source antigo** (`sha=85355c6d…`, `2026-09-25`).
O `restart` automático (`factory_reboot`) foi aceito (`HTTP 200`) mas **reconstruiu o source antigo**, não o
HEAD do GitHub. Por isso, a telemetria #052.3 (`concept_count`, `fact_count`, `run_scoped_gap`,
`graph_scoped_gap`) e o futuro runtime GEO **não** estarão disponíveis no `/api/metrics` até um
**redeploy/upload manual**.

## Evidência

- Space sha observado: `85355c6d0e32651eebe4acdf1eb7c7103f6fc245` (`lastModified=2026-09-25T03:03:55Z`).
- HEAD do repo após #048.10G: (ver SPRINT / `git log`).
- `restart` automático: aceito, mas rebuild do source antigo (`stage=RUNNING_BUILDING`, mesmo sha).
- Telemetry fields ausentes no payload live: `concept_count`, `fact_count`,
  `ingestion_accounting.run_scoped_gap`, `ingestion_accounting.graph_scoped_gap`.

## Ação manual do Operador

1. Abrir o HF Space `ENDARTStudios/Nexus-Alpha`.
2. Confirmar vínculo com o repositório/branch corretos.
3. Fazer **upload/redeploy do código do commit mais recente do `main`** — **não apenas restart**. Opções:
   - `scripts/deploy_hf_space.py` em ambiente com `huggingface_hub` instalado;
   - interface web do HF Space para sincronizar/atualizar arquivos;
   - reconectar o Space ao repositório se estiver desacoplado.
4. Aguardar build verde.
5. Validar `/api/metrics` esperando: `concept_count`, `fact_count`,
   `ingestion_accounting.run_scoped_gap`, `ingestion_accounting.graph_scoped_gap`, `verification.quorum=3`,
   `fallback_promoted_to_graph=0`, `top_invalid_predicates=[]`.

## Preflight obrigatório

Antes de qualquer worker futuro, rodar:

```powershell
python scripts/check_space_telemetry.py
```

Só prosseguir se retornar `classification = OK`. Caso contrário: `BLOCKED_SPACE_STALE_TELEMETRY`.

## Após validação

Executar o próximo ciclo **#048.10H** (worker incremental GEO) com snapshot/baseline/post/audits.
