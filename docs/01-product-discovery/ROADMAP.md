# 🗺️ Roadmap — Nexus-Alpha

Evolução planejada por versão. O escopo de execução de cada ciclo é sempre
congelado em `SPRINT.md`; este documento é a visão de médio prazo.

**Atualizado em:** 2026-09-23

---

## Estado atual

- ✅ **v1.12.0-beta** — Memória Episódica Durável (concluída: 422 episódios
  sobreviveram a restart; 146→~195 testes verdes).
- 🧊 **v1.13.0** — Freeze de infraestrutura (2–3 ciclos / 12–18h em produção):
  qualidade semântica apenas; itens incrementais já entregues (#041–#052,
  #056, #048).

## Próximo marco — Equivalência semântica entre fontes

**Evidência:** #048 em produção mostrou PT/EN gerando triplas distintas para o
mesmo fato; lexicalmente `near_match.high = 0` → variação é semântica.

| Passo | O quê | Restrição |
|---|---|---|
| 1 | Entity linking **diagnóstico** (medir `potential_verified_if_linking`) | sem promover fato; read-only |
| 2 | **#047** Aliasing curado de entidades (dicionário + evidência de métrica) | determinístico; sem LLM |
| 3 | Re-ingest controlado (backup → zerar → deploy → worker com seeds → comparar) | protocolo em `SPRINT.md` |
| 4 | Só então: reavaliar embeddings contextuais (item 2) e refino de prompt do CoT (item 3) | embedding segue sugestão, nunca promoção |

**Critério de sucesso:** `verification.facts_with_two_or_more_domains > 0` e/ou
`ingestion_accounting.duplicate_cross_domain > 0` em ciclo real do worker.

## Fila seguinte (após equivalência semântica)

1. **#053 — Independência editorial por publisher/eTLD+1** (`pt.` vs `en.
   wikipedia.org` ainda contam como 2 hosts do mesmo publisher).
2. **#050-v2 — Validador de span conservador→maduro** (fatos borderline).
3. **#054 — Ontologia temporal** (`:Ano`/`:Periodo`, `OCORREU_EM`) para
   fatos datados (14 rejeições `object_date_like` poderiam virar fatos).
4. **#055 — API REST do Almanaque** como fonte estruturada primária
   (páginas JS rendem `entities_processed: 0` hoje).
5. **#044+ — Expansão do predicate mapper** a partir de
   `top_unmapped_predicates` (só com verbos claros recorrentes ≥3).

## Linha de treino (opt-in, fora do runtime)

- Gate atual: `records >= 50`, `verified_facts >= 10`, sem segredos, YAML
  válido → smoke Kaggle (`epochs 1, batch 2, grad_accum 2, max_samples 100`).
- **Não planejado:** serving/merge de adapter, integração com `llm_provider.py`,
  LlamaFactory no CI. (Ver [`RULES.md`](./RULES.md) §5.)

## Visão de longo prazo (sem data)

- Crescimento de corpus por novos clusters curados (modelo do futebol
  replicado a outros domínios).
- Reflexão noturna (`reflection.py`) com desempate web para contradições
  mais integrada ao ciclo de consolidação.
- Expansão do GraphRAG (subgrafos > 2 saltos) se latência permitir.

## Princípios que governam este roadmap

1. **Custo zero** — toda evolução cabe em free tiers.
2. **Determinismo antes de IA** — resolução determinística sempre precede LLM.
3. **Métrica antes de código** — nenhuma alavanca sem evidência de auditoria.
4. **Quórum 3 inegociável.**
