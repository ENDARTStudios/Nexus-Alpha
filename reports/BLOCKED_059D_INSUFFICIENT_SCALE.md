# BLOCKED_059D_INSUFFICIENT_SCALE — Terceira família editorial + DISPUTOU

**Data:** 2026-09-27 · **Task:** #059D + #048.10E · **Classe:** **Cenário C — records insuficientes**

## Breadcrumb (EN Botafogo "Source: RSSSF Brasil – Botafogo")
A citação é **"Jogadores cedidos por clube na história da Seleção Brasileira" → `rsssfbrasil.com/sel/jogclub.htm`**
— o MESMO arquivo já explorado em #059C/#048.10D. **Não** existe página RSSSF Brasil dedicada ao Botafogo com
"Most appearances/goals" (a seção "Records" da EN wiki não tem citação RSSSF própria).

## Atlas `reports/broad_third_family_atlas_059d.json`
| Fonte | status | DEFENDEU | DISPUTOU | nota |
|---|---:|---:|---:|---|
| rsssfbrasil.com/sel/jogclub.htm | 200 | 2 | 0 | apenas Pelé+Jairzinho (allowlist) |
| rsssfbrasil.com/historical.htm | 200 | 0 | 0 | — |
| rsssfbrasil.com/national.htm | 200 | 0 | 0 | — |
| rsssf.org/tablesb/brazchamp.html | 200 | 0 | 0 | lista de campeões (não participantes) |
| rsssf.org/tablesb/brabra.html | 404 | — | — | inexistente |
| worldfootball.net (Botafogo/Santos) | **403** | — | — | `blocked_network` (bot protection) |
| national-football-teams.com/Garrincha | 200 | 0 | 0 | estrutura não rende player-club |
| fbref.com | **403** | — | — | `blocked_network` |

**`predicted_new_verified = 0`.**

## DISPUTOU
- Predicado **existe e é controlado** (`predicate_mapper`: disputou/participou/competed → DISPUTOU) — `disputou_predicate_controlled = true`.
- Mas narrativa wiki produce junk: `Botafogo --DISPUTOU--> do jogo de abertura` (rejeitado), `Santos --DISPUTOU--> amistoso` (genérico). Sem `CLUBE --DISPUTOU--> COMPETIÇÃO` limpo.
- Nenhuma fonte de participação (`brazchamp.html` = campeões) produziu colisão.
- **Não implementar** (dry-run zero-junk não atingido).

## Decisão (conservadora)
Sem mudança de runtime/seeds; sem worker (`predicted_new_verified = 0`). Fontes externas (worldfootball/fbref) bloqueadas por bot protection (403) — terceira família editorial não acessível por HTML estático.

## Próximo issue recomendado
```text
#048.10F / #059E — Terceira família editorial acessível (HTML estático, sem bot protection)
        ex.: bases de dados abertas/acadêmicas, arquivos públicos, datasets estáticos
#055 — Almanaque REST adapter apenas com Elite/licença (resolveria estruturalmente)
```

Não treinar. Não baixar quórum. Não forçar predicados/aliases. Não usar Almanaque sem licença.
