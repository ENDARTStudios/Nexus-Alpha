# #054.4 — Verificação do gate de lint (ruff)

**Data:** 2026-10-07 · **Ambiente:** ruff (venv atual do operador), `apps/api` inteiro · **Read-only** (nenhum `--fix` aplicado).

## Resultado

```
F401  unused-import                       30  (auto-fixável)
E702  multiple-statements-on-one-line     17
F841  unused-variable                     11
E402  module-import-not-at-top-of-file     9
TOTAL: 67 ocorrências
```

**Distribuição:** concentradas em `scripts/` de auditoria/diagnóstico históricos
(padrões de one-liners e imports tardios de CLI); `src/` ativo e os testes
estão limpos (o CI quebra em qualquer erro novo introduzido nos caminhos
testados — comprovado nos ciclos 054.2.R3/06).

## Avaliação do gate

1. **Não há gate de lint no CI hoje** (`validate-project` roda pytest + anti-leak, sem ruff).
2. Ativar `ruff check` como gate **hoje quebraria o CI** (67 ocorrências pré-existentes).
3. A maioria (30 F401) é auto-fixável; os demais exigem revisão por arquivo.

## Proposição (task própria com GO separado — #054.4.1)

1. `ruff check --fix` em `scripts/` (30 F401) → PR revisável por diff.
2. Correção manual de E702/F841/E402 em `scripts/` históricos (ou exclusão
   deliberada desses arquivos mortos do gate).
3. Aí sim: `ruff check apps/api` no `ai-validation.yml` como gate obrigatório.

**Decisão:** gate DEFERIDO até #054.4.1 (GO próprio exigido). O fluxo de
desenvolvimento atual já roda `ruff` local por commit nos arquivos tocados
(convenção aplicada nesta sessão em todos os commits).
