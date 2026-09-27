# ⚡ Performance — Orçamentos e Limites (Nexus-Alpha)

Ambiente de produção é **free tier** (HF Spaces CPU, Qdrant Cloud free,
Neo4j AuraDB Free) — os orçamentos abaixo refletem o que foi **medido**, não
desejado.

---

## 1. Números medidos (produção/estresse)

| Métrica | Valor medido | Fonte |
|---|---|---|
| Inserção episódica sob estresse | ≈ **1.100 nós/s** | `scripts/stress_episodes.py` (1.000 nós sintéticos) |
| Leitura de episódios | **< 0,2 s** | idem, pós-índices (`created_at`, `last_seen_at`, `status`, `fact_hash`) |
| Retenção sob carga | 1.000 sintéticos podados corretamente (30d/10k) | idem |
| Sobrevivência a restart | 422 episódios persistidos | produção v1.12.0-beta |

## 2. Limites operacionais ativos

| Limiar | Valor | Onde |
|---|---|---|
| Payload de ingest | **≤ 1 MB** (acima: rejeitado) | `src/security/interceptor.py` |
| Brute-force | bloqueio após **10 tentativas** | `interceptor.py` |
| Rate limit chat | **5 req/min por IP** | `src/security/rate_limiter.py` |
| Quarentena de rejeições | volátil, **10k entradas** com rotação | `RejectionQuarantine` |
| Set de chaves contábeis | **10k**; acima → `accounting_mode: approximate_overflow` | `IngestAccounting` (`app.py`) |
| Simulação de enxame | **≤ 50 rodadas** | `SwarmSimulator` |
| Conexões de rede do miner | timeout 10s; 10 conexões / 5 keepalive | `config/settings.yaml` |
| Texto mínimo útil | 200 bytes após filtragem de ruído | `settings.yaml` |

## 3. Orçamento por ciclo do worker (6h)

O ciclo completo (minerar → extrair → ingest → consolidar) deve caber no
window do GitHub Actions (grátis: 60 min/job em runner público):

1. Mineração: seeds + clusters curados com delay dinâmico entre requisições
   (anti-bloqueio) — o delay é parte do custo, não desperdício.
2. Extração: spaCy PT no worker (fallback heurístico se o download do modelo
   falhar — `continue-on-error: true` no cron).
3. Ingest: HTTP único por payload; refino server-side determinístico (barato).
4. Consolidação + poda: transações Cypher em lote; sem cron extra
   (decisão v1.12: duplicaria escrita e criaria corrida).

## 4. Frontend

- **Zero webfont** (stack de sistema) — sem layout shift, sem download.
- `react-force-graph-2d` com cooldown de física; topologia via
  `/api/graph/topology` (payload pequeno, 1–2 saltos).
- Chat: skeletons + resposta extrativa (< 3s alvo p95 com grafo quente);
  histórico curto por `session_id` (sem sessão ilimitada em RAM).
- Proxy Vercel: serverless function com timeout padrão; nenhuma chamada
  encadeada ao Space além da necessária.

## 5. Diretrizes quando algo ficar lento

1. **Medir antes de otimizar:** `/api/metrics` (`ingestion_accounting`,
   `cognitive_health.retention_pressure`) e logs do worker.
2. `retention_pressure: high` → verificar poda (`prune_episodes`) e volume de
   ingest do dia.
3. Leitura de episódios > 0,5s → suspeitar de índice ausente/Neo4j degradado
   (ver [`MONITORING.md`](./MONITORING.md)).
4. **Proibido** acelerar reduzindo quórum, delays anti-bloqueio ou pulando o
   refino determinístico — performance nunca overriding segurança
   (ver [`RULES.md`](./RULES.md)).

## 6. Dívidas de performance conhecidas

- Embeddings por feature hashing (384-dim): rápido e gratuito, porém sem
  riqueza contextual — troca do modelo é item do roadmap (medir antes).
- Subgrafos do GraphRAG limitados a 1–2 saltos de propósito; expandir exige
  novo orçamento de latência.
