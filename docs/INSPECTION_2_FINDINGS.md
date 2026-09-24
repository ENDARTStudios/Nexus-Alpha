# Inspeção 2 — Colapso cross-lingual PT vs EN (findings)

**Data:** 2026-09-23 · **Modo:** read-only · **Arquivo bruto:** `reports/inspection_2_croslingual.json` (gitignored)
**Script reproduzível:** `scripts/inspect_cross_lingual_divergence.py`
**Testes:** `tests/test_inspect_cross_lingual_divergence.py`

## Contexto

Após o re-ingest controlado pós-`#045.1` (Cenário C: `duplicate_cross_domain=0`,
`facts_with_two_or_more_domains=0`, `verified=0`), a Inspeção 2 mediu se a
divergência PT↔EN era **alias de entidade (H1)** ou **ruído de span (H3)**.

## Resultado quantitativo

| Métrica | Valor |
|---|---|
| Grafo `pt_only` / `en_only` / `both` | 78 / 32 / **0** |
| `cross_candidates` (mesmo predicado + overlap de token) | **0** |
| Alvos offline re-extraídos | 5 (santos_fc, estádio, pelé, garrincha, botafogo) |
| `shared_canonical_keys` | **0** em todos os alvos |
| Near-misses (mesmo predicado + overlap) | 44 |
| Linhas de divergência campo-a-campo | 63 |
| Auto-classificador H1 | 63/63 (**ingênuo — ver abaixo**) |
| Botafogo EN | **HTTP 404** (URL seed inválida) |

## Classificação corrigida (manual)

| Hipótese | Auto | Corrigido | Issue |
|---|---|---|---|
| H1 alias real | 63 | **≈0** (nenhum par de entidade limpa idêntica colide) | `#047` (boundary + dicionário, não “só alias”) |
| H2 predicate mapper | 0 | **0** (filtro near-miss força mesmo predicado) | N/A na Inspeção 2 |
| H3 span/fragmento | 0 | **≈60+** dominante | `#058.2` (fechado) + residual extractor |
| H4 normalização | 0 | **0** (chaves diferem após fold) | OK |

### Exemplos H3 (por alvo)

| Alvo | Campo | PT | EN | Leitura |
|---|---|---|---|---|
| santos_fc | subject | `E O` | `AND` | palavra fechada only |
| santos_fc | subject | `E O` | `AMERICANO MOVED TO` | falso par via `SER` |
| santos_fc | subject | `TIME SANTISTA` | `MY TIME IN FOOTBALL` | overlap só `TIME` |
| santos_fc | object | `PAULO` | `PAULO AND PALMEIRAS` | truncamento `São Paulo`→`PAULO` |
| estadio | subject | `ENFIM` | `NAMING OF THE STADIUM` | discurso vs fragmento |
| pele | subject | `PELE` | `PELE SAID HE` | cauda verbal EN |
| garrincha | subject | `GARRINCHA` | `ALTHOUGH GARRINCHA` | conectivo inicial EN |
| garrincha | subject | `GARRINCHA` | `ESTADIO NACIONAL MANE GARRINCHA` | entidades **distintas** (falso alias) |
| garrincha | object | `SELECIONADO` | ×7 objetos EN distintos | falso par por predicado `SER` |

## Por que o auto-classificador marca tudo como H1?

`classify()` em `scripts/inspect_cross_lingual_divergence.py` só olha
`subject`/`object` divergentes e assume alias. Ele **não** distingue:

1. fragmento sintático (H3) vs entidade real divergente (H1);
2. falso par (overlap de token genérico como `A`, `TIME`, `PAULO`);
3. entidades realmente diferentes que compartilham um token (`GARRINCHA` vs estádio).

O relatório bruto permanece a fonte da verdade; a leitura acima é a revisão humana.

## Causas estruturais confirmadas

1. **Boundary do extractor** — cauda verbal (`PELE SAID HE`), conectivo inicial,
   truncamento de topônimo (`São Paulo`→`PAULO` em algum caminho de captura).
2. **Sem dicionário bilíngue curado** — `Santos FC` vs `Santos Football Club`
   nunca colapsam (limitação honesta do fold puro, documentada em
   `tests/test_canonicalizer.py`).
3. **spaCy ON (worker) vs OFF (CI/offline)** — assinaturas de span diferentes
   entre ambientes; re-extração offline subestima qualidade live.

## Decisão

- `#058.2` (span validator v2) — executado em `d5a083c`.
- **`#047`** — dicionário bilíngue + boundary fix do extractor (não “medir agora”).
- Re-ingest controlado **somente após** `#047` + golden cross-lingual verde.
- `#047` (só alias passivo) **não** resolveria H3 sozinho; boundary é obrigatório.

## Anti-leak / invariantes

- Script read-only: Neo4j SELECT, HTTP GET Wikipedia, sem `/api/ingest`, sem Qdrant.
- Sem segredos no YAML de aliases; sem LLM; quórum permanece 3.
