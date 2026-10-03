# DEFENDEU R4 decision packet (#048.10M.1.2 — viabilidade)

**Data:** 2026-10-03 · **Somente diagnóstico read-only. Nada executado.**

## Resumo executivo
Os 7 candidatos DEFENDEU estão **estruturalmente bloqueados por cobertura de seeds**:
nenhum possui página de jogador nas seeds do worker (apenas Garrincha tem a própria
página; os demais dependem de elencos de clube). Resultado do worker #048.10M.1.2:
0/7 verificados, +186 fatos não-verificados acumulados, zero junk/forbidden/regressão.
O quórum 3 exige páginas que confirmem a tripla — hoje só existem wiki pt/en para
Garrincha e 1 confirmação rsssfbrasil para Jairzinho.

## Estado atual
- verified: 20 (preservado; sem regressão no worker)
- Garrincha: 2/3 (pt+en wiki; probe R3 provou 3 páginas rsssf SEM Garrincha → FREEZE)
- Jairzinho: 1/3 com não-Wikimedia (rsssfbrasil corroborou no worker)
- Zito/Sócrates/Romário/CAT/Ceni: 0 domínios (ausentes do grafo)
- probe history: R2 6×404 (caminhos supostos), R3 3×200 sem Garrincha
- seeds: sem jogador além de Garrincha; aliases/núcleo: nada faltando

## Pergunta central
Existe caminho seguro para DEFENDEU **sem** alterar seeds/aliases/cognição central?

## Resposta: **NÃO** — para 6 dos 7 candidatos. Para Garrincha: **não** (R3 provou
que as páginas permitidas acessíveis não o mencionam). Qualquer avanço exige seed
extension (governada) — mudança de `config/seed_clusters.yaml`, que exige GO próprio.

## Opções
### A — Congelar DEFENDEU
- Condições: nenhuma. Riscos: nenhum técnico (grafo saudável; +186 fatos não-verificados
  acumulam confirmação natural em ciclos futuros).
- Benefício: foco no único bloqueio processual real: **#054.2** (boot-race voltou a
  ocorrer no R3 e já foi elevada a prioridade alta pelo Operador).

### B — R5 probe cirúrgico com URLs derivadas localmente
- Candidatos: Jairzinho (rsssf.org já 200 OK nos clusters), Zito/Ceni (wiki pages em
  clusters de clube).
- URLs propostas: derivadas de `seed_clusters.yaml` e logs do worker — **nunca supostas** (D9).
- Orçamento futuro: ≤3 URLs/candidato.
- Riscos: repetir o padrão R3 (200 sem menção) — aceitável, budget pequeno.

### C — Seed extension design→implementação separada
- Mudança mínima: clusters de jogador (pt/en wiki + 1 rsssf) por candidato — design em
  `defendeu_r4_seed_extension_design_048_10m_1_2.md`.
- Impacto: +6-18 URLs/ciclo; zero alteração de núcleo/aliases.
- Riscos: baixos (tabela no design).
- Pré-condições: GO explícito para tocar `seed_clusters.yaml`.

### D — Excluir candidatos problemáticos e reduzir piloto
- Não resolve: **todos** os 7 dependem de seed extension ou acumulação multi-ciclo.

### E — Pivotar para #054.2 antes de qualquer expansão
- Motivação: boot-race voltou a ocorrer (R3) e já foi elevada a prioridade alta pelo
  Operador; leituras vivas falsas-risk afetam qualquer ciclo futuro de worker.

## Recomendação conservadora
**Opção E primeiro** (#054.2 — confiabilidade de sinal, prioridade alta já declarada),
**depois Opção C** (seed extension governada) se o Operador quiser continuar DEFENDEU,
**Opção B** como passo intermediário barato (probes ≤3 URLs/candidato com origem
governada). **Opção A** permanece válida se o Operador preferir congelar.

## Não executado
Nenhum HTTP; nenhum worker; nenhum ingest; nenhuma seed; nenhum alias; nenhuma
cognição central; nenhum treino; nenhum deploy.
