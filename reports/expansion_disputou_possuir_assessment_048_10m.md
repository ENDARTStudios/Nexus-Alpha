# #048.10M — Avaliação ontológica (DISPUTOU / POSSUIR / DEFENDEU)

Inspeção read-only de `predicate_mapper.py`, `canonicalizer.py`, `extractor.py`, `table_extractor.py`.

## Evidência de código

| Predicado | Mapeado? | Caminho de extração? | Classificação |
|---|---|---|---|
| **DEFENDEU** | SIM (`EXTRA_PREDICATES` + `EXTRA_MAP`) | SIM — frame nominal (`jogou pelo/pela/por`) + **target-aware** `JOGADOR→CLUBE` (#048.10B) + `table_extractor` club-context (#059C) | **SUPPORTED_NOW** |
| **VENCEU** | SIM | SIM (tabela #058 + narrativa) | SUPPORTED_NOW (já em uso) |
| **LOCALIZADO_EM** | SIM | SIM (geo parser/OSM) | SUPPORTED_NOW (já em uso) |
| **DISPUTOU** | SIM (`EXTRA_MAP`) | **NÃO** — ausente de `_NOMINAL_FRAMES` e de `DEFAULT_PREDICATES` | **NOT_RECOMMENDED_NOW** (exige frame de extração no `extractor.py` — off-limits neste plano) |
| **POSSUIR** | SIM (base + `EXTRA_MAP`) | PARCIAL — frame estreito `home ground is`; mas genéricos `possui/tem/has` estão em `DEFAULT_PREDICATES` | **NOT_RECOMMENDED_NOW** (alto risco semântico: posse genérica; exigiria aperto de frame/validator) |
| **TREINOU** | SIM (`EXTRA_MAP`) | NÃO — sem frame | NOT_RECOMMENDED_NOW (fora de escopo) |

## Veredito
- **DEFENDEU**: prioridade máxima, suportado hoje sem alterar ontologia central.
- **DISPUTOU/POSSUIR**: **não** podem ser escalados agora. Qualquer suporte exigiria alterar
  `extractor.py` (frame) e/ou endurecer `span_validator`/`predicate_mapper` — **não** fazer neste plano.

```text
BLOCKED_048_10M_REQUIRES_GLOBAL_ONTOLOGY_CHANGE
escopo: DISPUTOU (frame de extração) e POSSUIR (risco semântico de posse genérica)
proposta: issue separado #048.10N para novo frame + testes de span/predicado.
```
