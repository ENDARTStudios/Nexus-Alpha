# BLOCKED_060 — Gate de treino (avaliação read-only)

**Data:** 2026-09-27 · **Task:** #060 (avaliação read-only; treino NÃO executado) · **HEAD:** `b7fe512`

## Resultado

```text
records_total (fatos verificados exportáveis) = 10   (< 50)
unique_predicates = 1   (VENCEU)
unique_objects    = 2   (COPA LIBERTADORES, CAMPEONATO BRASILEIRO SERIE A)
unique_subjects   = 7
unique_publishers = 2   (Wikimedia, RSSSF)
python            = 3.14.7  (≠ 3.11–3.13)
gpu               = ausente
llamafactory      = não instalado
kaggle creds      = ausentes
NEXUS_ENABLE_TRAINING = ausente
```

Classificação: **Cenário 1 — BLOCKED_RECORDS_INSUFFICIENT**
(+ `DIVERSITY_GATE_FAILED`, + `PUBLISHER_INDEPENDENCE_WARNING`, + `TRAINING_BLOCKED_ENVIRONMENT`).

`training_recommended = false` · `training_allowed = false`

## Por que não treinar

1. **Records < 50** — só 10 fatos verificados por 3 domínios existem no grafo.
2. **Monocultura semântica** — 1 predicado (`VENCEU`), 2 objetos (competições). Treinar agora ensinaria um template estreito.
3. **Publishers = 2** (Wikimedia + RSSSF) — dívida **#053**.
4. **Ambiente** — Python 3.14 (exigido 3.11–3.13), sem GPU/Kaggle, LlamaFactory não instalado; flag de treino ausente.

## O que JÁ está provado

- Export é **read-only** (`GraphConnector.export_verified_facts` → `MATCH ... WHERE verificado=true`, sem CREATE/MERGE/SET/DELETE).
- Dataset Alpaca/JSONL válido: 10/10 linhas JSON, 0 inválidas, 0 output vazio, 0 segredos, schema `instruction/input/output`.
- Proveniência presente em 10/10 registros (`domains` + `confirmations` no campo `input`).
- Config LlamaFactory gera YAML parseável, sem segredos (nota: `dataset_dir: data/sft` — ajustar para o dir exportado num smoke).

## Próximo issue recomendado

```text
#048.10A — escalar fatos verificados para records >= 50
#048.10B — diversificar além de VENCEU/competição
  alvos: JOGADOR --DEFENDEU--> CLUBE
         CLUBE --POSSUIR--> ESTÁDIO
         ESTÁDIO --LOCALIZADO_EM--> CIDADE
         CLUBE --LOCALIZADO_EM--> CIDADE
         CLUBE --DISPUTOU--> COMPETIÇÃO
#053 — publisher independence (Wikimedia+RSSSF = 2 publishers)
```

Sempre com dry-run read-only antes de runtime. Não abrir #047.2/#045.3 sem evidência.

## Como retomar (runbook)

```bash
# 1) exportar novamente após escalar fatos
python scripts/train_lora.py export --source graph --limit 100 \
  --out-dir .autonomous/training/dataset --dataset-name verified_candidate

# 2) reavaliar o gate (read-only)
python scripts/evaluate_training_gate.py --limit 500

# 3) se records>=50 + diversidade + publishers + ambiente ok:
#    gerar smoke runbook em GPU/Kaggle (Python 3.11–3.13 + LlamaFactory opt-in).
#    NÃO treinar sem flag explícita NEXUS_ENABLE_TRAINING e ambiente.
```
