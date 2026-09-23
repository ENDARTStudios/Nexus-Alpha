# 🧭 ADR — Architecture Decision Records (Nexus-Alpha)

Formato curto: **Contexto → Decisão → Consequências**. Status: ✅ aceita ·
🔄 substituída · 🧊 suspensa. Decisões de sprint pontuais ficam em
`SPRINT.md`; entram aqui as duradouras.

---

## ADR-001 — Infraestrutura 100% free tier ✅
**Contexto:** projeto de pesquisa autônomo de longo prazo, sem orçamento.
**Decisão:** HF Spaces (core), GitHub Actions (worker/cron/backups), Qdrant
Cloud, Neo4j AuraDB Free, Vercel (proxy/frontend), Kaggle (treino opt-in).
**Consequências:** degradação graciosa obrigatória; Cypher sem APOC; deps
lite (`requirements-hf.txt`); free tier pode pausar (runbook DR-1).

## ADR-002 — Zero-trust de segredos ✅
**Contexto:** builds públicos do Actions e consoles do Space.
**Decisão:** zero credencial literal; `os.environ.get()`; Repository Secrets;
sanitizador de logs (`log_sanitizer.py` → `[MASKED]`); gate anti-leak no CI.
**Consequências:** todo payload/teste/doc é auditável; rotação resolve vazamento
histórico sem force-push.

## ADR-003 — Verificação por quórum de 3 domínios independentes ✅
**Contexto:** anti-fake-news; 4 URLs do mesmo domínio não corroboram.
**Decisão:** quórum **3**, contado por **domínio** (host, #049) — nunca por
URL; embedding nunca promove fato; sem quórum → quarentena.
**Consequências:** `verified_facts` honesto porém baixo; inegociável
([`RULES.md`](./RULES.md) §3).

## ADR-004 — Determinismo antes de IA no refino ✅
**Contexto:** LLM não é testável determinísticamente; refinamento é choke
point do grafo.
**Decisão:** canonicalizer (NFKD), predicate_mapper (vocabulário ≤30 + guard),
span_validator — funções **puras**, sem LLM/rede; LLM só em extração opcional
(`/api/extract`) e geração opcional no chat.
**Consequências:** comportamento auditável e testado; melhoria vira dados +
testes (ex.: #044), não prompt.

## ADR-005 — Memória episódica durável no Neo4j (v1.12.0-beta) ✅
**Contexto:** `data/` read-only e `$TMPDIR` efêmero no Space — episódios
morriam no restart.
**Decisão:** `:Episodio` com MERGE idempotente por `(fact_hash, day)`;
repetição incrementa `replays`; retenção 30d/10k; leitura com fallback
volátil (`source`).
**Consequências:** episódios sobrevivem (422 comprovados); índices exigidos;
retention_pressure monitorada.

## ADR-006 — Sem cron separado de consolidação ✅
**Contexto:** proposta de cron dedicado à consolidação.
**Decisão:** o worker de 6h já consolida; **não** criar cron extra.
**Consequências:** evita duplicação de `replays`/peso hebbiano e corrida no
Neo4j; consolidar manualmente (`POST /api/brain/consolidate`) é operacional,
não agendado.

## ADR-007 — Space privado + proxy server-side na Vercel ✅
**Contexto:** segredos não podem viver no frontend; Space público seria
enumerável.
**Decisão:** frontend só fala com `/api/nexus/[...path]` (Vercel), que injeta
`NEXUS_SPACE_URL`+`HF_TOKEN`+`NEXUS_API_TOKEN` server-side; `robots.txt` +
`vercel.json` blindam rotas; allowlist validada no CI (Node).
**Consequências:** nunca `NEXT_PUBLIC_` para segredo; alterar allowlist exige
teste.

## ADR-008 — Chat extrativo por padrão ✅
**Contexto:** alucinação de LLM contradiz o produto (fatos verificados).
**Decisão:** geração **extrativa** dos fatos recuperados (GraphRAG 1–2 saltos
+ vetor) como padrão; LLM remoto opcional (`NEXUS_LLM_BASE_URL`).
**Consequências:** zero dependência por padrão; respostas rastreáveis ao grafo.

## ADR-009 — Fine-tuning opt-in fora do runtime (v1.14.0) ✅
**Contexto:** treinar pesado no Space free é inviável; CI precisa ser leve.
**Decisão:** LlamaFactory externo (Kaggle); export apenas de fatos
**verificados**; sem torch no runtime/CI; `train` sem LlamaFactory → erro
amigável; gate `records≥50`, `verified_facts≥10`.
**Consequências:** `requirements-llamafactory.txt` isolado; Space fica inerte
ao treino; sem serving/merge de adapter por ora.

## ADR-010 — Gargalo final é semântico, não de infraestrutura ✅ (2026-09)
**Contexto:** #048 em produção: reputação resolvida (#056), páginas não-wiki
buscadas mas `entities_processed: 0`; wiki PT/EN geram triplas distintas para
o mesmo fato; `near_match.high = 0` lexical.
**Decisão:** congelar infraestrutura (freeze v1.13.0); atacar **equivalência
semântica entre fontes** — entity linking diagnóstico primeiro, aliasing
curado (#047) depois; re-ingest controlado para medir.
**Consequências:** nada de novos bancos/deps; embedding segue sugestão;
métrica flat sem re-ingest não invalida código.

## ADR-011 — Reputação de domínio por allowlist curada ✅ (#056)
**Contexto:** score padrão 0.60 < limiar 0.70 mandava todo publisher comum à
quarentena → cross-domain impossível por construção.
**Decisão:** `REPUTABLE_PUBLISHERS` com match por domínio registrável → 0.85;
`.org`/`.edu`/`.gov`/tech inalterados; baixa-confiança segue 0.4.
**Consequências:** curadoria manual das allowlists (revisar por sprint);
quórum permanece 3.

## ADR-012 — Governa de commits: 1 item por commit ✅ (reafirmada)
**Contexto:** exceções `2a41622` e `712724d` misturaram escopos e foram
mantidas por segurança operacional (sem force-push).
**Decisão:** staging explícito (`git add <paths>` + `git diff --cached`);
proibido `git add -A` sem inspeção; histórico nunca reescrito.
**Consequências:** rastreabilidade 1:1 entre issue/commit; erros de staging
se corrigem em commit novo.
