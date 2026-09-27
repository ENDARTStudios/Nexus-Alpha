# 👀 Code Review — Processo e Checklist (Nexus-Alpha)

O gate de CI é o primeiro revisor; o humano/agente revisa **intenção,
escopo e consequências**. Este doc define o checklist mínimo para aprovar.

---

## 1. Fluxo

```text
Push/PR → Gate CI (anti-leak → pytest → SPRINT.md → allowlist proxy)
        → Review humano/agente (checklists abaixo)
        → Merge em main (sem force-push)
```

Commits diretos em `main` são permitidos para itens pequenos — mas exigem o
mesmo checklist aplicado **antes** do push (revisão própria disciplinada).

## 2. Checklist universal (toda mudança)

**Escopo e governança**
- [ ] Dentro do escopo da sprint vigente (`SPRINT.md`).
- [ ] 1 item por commit; staging explícito; sem arquivos acidentais no diff.
- [ ] `git diff -- requirements-dev.txt .github/workflows/` vazio (se não mapeado).

**Segurança** ([`SECURITY_REVIEW.md`](./SECURITY_REVIEW.md) §3)
- [ ] Zero segredo literal; nenhum `NEXT_PUBLIC_` de segredo.
- [ ] Logs sanitizados; erros sem stack trace para o cliente.

**Qualidade** ([`STYLE_GUIDE.md`](./STYLE_GUIDE.md))
- [ ] Suíte verde; teste novo inclui caminho de erro; sem deps pesadas.
- [ ] Assíncrono no I/O; sem bloqueio.
- [ ] Cypher puro sem APOC; MERGE idempotente onde couber.

**Invariantes do produto**
- [ ] Quórum de triangulação permanece 3.
- [ ] Nenhum embedding/LLM promovendo fato.
- [ ] Degradação graciosa preservada (sem banco, o app sobe).
- [ ] Determinismo das funções de refino mantido.

**Documentação**
- [ ] Doc de `docs/` atualizada quando o comportamento muda.
- [ ] Decisão duradoura registrada como ADR.
- [ ] Métricas novas documentadas em [`ANALYTICS.md`](./ANALYTICS.md).

## 3. Checklist por área

**Backend/ingest (`app.py`, refino, conectores)**
- [ ] Contrato NexusPayload respeitado; contadores contábeis coerentes
      (`distinct_canonical_keys`, `canonical_to_fact_gap`).
- [ ] Motivos de rejeição tipados; quarentena recebe (não descarta).
- [ ] Fallback (`demo-memory`, `volatile`) sinalizado na resposta.

**Miner/seeds**
- [ ] Nova fonte: pública, HTTPS 200, sem paywall, não-low-trust.
- [ ] Delays/UA rotation preservados (não "otimizar" removendo).
- [ ] Seeds validadas por `tests/test_seed_clusters.py`.

**Frontend/UI**
- [ ] Tokens de cor do [`DESIGN.md`](./DESIGN.md) (sem hex avulso).
- [ ] Fetch somente via `lib/api.ts`/`nexus.ts`/`brain.ts`.
- [ ] [`ACCESSIBILITY.md`](./ACCESSIBILITY.md): teclado, aria-live, foco,
      reduced motion.
- [ ] Painéis read-only continuam read-only.

**Treino (opt-in)**
- [ ] Nada de torch/llamafactory no runtime/CI.
- [ ] `train` sem LlamaFactory → erro amigável testado.

## 4. Red flags (bloqueiam aprovação)

- Reduzir quórum/limiares de segurança para "fazer métrica subir".
- Trocar função determinística por chamada de LLM.
- `git add -A` no histórico do PR; commit misturando escopos.
- Métrica nova sem definição documentada.
- "Funciona no meu ambiente" com dependência de banco real nos testes.
- Nova dependência pesada no runtime do Space sem ADR.

## 5. Como registrar a revisão

- PRs: aprovação com resumo do que foi verificado (checklists acima).
- Commits diretos: o resumo da revisão vai na mensagem/registro da sprint
  (`SPRINT.md` apêndice) quando o item for mapeado.
- Achados recorrentes → viram regra em [`RULES.md`](./RULES.md) ou item
  neste checklist.
