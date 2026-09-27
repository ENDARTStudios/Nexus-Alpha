# 🚀 Production Deploy — Nexus-Alpha

Três planos independentes: **core** (HF Space), **frontend/proxy** (Vercel),
**worker** (GitHub Actions — sempre atualizado pelo `main`).

---

## 1. Pré-requisitos de deploy (checklist)

- [ ] Gate de CI verde no commit exato (`ai-validation.yml`).
- [ ] Suíte verde local (`pytest -q`).
- [ ] QA funcional concluído ([`QA_TESTING.md`](./QA_TESTING.md)).
- [ ] Snapshot de backup recente confirmado (`backups/`,
      [`BACKUP_DR.md`](./BACKUP_DR.md)).
- [ ] Docs de `docs/` atualizadas; `SPRINT.md` registra o item.
- [ ] Envs de produção conferidas (sem staging token em lugar nenhum).

## 2. Deploy do core — Hugging Face Space

1. **Build:** o Space usa `Dockerfile.hf` + `requirements-hf.txt`
   (lite — sem torch/spacy/transformers; LlamaFactory fica inerte por
   construção).
2. **Envs criptografadas no Space:** `NEO4J_URI` (`neo4j+s://` AuraDB),
   `NEO4J_USER`, `NEO4J_PASSWORD`, `NEXUS_API_TOKEN`, `QDRANT_HOST`
   (opcional), `QDRANT_API_KEY` (opcional), `NEXUS_LLM_*` (opcional),
   `NEXUS_BOOTSTRAP_SCHEMA=true`, CORS.
3. **Publicar:** push no repo do Space (ou `python scripts/deploy_hf_space.py`).
   ⚠️ O deploy do Space envia a **árvore de trabalho** (disco), não o commit —
   garanta staging limpo antes (lição do commit `712724d`).
4. **Smoke pós-deploy:**
   ```bash
   curl -s https://<user>-<space>.hf.space/health
   curl -s https://<user>-<space>.hf.space/api/metrics | python -m json.tool
   ```
5. **Validação cognitiva:** `cognitive_health.hebbian_consistency_check=true`;
   episódios preservados (restart **não** deve zerar `episodes` — se zerar,
   ver DR-1).

## 3. Deploy do frontend/proxy — Vercel

1. Push/merge em `main` → build Next.js (`npm run build`).
2. Envs de **produção** (Vercel): `NEXUS_SPACE_URL`, `HF_TOKEN`,
   `NEXUS_API_TOKEN` — **nunca** com `NEXT_PUBLIC_`.
3. `vercel.json` + `public/robots.txt` intactos (bloqueios `/api/`,
   `/_next/image*`); allowlist do proxy validada pelo CI.
4. Smoke: chat responde; painéis exibem dados reais; headers de segurança
   presentes.

## 4. Deploy do worker — GitHub Actions

- Sem deploy manual: o cron (`ai-cron.yml`, `0 */6 * * *`) roda o `main`
  mais recente. Para validar antes da próxima janela:
  `Actions → Nexus-Alpha Autonomous Worker Cron → Run workflow`.
- Secrets exigidos: `NEXUS_API_TOKEN`, `HF_SPACE_URL`, `HF_TOKEN`.
- O worker **complementa** seeds com os clusters curados
  (`config/seed_clusters.yaml`) — nada destrutivo.

## 5. Rollback

| Cenário | Ação |
|---|---|
| Core quebrado | re-deploy do commit/imagen anterior no Space (histórico do repo do Space); Space degrada mas **não para** por causa de banco |
| Frontend/proxy quebrado | Vercel → rollbacks instantâneos de deployment |
| Schema/migração ruim | restaurar snapshot mais recente ([`BACKUP_DR.md`](./BACKUP_DR.md) DR-2) + re-ingest controlado |
| Segredo exposto | rotacionar (DR-4) **antes** de qualquer re-deploy |
| Worker gerando ruído | os dados entram por quarentena/refino — investigar motivos; cron seguinte não acumula estado crítico (MERGE idempotente) |

## 6. Re-ingest controlado (protocolo de release com mudança de chave/canônica)

Padrão da sprint v1.13.0 (nota de fragmentação): nós históricos não se
fundem sozinhos.

1. Backup do grafo (snapshot atual).
2. Zerar grafo **apenas** se a sprint mapear (decisão explícita).
3. Deploy da nova versão.
4. Worker manual com seeds → comparar `raw_triples`, `canonical_triples`,
   `rejected_noise`, `distinct_canonical_keys`, `persisted_facts`,
   `duplicate_cross_domain`, `verified_facts`.
5. Registrar resultado em `SPRINT.md`. Métrica flat sem re-ingest **não**
   invalida o código (documentado no DoD v1.13).

## 7. Pós-deploy (primeiras 24h)

- [ ] 2+ ciclos do cron verdes.
- [ ] `/api/metrics` sem `unaccounted_raw` crescente.
- [ ] Quarentena recebendo rejeitados com motivos legítimos.
- [ ] Nenhuma regressão em `episodic_persistence_rate`.
- [ ] Monitoramento contínuo: [`MONITORING.md`](./MONITORING.md).
