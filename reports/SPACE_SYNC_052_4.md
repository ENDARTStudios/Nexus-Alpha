# SPACE_SYNC_052_4

**Data:** 2026-09-28
**HEAD local:** `c0c3160`
**Objetivo:** sincronizar o source do HF Space para o HEAD atual via Git, **somente fast-forward**.

## Diagnóstico (read-only)

| Item | Valor |
|---|---|
| Space ID | `endartstudios/nexus-alpha` |
| Space `sha` | `85355c6d0e32651eebe4acdf1eb7c7103f6fc245` |
| Space `lastModified` | `2026-09-25T03:03:55Z` |
| Space `private` | `true` |
| Space `sdk` / `stage` | `docker` / `RUNNING` |
| Git remoto acessível | **SIM** (`git ls-remote` OK) |
| Backup do Space | **SIM** (sha `85355c6d…`) |
| Fetch `space/main` | OK |
| `space/main` ancestral de `HEAD`? | **NÃO** (`merge-base --is-ancestor` exit 128) |
| Push permitido | **NÃO** |
| Push executado | **NÃO** |
| Telemetria pós-sync | **ainda ausente** |

## Causa

O repositório do Space é um **snapshot de deploy** com histórico **próprio** (top-level:
`app.py`, `src/`, `config/`, `Dockerfile`, `README.md`, `requirements*.txt`, `.gitattributes`, `.gitignore`).
Ele **não** é descendente do `main` do GitHub (históricos divergentes), então um push
`space LOCAL_SHA:main` **não** seria fast-forward. Por política, **não** forçamos push.

O mecanismo correto é o deploy por **upload de subconjunto** (`scripts/deploy_hf_space.py` →
`HfApi.upload_folder` de `app.py`, `src/**`, `config/**`, `requirements*.txt`; `README_HF.md`→`README.md`;
`Dockerfile.hf`→`Dockerfile`), não um push do repositório inteiro.

## Segurança

- Nenhum worker executado; nenhuma escrita em Neo4j/Qdrant; nenhum treino.
- Nenhum force-push (GitHub ou Space).
- Backup do Space em `.autonomous/space_sync/` (**não commitado**); askpass temporário **não commitado**.

## Classificação

`BLOCKED_052_4_SPACE_HISTORY_DIVERGED` (ver `reports/BLOCKED_052_4_SPACE_SYNC.md`).
