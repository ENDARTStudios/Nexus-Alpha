# 💾 Backup e Disaster Recovery — Nexus-Alpha

Infraestrutura de custo zero exige estratégia de backup **dentro do free
tier**. O desenho canônico está na seção 4 do [`ARCHITECTURE.md` raiz]
(../ARCHITECTURE.md); aqui está o runbook.

---

## 1. O que é durável × efêmero

| Dado | Onde vive | Destino se tudo cair |
|---|---|---|
| Episódios (`:Episodio`) | **Neo4j AuraDB** (durável) | snapshot semanal + reingest |
| Fatos semânticos (`:Fato`/`:RELACIONA`) | Neo4j AuraDB | snapshot semanal + reingest |
| Vetores (Qdrant) | deriváveis do grafo | **regeneráveis** por `embeddings.py` (feature hashing local) — sem backup dedicado |
| Working memory | RAM | **efêmera por design** — não se recupera |
| JSONL volátil (`data/`, `$TMPDIR`) | disco do Space | efêmero; `data/` é read-only no Space |
| Quarentena de rejeições | `/tmp` (10k rotativo) | dispensável (são rejeitados) |
| Config de seeds | `config/seed_clusters.yaml` | versionado no git |

**Consequência-chave:** o Neo4j é o único estado irrecuperável → é o alvo do
backup. Tudo o mais é derivável ou efêmero por design.

## 2. Backup semanal automatizado

- **Workflow:** `.github/workflows/db-backup.yml`
- **Agenda:** todo domingo às 00:00 UTC (`cron: '0 0 * * 0'`)
- **O que faz:** worker autônomo conecta no AuraDB, exporta snapshot JSON das
  estruturas do grafo para `backups/` e faz commit+push como **Nexus-Alpha Bot**.
- Credenciais via Repository Secrets (nunca no repositório).

### Verificação manual (mês)
```bash
ls backups/                      # 1 snapshot por semana
python -c "import json,sys; json.load(open('backups/<latest>.json'))"  # JSON válido
```

## 3. Runbooks de desastre

### DR-1 — Space reiniciou e `episodes = 0`
1. Checar `/api/metrics` → `cognitive_health.hebbian_consistency_check`.
2. `false` ⇒ Neo4j indisponível: verificar instância AuraDB (free tier pode
   pausar por inatividade) e credenciais (`NEO4J_URI` etc. no Space).
3. Restabelecida a conexão, episódios/fatos **voltam sem ação manual**
   (comprovado: 422 episódios sobreviveram a restart).

### DR-2 — AuraDB perdido/corrompido
1. Provisionar AuraDB Free novo (`neo4j+s://`).
2. Restaurar do snapshot mais recente de `backups/` (Cypher LOAD/reattach
   conforme schema do snapshot JSON).
3. Rodar re-ingest controlado se o snapshot for antigo
   (protocolo em `SPRINT.md`: backup → zerar → deploy → worker com seeds →
   comparar métricas).
4. Regenerar vetores Qdrant a partir do grafo (embeddings locais).

### DR-3 — Qdrant indisponível/limpo
1. Sem ação emergencial: sistema degrada para vetores in-memory.
2. Recriar collection `nexus_semantic_memory` (384-dim) e reindexar a partir
   dos fatos do grafo.

### DR-4 — Segredo vazado
1. **Rotacionar imediatamente**: `NEXUS_API_TOKEN`, `HF_TOKEN`,
   `NEO4J_PASSWORD`, `QDRANT_API_KEY` (Space + Repository Secrets + `.env`).
2. Auditar histórico (`git log -S "<segredo>"`) — sem force-push; se o
   segredo está no histórico, a rotação resolve.
3. Registrar incidente em `SPRINT.md` (apêndice).

### DR-5 — Worker travou / cron falhou
1. `Actions → ai-cron.yml` → inspecionar último run vermelho.
2. Re-executar via `workflow_dispatch` após corrigir a causa.
3. Ciclos perdidos são auto-recuperáveis: nada se acumula de estado crítico;
   seeds são idempotentes (MERGE + `replays`).

## 4. Regras

1. Backup **nunca** contém segredo (apenas estrutura de grafo; sanitizar).
2. Snapshot semanal é o mínimo — aumentar frequência só se o DoD da sprint
   mapear (custo de Actions).
3. **Proibido** armazenar backup fora do repositório (nuvem pessoal, Drive).
4. Toda mudança de schema do grafo deve manter compatibilidade com o formato
   de snapshot ou documentar migração no PR.
