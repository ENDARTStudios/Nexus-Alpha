# 🧩 Task Breaking Down — Como decompor trabalho (Nexus-Alpha)

Padrão usado nas sprints #036→#056: cada issue é **pequena, mensurável e com
escopo fechado**. Este doc é o manual para criar a próxima issue.

---

## 1. Princípios

1. **Evidência antes da tarefa.** Toda issue nasce de uma métrica/auditoria
   (ex.: #050 nasceu do dry-run do #046; #052 nasceu do gap do #051).
   Sem evidência, é research — e research é read-only primeiro.
2. **1 issue = 1 commit = 1 ponto de alavanca.** Se precisa de "e", quebre.
3. **Arquivos fechados.** A issue lista os arquivos afetados; nada fora dela
   pode ser tocado (`RULES.md` §1).
4. **Invariantes explícitos.** Toda issue reafirma o que **não** pode mudar:
   quórum 3, sem embedding-promotor, sem LLM no determinístico, sem APOC,
   CI lite.
5. **Read-only primeiro.** Antes de mudar o sistema, uma auditoria metric-only
   (#046, #051) valida a hipótese; só depois a issue de mudança.

## 2. Anatomia da issue (template obrigatório)

```markdown
#### [Issue #NNN] — <verbo + objeto>
- **Descrição:** o quê + por quê (citar métrica/evidência).
- **Arquivos Afetados:** caminho exato de cada arquivo.
- **Critérios:** condições verificáveis (números, comportamentos).
- **Fora de escopo:** o que NÃO faz (protege contra escopo rampante).
- **Invariantes:** quórum 3; sem LLM no determinístico; CI lite; sem segredos.
```

Exemplo real (condensado do #049):

```markdown
#### [Issue #049] — Corroboração por domínio distinto
- Descrição: confirmacoes contava URLs (4 URLs = mesmo domínio inflava).
- Arquivos: graph_connector.py (domain_from_url, INGEST_QUERY, SNAPSHOT_QUERY), app.py.
- Critérios: count(DISTINCT ff.domain); bloco verification em /api/metrics.
- Fora de escopo: quórum continua 3; sem mudança de TriangulationFilter.
```

## 3. Tamanhos e critérios de quebra

| Sinal de issue grande demais | Ação |
|---|---|
| Mais de ~5 arquivos afetados | quebrar por módulo (ex.: modelo → leitura/retenção: #036/#037) |
| Dois objetivos no título | separar (ex.: "aliasing + entity linking" → 2 issues) |
| Precisa de deploy E auditoria para validar | issue de código + protocolo de validação separado (re-ingest controlado) |
| Mudança de schema + mudança de código | schema primeiro (idempotente), código depois |
| "Melhorar X" sem número | virar research metric-only antes (#046 é o padrão) |

## 4. Sequenciamento típico de um tema

```text
1. Auditoria read-only (metric-only, sem deploy)      → evidência
2. Choke point único (uma transformação no ingest)    → código
3. Observabilidade da mudança (contadores dinâmicos)  → junto do 2
4. Validação em produção (worker manual + baseline/post) → número real
5. Registro do resultado em SPRINT.md                 → governança
```

Exemplo completo: #051 (auditoria) → #052 (contabilidade) → #056 (reputação)
→ #048 (seeds) → resultado em produção registrado.

## 5. Definition of Ready (para começar)

- [ ] Mapeada na sprint vigente (`SPRINT.md`) — senão, não executa.
- [ ] Evidência/hipótese com número.
- [ ] Arquivos afetados listados.
- [ ] Critérios verificáveis + teste associado previsto.
- [ ] Invariantes reafirmados.

## 6. Definition of Done (para fechar)

- [ ] `python -m pytest -q` verde (inclui teste novo).
- [ ] `git diff -- requirements-dev.txt .github/workflows/` vazio (quando a
      issue não mapear esses arquivos).
- [ ] Métrica/contadores expostos se o tema for observável.
- [ ] Doc de `docs/` correspondente atualizada.
- [ ] Resultado real (números) registrado em `SPRINT.md`.
- [ ] 1 commit, staging explícito, sem segredo.

## 7. Anti-padrões que este projeto já aprendeu a evitar

- **Otimizar sem medir:** #044/#045 só reabrem com `top_unmapped` recorrente.
- **Duplicar agendamento:** consolidar em cron extra (ADR-006).
- **Métrica vaidosa:** `confirmacoes` por URL (#049 corrigiu para domínio).
- **Misturar escopos no commit:** exceções `2a41622`/`712724d` — não repetir.
