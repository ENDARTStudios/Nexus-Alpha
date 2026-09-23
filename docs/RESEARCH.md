# 🔬 Research — Evidências e Questões Abertas (Nexus-Alpha)

Registro de investigações com dados medidos (auditorias read-only, dry-runs e
ciclos de produção). Cada seção responde: o que medimos, o que concluímos e
qual a alavanca indicada.

---

## R1 — Por que `cross_domain` não sobe? (GARGALO ATUAL)

**Fonte:** produção, worker_dispatch com clusters curados (#048, 2026-09).

```text
BASELINE: duplicate_cross_domain=0 facts_with_multi_domain=0 verified=0
POST    : duplicate_cross_domain=0 facts_with_multi_domain=0 verified=0
          distinct=108 persisted=108 gap=0 unaccounted=0
          duplicate_same_source_url=80 duplicate_same_domain=5
```

**Causa raiz (logs do worker):**
1. Reputação de domínio **resolvida** (#056 funcionou): `santosfc.com.br`,
   `ge.globo.com`, `botafogo.com.br` buscados com 200.
2. Mas páginas não-wiki retornaram `entities_processed: 0` — o refino rejeitou
   todas as triplas (páginas JS/listing/texto não-declarativo).
3. Wiki PT e EN geraram triplas **diferentes entre si** para o mesmo fato
   (superfícies distintas: tradução/sinônimo). Como o #051 mostrou
   `near_match.high = 0` lexicalmente, a variação é **semântica**.

**Conclusão:** o gargalo final não é cobertura de domínios nem reputação — é
**equivalência semântica entre fontes**.

**Alavancas indicadas (em ordem):**
1. Entity linking como **diagnóstico** (medir `potential_verified_if_linking`;
   nunca promover fato por embedding — regra de ouro).
2. #047 — aliasing curado de entidades.

## R2 — Qualidade da extração: objetos-fragmento

**Fonte:** auditoria #046 (read-only, 106 fatos) + dry-run do span validator (#050).

Amostra real de triplas sem valor semântico:
`ARTHUR SAMUEL --DEFINE--> EM 1959` · `ALGORITMO BACKPROPAGATION --UTILIZA--> COM ISSO`
`AREA DE REDES NEURAIS --POSSUIR--> APOS A PUBLICACAO EM 1986`

Dry-run do validador (106 fatos): `would_pass=67`, `would_reject=39`
(top motivos: `object_date_like=14`, `object_prepositional_phrase=14`,
`subject_quantifier_phrase=8`).

**Conclusão:** datas/orações/locuções como objeto tornam a corroboração
impossível por construção → span validator determinístico implementado (#050).
Fatos borderline (`OBJETIVO --APRENDE--> REGRA GERAL QUE MAPEIA`) ainda passam —
**v2 pendente**.

## R3 — `confirmacoes` contava URLs, não domínios

**Fonte:** #046/#049. Um fato tinha `confirmacoes=4` com 4 URLs do mesmo
domínio (`pt.wikipedia.org`) → `cross_source_matches` superestimava.

**Correção implementada (#049):** `f.domain` em `:FonteWeb` +
`count(DISTINCT ff.domain)`. `verified_facts` pode ter caído — é a métrica
ficando honesta, não regressão.

**Dívida:** independência ainda é por host — `pt.`/`en.wikipedia.org` contam
como 2 (#053: eTLD+1/publisher).

## R4 — Pipeline reconciliation pós-limpeza

**Fonte:** #051 (66 fatos limpos).

```text
raw:209 → canonical:78 → rejected:130 → persisted:66
canonical_to_fact_gap:12  unaccounted_raw:1
predicate_health: unmapped 49, modal 26, ambiguous 11
top_unmapped: DESCREVER 6, DAR 4, VIR 3 ...
```

**Conclusões:**
- Gap de 12 = triplas canônicas repetidas entre payloads com a mesma
  `source_url` (MERGE reusa `:FonteWeb` sem nova confirmação) → resolveu-se
  com a contabilidade por chave distinta (#052).
- `top_unmapped` sem verbos claros recorrentes (≥3) → predicate mapper
  (#045) NÃO é o gargalo → reabrir só se a métrica mudar.

## R5 — Reputação de domínio era o bloqueio estrutural

**Fonte:** #056. Todo publisher comum (`.com`) recebia 0.60 < 0.70 e ia para
quarentena **antes** do ingest → cross-domain impossível por construção
(corpus só podia ser Wikipedia).

**Correção:** `REPUTABLE_PUBLISHERS` (allowlist curada por domínio registrável)
→ 0.85. Invariantes mantidos: quórum 3; `.org`/`.edu`/`.gov` 0.9; desconhecidos
0.6; baixa-confiança (reddit/medium/wordpress) 0.4.

## R6 — Perguntas abertas

1. **Validador de span v2:** como tratar fatos borderline sem abrir
   falsos positivos? (heurística de núcleo verbal + objeto nominal?)
2. **Ontologia temporal (#054):** `:Ano`/`:Periodo` + `OCORREU_EM` liberaria
   os 14 fatos `object_date_like` rejeitados — vale o custo do schema novo?
3. **Almanaque (#055):** API estruturada primária substituiria parte da
   mineração de páginas JS (que hoje rendem `entities_processed: 0`)?
4. **Embeddings contextuais (item 2 do freeze):** trocar o modelo base
   (feature hashing 384-dim) melhoraria near-match semântico? Medir antes
   de decidir — embedding segue sendo **sugestão**, nunca promoção.
