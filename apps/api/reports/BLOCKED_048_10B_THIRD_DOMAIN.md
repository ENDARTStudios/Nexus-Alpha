# BLOCKED_048_10B — Terceiro domínio independente para DEFENDEU

**Data:** 2026-09-27 · **Task:** #048.10B · **HEAD:** `031edf2`+ · **Classe:** `BLOCKED_THIRD_DOMAIN_FOR_DEFENDEU` (Cenário B)

## O que funcionou (extração)

`target-aware selection` (#048.10B) fez `PELÉ --DEFENDEU--> SANTOS FUTEBOL CLUBE` ser emitido
no cap de produção (25) nas 3 URLs:

```text
pt.wikipedia.org/wiki/Pelé     -> EDSON ARANTES DO NASCIMENTO | DEFENDEU | SANTOS FUTEBOL CLUBE
en.wikipedia.org/wiki/Pelé     -> EDSON ARANTES DO NASCIMENTO | DEFENDEU | SANTOS FUTEBOL CLUBE
pt.wikipedia.org/wiki/Santos_FC-> EDSON ARANTES DO NASCIMENTO | DEFENDEU | SANTOS FUTEBOL CLUBE
```

Resultado no grafo: `confs=3`, domínios `{pt.wikipedia.org, en.wikipedia.org}` → **2 domínios**.

## Por que NÃO conta como `verified_facts_domain_independent`

O flag canônico (Space `app.py` / `graph_connector.INGEST_QUERY`) exige **3 domínios distintos**:

```cypher
SET fato.confirmacoes = count(DISTINCT ff.domain),
    fato.verificado  = (confirmacoes >= $quorum)   -- quorum = 3 DOMÍNIOS
```

`PELÉ→SANTOS` tem 2 domínios → `f.verificado = false` → **não entra** no export de treino
(`WHERE f.verificado = true`) nem em `verification.verified_facts_domain_independent`.
Portanto `verified_facts_domain_independent` permanece **10** (não 11).

> Nota: a query de auditoria `confs>=3 AND size(doms)>=2` retorna 11 — é uma definição mais
> fraca (conta URLs, não domínios). A definição canônica do projeto (nome: *domain independent*)
> usa **domínios** = 10. A discrepância fica registrada (dívida #053).

## Por que não há 3º domínio agora

- RSSSF (`copalib`/`brazchamp`) cobre **títulos**, não jogador↔clube.
- `santosfc.com.br` é unproductive (#048.3, 0 triplas).
- Um 3º idioma Wikipedia (es/fr) seria **mesmo publisher (Wikimedia)** → monocultura editorial
  que o #053 sinaliza; **não usar como independência**.

## Resultado do worker

| Métrica | Antes | Depois | Δ |
|---|---:|---:|---:|
| duplicate_cross_domain | 11 | 12 | +1 |
| facts_with_two_or_more_domains | 11 | 12 | +1 |
| verified_facts_domain_independent (canônico) | 10 | 10 | 0 |
| facts_with_three_or_more_domains | 10 | 10 | 0 |
| records_total (export) | 10 | 10 | 0 |

Classificação: **Cenário B** (extração melhorou; falta 3ª fonte independente).

## Próximo issue

```text
#059C — Atlas de terceira fonte estática INDEPENDENTE (não-Wikimedia) para player-club DEFENDEU
        (ex.: base estatística histórica, arquivo de federação, acervo público em HTML estático)
#053  — definição de independência por publisher/eTLD+1 (hoje 3 domínios ≠ 3 publishers)
#055  — Almanaque REST apenas com licença Elite
```

Não treinar. Não baixar quórum. Não usar API do Almanaque sem licença.
