# RUNBOOK_048_10M_EXPANSION_PLANNING

## Objetivo
Planejar **read-only** a próxima família não-VENCEU, sem executar worker.

## Pré-condições (verificadas em #048.10L.5)
1. #048.10L.5 hygiene ready (resíduo MINEIRAO->RJ removido);
2. `verified_facts_domain_independent = 20` estável;
3. `graph_scoped_gap = 0`; `fact_accounting_status = ok`;
4. `publisher_family_count = 3` / `effective_publisher_count = 3`;
5. `canonical_to_fact_gap` explicado (`scope_mismatch_non_blocking`);
6. nenhum resíduo GEO unverified perigoso (wrong-city) remanescente;
7. treino continua bloqueado (`records<50`, `environment_gate=false`).

## Candidatos a avaliar (somente atlas/dry-run)
- **DEFENDEU** com mais jogadores/clubes verificáveis por 3 domínios;
- **DISPUTOU** competição;
- **POSSUIR** estádio, **apenas** se houver 3 famílias independentes e zero junk;
- nunca aceitar bairro/estado/país/endereço/coordenada/cláusula/genérico/clube como objeto.

## Proibições
- não rodar worker; não treinar; não alterar quórum;
- não alterar `canonicalizer`/`predicate_mapper`/`span_validator`/`entity_aliases`;
- não usar Almanaque sem licença; não usar Transfermarkt/Soccerway;
- não escalar next-next GEO sem dry-run próprio e autorização.

> Este runbook é apenas planejamento. Não executar #048.10M neste task.
