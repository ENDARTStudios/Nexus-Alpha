# BLOCKED_048_10 — Diversificação de fatos verificados (atlas read-only)

**Data:** 2026-09-27 · **Task:** #048.10 · **HEAD:** `62b835d`
**Atlas:** `reports/diversified_fact_families_atlas_048_10.json` · **cap de produção:** 25

## Resultado

```text
families_evaluated   = 4  (DEFENDEU, LOCALIZADO_EM clube, LOCALIZADO_EM estádio, POSSUIR)
eligible_families    = 0  (cap=25, produção)
predicted_new_verified = 0
```

| Família | Fato | confs (cap=25) | doms | verified |
|---|---|---:|---:|---|
| DEFENDEU | GARRINCHA→BOTAFOGO | 2 | 2 | ✗ |
| DEFENDEU | PELÉ→SANTOS | 2 | 1 | ✗ |
| LOCALIZADO_EM | BOTAFOGO→RIO | 0 | 0 | ✗ |
| LOCALIZADO_EM | SANTOS→SANTOS | 0 | 0 | ✗ |
| LOCALIZADO_EM | NILTON SANTOS→RIO | 0 | 0 | ✗ |
| LOCALIZADO_EM | URBANO CALDEIRA→SANTOS | 1 | 1 | ✗ |
| POSSUIR | SANTOS→URBANO CALDEIRA | 0 | 0 | ✗ |
| POSSUIR | BOTAFOGO→NILTON SANTOS | 0 | 0 | ✗ |

## Causas-raiz (evidência)

1. **Extrator narrativo produz junk, não o fato limpo** (probe EN/PT Botafogo):
   - `team --POSSUIR--> Estádio Olímpico Nilton Santos` (sujeito genérico "team"; a frase "The team's home ground is X" não resolve o clube como sujeito);
   - `botafogo --LOCALIZADO_EM--> neighborhood of Botafogo` (invertido/bairro);
   - `Mourisco Mar/Caio Martins --LOCALIZADO_EM--> botafogo` (invertido).
   Nenhum gate de tabela cobre essas famílias — só honras (`honours_competition_year`) está implementado.
2. **Cap de produção = 25**: `PELÉ→SANTOS` só chega a `confs=3` com cap=300 (o 3º URL — pt Santos — traz a tripla além do índice 25). Elevar o cap é uma mudança ampla (mais ruído por página) — não autorizado neste ciclo.
3. **Sem 3º domínio p/ não-VENCEU**: RSSSF só cobre títulos; pt.wiki+en.wiki dão no máximo 2 domínios (a verificação exige `confs>=3 AND doms>=2`, o que exigiria ≥2 URLs Wikimedia distintas por fato).

## Decisão (conservadora)

- **Sem mudança de runtime** (`table_extractor.py`, `extractor.py`, `canonicalizer.py` intocados).
- **Sem mudança de seeds** (não escalar apenas VENCEU, conforme diretriz).
- **Sem aliases/predicates novos** (sem evidência de divergência de rótulo; a falha é de extração de sujeito/objeto, não de alias).
- **Sem worker run** (nada novo a medir; evita reprocessar as mesmas páginas).

## Próximo issue recomendado

```text
#048.10B — Extração controlada player→club (DEFENDEU) + club→stadium (POSSUIR/MANDA_EM)
            e stadium/club→city (LOCALIZADO_EM): resolver clube como SUJEITO
            (hoje o extrator devolve "team"/genérico/invertido).
#059     — Fontes estáticas independentes adicionais (não-Wikimedia) para fatos não-título.
#053     — Independência editorial (Wikimedia+RSSSF = 2 publishers).
```

Não abrir #047.2/#045.3 (sem evidência de divergência de rótulo). Não treinar. Quórum permanece 3.
