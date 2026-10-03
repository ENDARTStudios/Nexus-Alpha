# #048.10M.1.2 — DEFENDEU pilot worker result

**Data:** 2026-10-03 · **Classificação:** `BLOCKED_048_10M_1_2_WORKER_FAILED` (fact-level FAIL 0/7; worker tecnicamente saudável, sem junk/forbidden/regressão/fonte proibida)

## Snapshot
- arquivo: `reports/defendeu_pilot_worker_aurasnapshot_048_10m_1_2.json`
- created_at: 2026-10-03T01:55:55Z · 5789 nós (2023 Conceito, 3278 Episodio, 412 Fato, 76 FonteWeb) · 4144 relações
- restore executado: **NÃO**

## Baseline (pré-worker)
verified=20 · records=20 · fact=412 · concept=2023 · quorum=3 · gsg=0 · fas=ok · ss=0 · unaccounted=0 · top_invalid=[] · fpg=0 · publisher_families=3 · hebbian=True

## Worker
- comando: `PYTHONPATH=. python scripts/worker_cycle.py` (comando canônico do repo; env via `.env` com `HF_SPACE_URL` mapeado de `NEXUS_SPACE_URL`)
- execução única: **sim** (2 tentativas de bootstrap anteriores falharam **antes de qualquer efeito**: 1ª sem env → erro de secrets, zero fetch; 2ª órfã do launcher durante warm-up pós-mineração, zero ingest — grafo verificado inalterado)
- retry: não · fontes usadas: seeds governadas existentes (wiki pt/en clubes+jogadores-parciais, rsssf.org — extração tabular confirmada em `copalib.html`/`brazchamp.html`, gazetadoparana, ge.globo, GEO/OSM, queries de IA do escopo original)
- rate limit events: **0** (nenhum 403/429/challenge; limites do #054.1 respeitados)
- ingest: **72 fontes, todas 200 OK** · consolidação: 200 (consolidated=1053, episodes_marked=3402, pruned=0)

## Post
verified=**20** · records=20 · fact=**598** (+186) · concept=**2136** (+113) · quorum=3 · gsg=0 · fas=ok · ss=0 · unaccounted=0 · top_invalid=[] · fpg=0 · publisher_families=3 · hebbian=True

## Fact-level
expected=7 · verified=**0** · presente-não-verificado: Garrincha (2 domínios), Jairzinho (1 domínio, não-Wikimedia ✓) · ausentes do grafo: Zito, Sócrates, Romário, Carlos Alberto Torres, Ceni (5) · junk=0 · forbidden=0 · source violations=0

## Causa raiz (incidente: `defendeu_pilot_worker_incident_048_10m_1_2.md`)
Seeds do worker miram **clubes**, não **páginas de jogadores** → 5/7 candidatos nem
chegaram ao grafo; e quórum 3 não fecha em ciclo único (corroboração é cumulativa).

## Regressões
current_verified: não · venceu: não · localizado_em: não · defendeu existente: não

## Classificação
`BLOCKED_048_10M_1_2_WORKER_FAILED` (FAIL de fact-level 0/7 — packet §7; worker saudável; expansão congelada; decisão do Operador entre as 3 opções do incidente)
