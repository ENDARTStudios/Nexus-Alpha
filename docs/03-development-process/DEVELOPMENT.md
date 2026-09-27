# 👨‍💻 Development — Fluxo de Trabalho Diário (Nexus-Alpha)

Pré-requisito: ambiente pronto ([`SETUP.md`](./SETUP.md)) e regras lidas
([`RULES.md`](./RULES.md)).

---

## 1. Escolher trabalho

1. A sprint vigente em `SPRINT.md` define o escopo exclusivo.
2. Tarefas mapeadas: [`TASKS.md`](./TASKS.md) + issues GitHub.
3. Fora do escopo da sprint? Não executa — propõe em nova sprint.

## 2. Ciclo de implementação

```bash
# 1. Branch curta (ou direto em main para itens pequenos aprovados)
git checkout -b feat/<tema>

# 2. Implemente com o par módulo+teste
#    src/<camada>/...  ↔  tests/test_<modulo>.py

# 3. Rode a suíte localmente
python -m pytest -q

# 4. Staging EXPLÍCITO (nunca git add -A)
git status
git add src/<arquivo> tests/<teste> docs/<doc-atualizado>
git diff --cached

# 5. Commit convencional (1 item)
git commit -m "feat(cognition): guard nonverbal predicates in EntityExtractor"

# 6. Push e acompanhe o gate
git push
```

## 3. O que o CI executa em cada push/PR

`.github/workflows/ai-validation.yml`:

1. **Anti-leak:** `grep` por segredo em `src/` (falha se match).
2. **pytest** (`requirements-dev.txt`, PYTHONPATH na raiz).
3. **Conformidade:** `SPRINT.md` precisa existir na raiz.
4. **Allowlist do proxy:** validação Node 20 (alterou rota? atualize o teste).

Verde = pronto para merge em `main`. Vermelho = corrija, **não** force-push.

## 4. Padrões por tipo de mudança

| Tipo | Regras específicas |
|---|---|
| **Módulo novo** | camada correta ([`ARCHITECTURE.md`](./ARCHITECTURE.md) §1); testes sem torch/spacy/Neo4j real; degradação graciosa |
| **Refino determinístico** | função pura; motivo tipado; contadores dinâmicos em `/api/metrics`; teste golden por par entrada→saída |
| **Cypher** | puro sem APOC; MERGE idempotente; índices para campos de filtro; respeitar schema (`fact_hash`, `f.domain`) |
| **Endpoint novo** | auth igual aos existentes; erro sanitizado; registrar em [`API.md`](./API.md) |
| **Frontend** | tokens do [`DESIGN.md`](./DESIGN.md); fetch só via `lib/api.ts`; checklist de [`ACCESSIBILITY.md`](./ACCESSIBILITY.md) |
| **Seeds/config** | validar com testes estruturais (`test_seed_clusters.py`); URL pública HTTPS 200 |
| **Doc** | pt-BR, com números/evidência; atualizar `docs/README.md` se criar arquivo |

## 5. Métricas e observabilidade

Mudou comportamento observável? Exponha/ajuste contadores em `/api/metrics`
(o padrão do projeto: `rejection_reasons` dinâmico — novos motivos não
exigem mudança em `app.py`) e documente em [`ANALYTICS.md`](./ANALYTICS.md).

## 6. Executar ciclo de worker manualmente

```bash
export NEXUS_API_TOKEN=... HF_SPACE_URL=... HF_TOKEN=...
PYTHONPATH=. python scripts/worker_cycle.py
```
Use para validar mudanças de mineração/ingest **antes** do cron; capture
baseline/post das métricas (padrão #048) e registre em `SPRINT.md`.

## 7. Utilitários de auditoria (read-only)

```bash
PYTHONPATH=. python scripts/audit_cross_source.py    # near-match cross-source
PYTHONPATH=. python scripts/audit_post_clean.py      # reconcile + cobertura + predicate health
PYTHONPATH=. python scripts/stress_episodes.py 1000  # estresse de memória episódica
```

Nenhum deles promove/altera fatos — são ferramentas de diagnóstico.

## 8. Fim de tarefa (checklist de fechamento)

- [ ] Suíte verde; teste novo cobre o caminho de erro.
- [ ] `git diff -- requirements-dev.txt .github/workflows/` vazio (se não mapeado).
- [ ] Doc(s) de `docs/` atualizada(s).
- [ ] Resultado/números registrados em `SPRINT.md`.
- [ ] 1 commit limpo; nenhum segredo; nenhum `NEXT_PUBLIC_` de segredo.
