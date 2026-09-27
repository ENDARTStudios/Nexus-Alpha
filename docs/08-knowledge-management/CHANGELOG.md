# 📝 Changelog — Nexus-Alpha

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).
Versão no esquema `MAJOR.MINOR.PATCH-FASE`. O registro de execução detalhado
(evidências, métricas, decisões) vive em `SPRINT.md`.

---

## [1.14.0] — LlamaFactory opt-in

### Adicionado
- Export de fatos verificados do grafo → dataset Alpaca/JSONL
  (`src/training/dataset.py`; gera `data/sft/nexus_verified_facts.jsonl` +
  `dataset_info.json`).
- Geração de config LoRA/SFT YAML para LlamaFactory
  (`src/training/config.py`, `config/llamafactory/sft_lora.yaml`).
- CLI opt-in `scripts/train_lora.py` (`export|config|train`) com erro
  amigável quando LlamaFactory ausente.
- `requirements-llamafactory.txt` (isolado; fora do runtime e do CI).

### Decidido
- Fine-tuning roda externamente (Kaggle/GPU, Python 3.11–3.13); sem serving
  ou merge de adapter; gate de treino `records>=50`, `verified_facts>=10`.

## [1.13.0] — Qualidade semântica (freeze de infraestrutura)

### Adicionado
- **#041** `canonicalizer.py`: fold NFKD + artigos iniciais + hífen na chave
  de lookup; fallback determinístico UPPER para desconhecidas.
- **#042** `triple_refiner.py` via `map_predicate`; EXTRA_MAP reflexivo;
  golden cross-extractor.
- **#043** Guard `validate_predicate` no `EntityExtractor` (spaCy e fallback)
  + observabilidade de rejeição (`rejection_reasons`, `top_invalid_predicates`).
- **#044** Aliases PT de alta confiança (ter→POSSUIR, incluir→CONTIENE,
  aplicar→UTILIZA, publicar/desenvolver→PRODUZ); motivos `modal_predicate`/
  `ambiguous_predicate`.
- **#046** `cross_source_audit.py` + `scripts/audit_cross_source.py`
  (read-only, sem promover fato).
- **#049** Corroboração por **domínio** distinto: `f.domain` em `:FonteWeb`,
  `count(DISTINCT ff.domain)`, bloco `verification` em `/api/metrics`.
- **#050** `span_validator.py`: rejeita objetos-fragmento (data, oração,
  locução, pronome, quantificador); dry-run 39/106 rejeitados.
- **#051** `domain_coverage()`, `reconcile_pipeline()` +
  `scripts/audit_post_clean.py`.
- **#052** `IngestAccounting` em `app.py`: chaves canônicas distintas vs
  ocorrências; classificação de duplicação (same_url/same_domain/cross_domain);
  bloco `ingestion_accounting`.
- **#056** `REPUTABLE_PUBLISHERS` em `security_protocol.py`: allowlist curada
  por domínio registrável → score 0.85; testes `test_domain_reputation.py`.
- **#048** Clusters curados de domínios independentes (futebol) em
  `config/seed_clusters.yaml` + `src/miner/seed_loader.py`; integração no
  `scripts/worker_cycle.py`; testes `test_seed_clusters.py`.

### Descoberto
- Produção (#048): gargalo final é **equivalência semântica entre fontes**
  (PT/EN, sinônimos) — não cobertura nem reputação. Ver [`RESEARCH.md`](./RESEARCH.md).
- Dívidas registradas: #053 (eTLD+1), #054 (ontologia temporal),
  #055 (Almanaque API).

### Governança
- Exceções mantidas sem revert: commits `2a41622` (escopos misturados) e
  `712724d` (hotfix + alinhamento de Space); regra de 1 item por commit
  reafirmada.

## [1.12.0-beta] — Memória Episódica Durável

### Adicionado
- `:Episodio` durável no Neo4j (`fact_hash + day`, MERGE idempotente,
  `replays` incrementa).
- Índices: `created_at`, `last_seen_at`, `status`, `fact_hash`.
- Leitura durável com fallback volátil (`source: "neo4j"|"volatile"`).
- Retenção **30 dias OU 10.000 nós** com marcação de consolidados.
- `cognitive_health` em `/api/metrics` (`episodic_persistence_rate`,
  `hebbian_consistency_check`, `retention_pressure`).
- `scripts/stress_episodes.py` (estresse: 1.000 nós ≈1.100 nós/s, leitura <0,2s).

### Evidência
- 422 episódios sobreviveram a restart do Space.
- Decisão executiva: **sem** cron separado de consolidação (o worker de 6h já
  consolida; cron extra duplicaria replays e criaria corrida no Neo4j).

## [1.11.0-alpha] — Proxy server-side + métricas duráveis
- Space privado; proxy Vercel (`/api/nexus/[...path]`); allowlist de rotas
  (validação Node no CI); métricas duráveis.

## [1.10.0-alpha] — Painel Cérebro
- Contrato normalizado de `/api/brain/stats`; `BrainPanel` read-only.

## [1.9.0-alpha] — Cérebro espelhado
- working/episódica/semântica + consolidação Hebbiana (`src/brain/`).

## [1.8.0-alpha] — Motor GraphRAG
- Subgrafos 1–2 saltos no chat (`src/cognition/graph_rag.py`).

## [1.7.0-alpha] — Consolidação + rate limiting
- Caixa alta total; `rate_limiter.py` (5 req/min por IP no `/api/chat`).

## [1.6.0-alpha] — Extração LLM canônica
- `LLMCanonicalExtractor` + `/api/extract`.

## [1.5.0-alpha] — Resolução vetorial de entidades
- `entity_resolver.py` + schema canônico via LLM.

## [1.4.0-alpha] — Chat + seeds + quórum modular
- Atendimento conversacional (`chat_service.py`, `llm_provider.py` extrativo),
  malha de seeds, `NEXUS_VERIFY_QUORUM`.

## [1.3.0-alpha] — Tooling
- MCP (codebase-memory, agentmemory), subagents, Agent Reach (Jina/RSS/yt-dlp),
  browser-use opt-in, Strix opt-in.

## [1.2.0-alpha] — Estabilidade
- Correção de `/health`; TLS `neo4j+s://` do AuraDB.

## Não publicado / backlog
- #047 aliasing curado; entity linking diagnóstico; #053/#054/#055;
  span validator v2 — ver [`ROADMAP.md`](./ROADMAP.md) e [`TASKS.md`](./TASKS.md).
