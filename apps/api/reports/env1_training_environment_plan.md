# ENV-1 — Plano de ambiente de treino (read-only)

**Data:** 2026-10-09 · **Status:** PLANO — nenhum treino executado; aguarda GO-6 do Operador.
**Contexto:** todos os gates de DADOS estão verdes (verified 52 ≥ 10 · records 52 ≥ 50 · schema · sanitization · diversity · publisher · provenance). O único bloqueio remanescente é o ambiente.

## Gate atual (medido por `evaluate_training_gate.py`)

| Item | Estado | Requisito |
|---|---|---|
| `python_gate` | ❌ | Python **3.11–3.13** (ambiente atual: **3.14.7**) |
| `gpu_gate` | ❌ | GPU disponível (atual: nenhuma) |
| `llamafactory_gate` | ❌ | LlamaFactory instalado (requirements presentes: `requirements-llamafactory.txt`) |
| `training_enable_gate` | ❌ | Flag explícita de habilitação |
| `kaggle_credentials_present` | ❌ | Credenciais Kaggle (opcional) |
| `training_allowed` | ❌ | **Hardcoded `false`** — autorização é sempre decisão do Operador (GO-6/GO-7) |

## Opções de ambiente (custo zero primeiro)

| Opção | GPU | Python | Custo | Notas |
|---|---|---|---|---|
| **A. Kaggle Notebooks** (recomendada) | T4 16GB ou P100, 30h/semana | 3.11 (controlável) | **grátis** | `requirements-llamafactory.txt` instalável; dataset (52 records, JSONL) sobe como Dataset privado |
| B. Google Colab | T4 grátis (sessões curtas) | 3.11 | grátis | Limite de sessão; bom para smoke test |
| C. HF Jobs / Spaces GPU | A10G/T4 por hora | 3.11+ | pago (~$0.40/h) | Integrado ao HF já usado pelo projeto |
| D. Local (esta máquina) | **nenhuma** | 3.14 (incompatível) | — | Precisa venv 3.11 + não há GPU → inviável para treino real |

## Plano de execução (com GO-6)

1. **Criar venv Python 3.11** no ambiente de treino (Kaggle/Colab) — nunca na raiz do monorepo.
2. **Instalar** `apps/api/requirements-llamafactory.txt` + `llamafactory`.
3. **Subir o dataset** `.autonomous/training/dataset/verified_candidate.jsonl` (52 records; schema `instruction`/`input`/`output`; **não commitado** — política O3) como input privado do notebook.
4. **Smoke test** (1 step, batch mínimo) para validar o pipeline antes do treino real.
5. **Treino LoRA** com holdout: `python scripts/train_lora.py` (runbook do script) — métricas + relatório; **nenhuma promoção automática de modelo** (TRAIN-1).
6. **EVAL-1** (read-only): checagem pós-treino contra os fatos do grafo — alinhamento; decisão de integração **deferida** ao Operador.

## Riscos e honestidade sobre o escopo

- **52 records é o piso do gate, não um dataset robusto.** Um LoRA treinado com ~52 pares produz um modelo que reproduz o formato/tom, não conhecimento confiável. O valor real do pipeline é a **infra de verificação** (quórum 3 provado em 7/7 candidatos + GEO).
- **Recomendação:** se o objetivo é um modelo útil, expandir o dataset via as alavancas já provadas (Wikidata por predicado, multílingue, mais clubes) antes de investir em treino — cada 10× de records muda a natureza do resultado.
- `training_allowed` permanece `false` por design: mesmo com ambiente pronto, o treino exige **GO-6 + flag explícita**.

## Decisão devolvida ao Operador

1. **GO-6** para provisionar o ambiente (Kaggle, custo zero) e rodar o smoke test, **ou**
2. **Deferir formalmente** o treino (registrado no SPRINT) e priorizar a expansão do dataset — o projeto permanece na Conclusão Operacional com a infra de verificação completa.
