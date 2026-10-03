# BLOCKED_048_10D — DEFENDEU scale-up esgotado + 3ª família bloqueada

**Data:** 2026-09-27 · **Task:** #048.10D · **Classe:** **Cenário C — records insuficientes**

## Trilho A — Escala DEFENDEU: esgotada (0 novos)
Atlas `reports/defendeu_scale_atlas_048_10D.json`:
| Fato | domínios | collision |
|---|---|---|
| PELÉ→SANTOS | pt.wiki+en.wiki+rsssfbrasil.com | full (já verificado em #059C) |
| GARRINCHA→BOTAFOGO | pt.wiki+en.wiki | partial (falta 3º domínio) |
| NILTON/DIDI/HELENO | — | no_collision |
| JAIRZINHO→BOTAFOGO | rsssfbrasil.com | no_collision (wiki pt/en não emite) |

- `rsssfbrasil.com/sel/jogclub.htm` contém **apenas** Pelé e Jairzinho (allowlist); **não** cita Garrincha/Nilton/Didi/Heleno/Quarentinha/Zagallo/Amarildo/Manga/Geninho (grep = 0).
- `rsssfbrasil.com/perfis.htm` = perfis de **membros** da RSSSF Brasil (não jogadores).
- Páginas `rsssf.org/tables/{58,62,70}full.html` = crônicas de partidas (escalações sem clube) → sem player-club.
- Jairzinho→Botafogo só existe na terceira fonte (wiki pt/en não emite a tripla) → 1 domínio.
- **`predicted_new_verified = 0`.**

## Trilho B — 3ª família predical: bloqueada (junk estrutural)
Atlas `reports/third_predicate_family_atlas_048_10D.json` → `eligible_families = 0`:
- `LOCALIZADO_EM` clube→cidade: só `BOTAFOGO→RIO` limpo (pt.wiki); en.wiki devolve `neighborhood of Botafogo`; sem 3º domínio. `SANTOS→SANTOS`, estádios = 0.
- `POSSUIR` clube→estádio: junk (`team POSSUIR Estádio`, `arena POSSUIR também`, `Santos POSSUIR em parceria…`).
- **Nenhuma família atinge colisão 3-domínios sem junk.**

## #053.1 — Telemetria de publisher family (adicionada, sem mudar métrica)
`evaluate_training_gate.py` agora expõe `unique_publisher_families`, `effective_publisher_count`,
`publisher_family_distribution`, `publisher_family_independence_ok`.
Resultado: `unique_publishers = 3` (domínios) mas `unique_publisher_families = 2`
(Wikimedia, **RSSSF** unificando rsssf.org+rsssfbrasil.com) → confirma o WARNING.
`verified_facts_domain_independent` e quórum **inalterados**.

## Estado do gate
```text
records_total = 11 (<50)
unique_predicates = 2 (VENCEU, DEFENDEU) (<3)
non_VENCEU_ratio = 0.09 (<0.30)
diversity_gate = false
publisher_independence_gate = true (domínios) / publisher_family = 2 (WARNING #053.1)
environment_gate = false (Python 3.14, sem GPU/LlamaFactory/flag)
training_recommended = false
```

## Próximo issue recomendado
```text
#059D — Atlas mais amplo de fontes estáticas independentes (não-Wikimedia) p/ player-club DEFENDEU
        (ex.: national-football-teams.com, worldfootball.net — testar read-only; provavelmente JS/ToS)
#048.10E — Terceira família predical segura via fonte estática com prosa declarativa limpa
#055 — Almanaque REST adapter apenas com Elite/chave/ToS
```

Não treinar. Não baixar quórum. Não forçar aliases/predicates. Não usar Almanaque sem licença.
