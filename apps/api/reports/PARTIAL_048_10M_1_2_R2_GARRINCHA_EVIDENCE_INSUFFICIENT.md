# PARTIAL_048_10M_1_2_R2_GARRINCHA_EVIDENCE_INSUFFICIENT

**Data:** 2026-10-03 · **Modo:** read-only (nenhum worker/ingest/escrita/seed/treino/deploy)

## Motivo

O probe read-only da Fase B esgotou o orçamento (6/6 requisições) **sem confirmar nenhum domínio não-Wikimedia** com evidência plausível de Garrincha+Botafogo+contexto de defesa: **6×404 em caminhos probeados incorretamente**.

## Causa raiz do 404 (documentada para o próximo ciclo)

Os caminhos probeados foram suposições. Os caminhos **REAIS** minerados com 200 OK pelo piloto (36h antes) estão no log `worker_run3.log`:

```text
https://www.rsssf.org/sacups/copalib.html       (200 OK, produtivo p/ VENCEU)
https://www.rsssf.org/tablesb/brazchamp.html    (200 OK, produtivo p/ VENCEU)
```

E o seeds `pele_santos` (linha 75-76 do `seed_clusters.yaml`) contém:

```text
https://www.rsssfbrasil.com/sel/jogclub.htm     (jogadores-por-clube — nunca probeado para Garrincha)
```

Nota: `reports/defendeu_botafogo_rsssf_atlas_048_10I.json` lista `rsssfbrasil.com/clubes/botafogo.htm` como 200 no audit 048_10I — **hoje 404**: ou o site reestruturou, ou o audit usou UA/headers diferentes. Observação registrada, não investigada neste ciclo (orçamento esgotado).

## O que o ciclo R2 PROVOU (não é fracasso total)

**Fase A PASSOU integralmente** — o fato canônico do Garrincha no grafo é saudável:

```text
canonical_fact_found = true
fact_id = 4:3b5e8459-...:3749 (elementId)
verified = false (2 < quórum 3 — esperado)
same_triple_confirmation = true
confirmed_domains = pt.wikipedia.org + en.wikipedia.org (2/3)
span_broken/junk/forbidden/invalid = false ×4
homonymy_risk = low
blocking_reason = null
```

## Bloqueio atual

`ready_for_future_g1 = false` — o dry-run corrigido (D5) não pode contar `domains_to_be_mined` sem probe confirmado. Falta exatamente: **probe de 3 URLs comprovadas** (`brazchamp.html`, `copalib.html`, `jogclub.htm`) num próximo ciclo read-only com orçamento renovado.

## Próximo passo recomendado

**R3 read-only com orçamento renovado (≤3 requisições)** nas URLs corretas documentadas acima. Se qualquer uma mencionar Garrincha+Botafogo com contexto de carreira → G1 pronto para GO do Operador. Sem rodar worker, sem ingest, sem seeds.
