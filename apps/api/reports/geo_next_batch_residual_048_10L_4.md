# #048.10L.4 — Residual pós-fechamento GEO

## Fato residual (não bloqueante, não verificado)

```text
MINEIRAO --LOCALIZADO_EM--> RIO DE JANEIRO   (verificado=false, domain_count=1, pt.wikipedia.org)
```

- **Origem:** criado em **#048.10L.2** (antes do hardening), quando o parser de infobox em HTML cru
  capturava "Rio de Janeiro" na página PT do Mineirão.
- **Estado:** **não verificado** (1 domínio, quórum 3 não atingido), **não promovido** (`fallback_promoted_to_graph=0`),
  **não** aparece no registry nem na evidência fact-level strong.
- **Recorrência prevenida:** o hardening de L.3 (`expected_city` source-scoped + rejeição cross-city) impede
  nova emissão; o worker de L.4 **não** reproduziu o fato (GEO/Wiki 18/18 sem "Rio" para Mineirão).
- **Impacto:** nenhum nos gates críticos — `junk_objects=0` (nenhum objeto tipo proibido), `forbidden=0`,
  `graph_scoped_gap=0`, `fact_accounting_status=ok`, `verified=20`, `5/5 strong`.

## Recomendação

- Limpeza **escopada** do `Fato` `MINEIRAO|LOCALIZADO_EM|RIO DE JANEIRO` em **#048.10L.5** (write mínimo,
  com snapshot e autorização), **não** neste ciclo (proibido write fora do worker/deste task).
- Nenhum restore automático.
