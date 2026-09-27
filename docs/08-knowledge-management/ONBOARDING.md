# 🚀 Onboarding — Nexus-Alpha

Guia de entrada para novos desenvolvedores e agentes autônomos. Tempo de
leitura: ~15 min. Ao final você saberá governar, rodar e contribuir.

---

## 1. O que é este projeto

Nexus-Alpha é uma IA autônoma que **minera a web semanticamente**, extrai
triplas `{sujeito, predicado, objeto}`, verifica cada fato contra
**3+ domínios independentes** e só então consolida conhecimento num grafo
Neo4j — tudo em infraestrutura gratuita (HF Spaces + GitHub Actions +
Qdrant Cloud + Neo4j AuraDB Free).

Leia nesta ordem:
1. [`PRD.md`](./PRD.md) — o produto e suas funcionalidades.
2. [`RULES.md`](./RULES.md) — as regras invioláveis (**obrigatório**).
3. [`../ARCHITECTURE.md`](../ARCHITECTURE.md) — pipeline e módulos.
4. [`SETUP.md`](./SETUP.md) — ambiente local.

## 2. Primeiros passos (checklist)

```bash
git clone git@github.com:ENDARTStudios/Nexus-Alpha.git && cd Nexus-Alpha
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt                  # lite: sem torch/spacy
cp .env.example .env                                 # preencha NEO4J_* e NEXUS_API_TOKEN
python -m pytest -q                                  # deve ficar verde (~195 testes)
```

- Sem Neo4j local? Os testes usam fakes — CI roda sem bancos.
- Painel rápido: `streamlit run dashboard/app.py` (opcional).
- Pipeline completo local: `python -m src.main "Inteligência Artificial"`.

## 3. Regras que você não pode quebrar (resumo)

A lista completa está em [`RULES.md`](./RULES.md); as 6 fatais:

1. **Escopo fechado:** só altere o que `SPRINT.md` mapeia.
2. **1 item por commit**, staging explícito, **nunca `git add -A`**.
3. **Zero segredo no código** — só `os.environ.get()`; o gate anti-leak
   falha o build.
4. **Quórum de triangulação = 3 domínios** — inegociável.
5. **Determinismo antes de IA** — nada de LLM nas etapas determinísticas;
   embedding nunca promove fato.
6. **Testes verdes** em todo push (`python -m pytest -q`), sem depender de
   torch/transformers/spacy.

## 4. Mapa do repositório (5 minutos)

```
app.py                    FastAPI core (Space, :7860) — todos os endpoints
src/miner/                coleta, anti-bloqueio, reputação, seeds, quarentena
src/cognition/            extração/refino determinístico, RAG, chat, reflexão
src/database/             graph_connector (Neo4j) + vector_connector (Qdrant)
src/security/             triangulation, log_sanitizer, interceptor, rate_limiter
src/brain/                working/episódica/semântica + Hebbian
src/simulation/           SwarmSimulator (/api/simulate)
src/training/             export SFT/LoRA (opt-in, fora do runtime)
src/frontend/ + src/app/  Next.js (ChatWidget, BrainPanel, proxy Vercel)
dashboard/                Streamlit (operador)
scripts/                  worker_cycle, train_lora, auditorias, deploy
config/                   settings.yaml, security_policies.json, seed_clusters.yaml
tests/                    ~195 testes (rodam no CI lite)
.github/workflows/        ai-validation (gate), ai-cron (6h), db-backup (dom. 00:00)
SPRINT.md                 governança vigente — leia antes de qualquer PR
```

## 5. Fluxo de trabalho

1. Escolha uma tarefa mapeada em `SPRINT.md` / [`TASKS.md`](./TASKS.md).
2. Branch curta a partir de `main` (ou direto em `main` para itens pequenos
   aprovados — o projeto commita direto com staging explícito).
3. Implemente + teste (ver [`DEVELOPMENT.md`](./DEVELOPMENT.md)).
4. `git add <paths>` → `git diff --cached` → commit convencional
   (`feat(miner): ...`, `fix(cognition): ...`, `docs(...)`).
5. O gate de CI roda: anti-leak → pytest → conformidade SPRINT.md →
   allowlist do proxy. Verde = pronto.

## 6. Como o sistema roda em produção (mental model)

```
GitHub Actions (cron 6h) → scripts/worker_cycle.py
   → minera seeds + clusters → extrai triplas
   → POST /api/ingest (X-Nexus-Token) no Space (app.py)
   → refino determinístico → grafo/quarentena → consolidação
Vercel (proxy) → frontend público fala com o Space privado
Domingos 00:00 → db-backup.yml → snapshot JSON do Neo4j em backups/
```

## 7. Onde procurar ajuda

- **Saúde do sistema:** [`MONITORING.md`](./MONITORING.md) (`/health`, `/api/metrics`).
- **"Por que está assim?":** [`RESEARCH.md`](./RESEARCH.md) (evidências) e
  [`ADR.md`](./ADR.md) (decisões).
- **Endpoints:** [`API.md`](./API.md).
- **Histórico e decisões de sprint:** `SPRINT.md` (raiz) e [`CHANGELOG.md`](./CHANGELOG.md).

## 8. Critérios de "primeira contribuição aceita"

- [ ] Ambiente local rodando com testes verdes.
- [ ] 1 PR/commit seguindo as regras de escopo e staging.
- [ ] Doc de `docs/` atualizada caso o comportamento tenha mudado.
- [ ] Nenhum segredo, nenhuma dependência pesada nova, nenhum APOC no Cypher.
