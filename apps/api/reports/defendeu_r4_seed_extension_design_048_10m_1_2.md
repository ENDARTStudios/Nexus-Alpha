# DEFENDEU governed seed extension design (#048.10M.1.2.R4 — APLICADO)

**Data:** 2026-10-03 · **Status:** DESIGN aplicado em 2026-10-07 com GO do Operador (Opção C, extensão mínima): probes validaram 12 URLs wiki (200+título) e `jogclub.htm` menciona apenas Jairzinho — só o cluster `jairzinho_botafogo` (3 domínios/2 publishers/não-Wiki) cumpre as regras estruturais e foi adicionado. Zito/CAT/Romário/Sócrates/Ceni permanecem fora até 3ª fonte não-Wiki validada (D9 — sem caminhos supostos). Detalhes e riscos originais do design preservados abaixo.

## Estado atual dos seeds
4+ clusters governados (`config/seed_clusters.yaml`) mirando **clubes/estádio/jogador único**:
Santos FC (pt/en + site + globo), Estádio Urbano Caldeira, Pelé (pt/en + rsssfbrasil
`sel/jogclub.htm`), Garrincha/Botafogo (pt/en Garrincha + Botafogo pt/en + site +
gazetadoparana), mais clusters de copalib/brazchamp (rsssf.org), Flamengo, Palmeiras,
São Paulo, Grêmio, Internacional — herança do piloto.

## Candidatos cobertos atualmente (por páginas de jogador próprias)
- **Garrincha** ✅ (página pt/en + gazetadoparana) — 2/3 domínios confirmados no grafo.

## Candidatos NÃO cobertos (páginas de jogador ausentes das seeds)
- **Jairzinho** — corroborado 1× por rsssfbrasil via páginas de clube do worker; falta 2.
- **Zito, Sócrates, Romário, Carlos Alberto Torres, Ceni** — 0 domínios no grafo
  (páginas pt/en.wikipedia dos jogadores não estão em nenhum cluster).

## Mudança mínima proposta, NÃO aplicada
Para cada jogador ausente, adicionar um bloco de cluster no padrão existente
(`candidate_cluster`): pt.wikipedia + en.wikipedia da página do jogador +
1 fonte rsssf não-Wikimedia plausível por clube. **Mínimo para o quórum:**
as páginas pt/en já estão nos clusters de clube existentes (elencos) — na prática,
a extensão mínima real é **1 seed rsssf/jogador por candidato** ou confiar na
mineracão cumulativa dos clusters de clube já ativos.

## Impacto no worker
- +6 a +18 URLs novas (1-3 por jogador); volume dentro do orçamento atual
  (worker já processa 72 fontes por ciclo; rate limits #054.1: ingest 120/min
  por token — margem ampla).

## Riscos
- **junk:** baixo (páginas wikipedia de jogadores são declarativas; o span validator
  rejeita fragmentos — 0 junk no worker #048.10M.1.2)
- **forbidden:** zero (fontes permitidas)
- **span-break:** baixo (padrão já provado nas páginas de clube)
- **homonímia:** baixo (Zito/Sócrates/Ceni têm aliases canônicos no atlas)
- **alias:** nenhum novo necessário (aliases já no atlas)
- **core:** nenhuma alteração (extrator/predicados já suportam DEFENDEU)
- **rate limit:** sem risco (incremento ~10-15% no volume do ciclo)
- **volume:** +18 URLs/ciclo no máximo

## Pré-condições para futuro GO
1. GO explícito do Operador para alterar `config/seed_clusters.yaml`.
2. URLs validadas manualmente (HTTPS/200/menção plausível) — **sem probe de
   caminhos supostos** (D9): derivar de `Sel/jogclub` do rsssfbrasil já 200 OK
   e das páginas wiki de clubes já mineradas.
3. Suite verde + anti-leak.
4. Worker único pós-extension com baseline/post/fact-level validation por candidato.

## Recomendação
VIAVEL e de baixo risco — mas só executar **após** o Operador decidir que DEFENDEU
vale a extensão (alternativa: congelar DEFENDEU e priorizar #054.2). A página
`rsssfbrasil.com/sel/jogclub.htm` (200 OK, já nas seeds do cluster Pelé) é o
caminho natural não-Wikimedia — porém **não menciona Garrincha** (R3 provou);
para os outros jogadores precisa de verificação de conteúdo por URL específica.
