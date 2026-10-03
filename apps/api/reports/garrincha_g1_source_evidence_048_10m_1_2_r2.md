# Garrincha G1 source evidence (048_10m_1_2_r2)

## Política

- Permitidas: pt/en wikipedia, RSSSF (`rsssf.org`, `www.rsssf.org`), RSSSF Brasil (`rsssfbrasil.com`, `www.rsssfbrasil.com`)
- Proibidas: Transfermarkt, Soccerway, worldfootball, fbref, Almanaque sem licença, redes, fóruns, SEO, bets
- Wikimedia PT/EN: mesma publisher family
- RSSSF/RSSSF Brasil: família não-Wikimedia, warning de mesma família se ambos contarem

## Estado atual

- Garrincha --DEFENDEU--> Botafogo: **presente, não verificado** (elementId `4:3b5e8459-...:3749`, 2 confirmações na mesma tripla canônica)
- Domínios já confirmados: `pt.wikipedia.org`, `en.wikipedia.org` (2/3 — falta 1 não-Wikimedia)
- Domínios apenas locais: `www.rsssf.org` (produtivo p/ VENCEU no piloto), `www.rsssfbrasil.com` (produtivo p/ DEFENDEU do Jairzinho no piloto) — **sem confirmação viva para o fato do Garrincha**
- Domínio não-Wikimedia plausível: **não confirmado neste ciclo** (probe budget 6/6 esgotado em caminhos 404; caminhos reais do piloto documentados no PARTIAL)

## Probes

| domain | url | status | evidence | blocked |
|---|---|---:|---|---|
| www.rsssfbrasil.com | /clubes/botafogo.htm | 404 | none | false (caminho errado) |
| www.rsssf.org | /players/garrincha.html | 404 | none | false (caminho errado) |
| www.rsssf.org | /tablesb/botafogo.html | 404 | none | false (caminho errado) |
| rsssfbrasil.com | /clubes/botafogo.htm | 404 | none | false (caminho errado) |
| www.rsssfbrasil.com | /brazchamp.html | 404 | none | false (caminho errado) |
| www.rsssfbrasil.com | /copalib.html | 404 | none | false (caminho errado) |

Orçamento: 6/6 usados (máximo do task). Sem 403/429/bot-challenge. Sem bypass. Sem contaminação.

## Caminhos reais do piloto (para próximo probe read-only, sem custo neste ciclo)

```text
https://www.rsssf.org/tablesb/brazchamp.html   (200 OK no piloto — produtivo p/ VENCEU)
https://www.rsssf.org/sacups/copalib.html      (200 OK no piloto — produtivo p/ VENCEU)
https://www.rsssfbrasil.com/sel/jogclub.htm    (SEED EXISTENTE linha 75 — jogadores-por-clube, nunca probeado p/ Garrincha)
```

## Conclusão

Fato canônico saudável (2/3, mesma tripla, spans limpos). Falta **probe de 3 URLs corretas** (documentadas acima) para confirmar 1 domínio não-Wikimedia plausível → aí G1 fica pronto. Neste ciclo: **PARTIAL** por orçamento de probe esgotado em caminhos incorretos.
