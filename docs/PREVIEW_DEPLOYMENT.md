# 🧷 Preview Deployment — Validar antes de produção (Nexus-Alpha)

Como testar mudanças de ponta a ponta **sem tocar a produção** (Space + Vercel
+ worker de cron).

---

## 1. Níveis de preview

| Nível | O que valida | Como |
|---|---|---|
| **L1 — Local puro** | lógica, refino, degradação | `pytest -q` (fakes; sem bancos) |
| **L2 — Local com bancos** | Cypher real, MERGE, índices | `docker-compose up -d neo4j-db` + `NEO4J_URI=bolt://localhost:7687` |
| **L3 — Space de staging** | integração real ingest→grafo | Space HF **separado** (recomendado) ou deploy manual no Space principal em janela controlada |
| **L4 — Vercel preview** | frontend + proxy | deploy de preview automático da Vercel em branch/PR |

## 2. L3 — Space de staging

1. Criar Space privado irmão (mesmo `Dockerfile.hf`, `requirements-hf.txt`).
2. Configurar variables/secrets do staging: `NEO4J_URI` (pode ser o AuraDB
   real **apenas se** aceitar risco de dados de teste — preferível um
   instance separado ou o docker local exposto via túnel), `NEXUS_API_TOKEN`
   distinto do de produção, `QDRANT_HOST` opcional.
3. Subir a imagem: `python scripts/deploy_hf_space.py` (apontando para o
   Space de staging).
4. Smoke:
   ```bash
   curl -s https://<staging>.hf.space/health
   curl -s -X POST https://<staging>.hf.space/api/ingest \
        -H "X-Nexus-Token: $TOKEN_STAGING" -H "Authorization: Bearer $HF_TOKEN" \
        -H "Content-Type: application/json" -d '<payload pequeno>'
   curl -s https://<staging>.hf.space/api/metrics | python -m json.tool
   ```
5. Critérios de aceite: `/health` ok; ingest com contadores coerentes;
   degradação testada (derrube o grafo e verifique `demo-memory`).

## 3. L4 — Vercel preview (frontend)

1. Abra PR/branch → Vercel gera URL de preview automaticamente.
2. No preview, o proxy usa as **mesmas** envs de produção por padrão — para
   apontar ao staging, sobrescreva `NEXUS_SPACE_URL`/tokens apenas no
   escopo de preview (Vercel → Settings → Environment Variables → Preview).
3. Testar: chat (extrativo + fallback de rede), painéis (BrainPanel
   `source`), KnowledgeGraph, acessibilidade por teclado.

## 4. Worker em modo preview

Ciclo manual controlado (nunca esperar o cron para validar):

```bash
export NEXUS_API_TOKEN=<staging-token> HF_SPACE_URL=https://<staging>.hf.space HF_TOKEN=...
PYTHONPATH=. python scripts/worker_cycle.py
```

Capturar baseline/post de `ingestion_accounting` e `verification`
(padronizado no #048) e registrar em `SPRINT.md`.

## 5. Regras

1. **Nunca** apontar preview para o grafo de produção sem snapshot recente
   (`db-backup.yml`) — re-ingest de teste infla `replays` (inofensivo) mas
   polui métricas de contabilidade.
2. Tokens de staging ≠ tokens de produção.
3. Preview não altera allowlists de segurança nem quórum.
4. Limpar dados de teste do staging (zerar collection/grafo de staging) ao
   encerrar a validação.

## 6. Checklist antes de promover preview → produção

- [ ] Suíte verde no commit exato que vai para produção.
- [ ] Smoke L3 concluído e registrado.
- [ ] Envs de produção corretas (tokens de **produção**).
- [ ] Plano de rollback definido ([`PRODUCTION_DEPLOY.md`](./PRODUCTION_DEPLOY.md) §5).
