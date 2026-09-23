# 🧠 Memória — Modelo Cognitivo Persistente (Nexus-Alpha)

> Documentação operacional da memória. O desenho canônico está na seção 5 do
> [`ARCHITECTURE.md` raiz](../ARCHITECTURE.md); aqui estão semântica, limites,
> APIs e troubleshooting.

**Implementação:** `src/brain/memory.py`, `src/brain/regions.py`,
`src/database/graph_connector.py` · **Status:** v1.12.0-beta concluída

---

## 1. As três camadas

| Camada | Região (referência) | Onde vive | Semântica | Persistência |
|---|---|---|---|---|
| **Working** | Córtex pré-frontal | RAM (`BrainMemorySystem`) | 7 slots ativos, decaimento por minutos | ❌ efêmera por design |
| **Episódica** | Hipocampo | Neo4j `:Episodio` + JSONL volátil em `data/` (somente-leitura no Space) | fatos vividos no dia | ✅ durável (Neo4j) |
| **Semântica** | Córtex temporal | Neo4j `:Fato` / `:RELACIONA` | conhecimento consolidado (Hebbian) | ✅ durável |

Fluxo: `Working → Episódica (MERGE idempotente) → Semântica (consolidação)`.

## 2. Idempotência e chaves

- `fact_hash = sha256(subject|predicate|object)` normalizado
  (strip por campo + lower).
- MERGE por **`(fact_hash, day)`**: repetir o mesmo fato no mesmo dia
  incrementa `replays` — nunca cria micro-eventos (anti-inflação).
- A `chave` canônica de `:Fato` é calculada no ingest (fold NFKD + artigos
  iniciais + hífen, fallback UPPER para desconhecidas — #041).
- Índices no grafo: `created_at`, `last_seen_at`, `status`, `fact_hash`.

## 3. Limites operacionais (regra de ouro)

| Limite | Valor | Onde |
|---|---|---|
| Retenção episódica | **30 dias OU 10.000 nós** | `GraphConnector.prune_episodes` no ciclo de consolidação |
| Quórum de triangulação | **3 domínios distintos** | `NEXUS_VERIFY_QUORUM` / `settings.yaml` |
| Slots de working memory | 7 | `BrainMemorySystem` |
| Quarentena de rejeições | volátil `/tmp`, 10k com rotação | `RejectionQuarantine` |

`retention_pressure` (em `/api/metrics`): `low` <50%, `medium` <80%,
`high` ≥80% de 10k.

## 4. APIs de memória

| Endpoint | Método | Função |
|---|---|---|
| `/api/brain/stats` | GET | contadores derivados do grafo (hebbian/consolidado) |
| `/api/brain/episodes` | GET | leitura durável: tenta Neo4j; fallback volátil com `source: "volatile"` |
| `/api/brain/activate` | POST | ativação na working memory |
| `/api/brain/episode` | POST | registra episódio |
| `/api/brain/consolidate` | POST | consolida episódios → semântica (+poda de retenção) |

**Importante:** consolidar também via worker de 6h é proibido em cron extra —
decisão executiva: o worker de 6h já consolida; cron adicional duplicaria
`replays`/peso hebbiano e criaria corrida no Neo4j.

## 5. Saúde cognitiva

`GET /api/metrics → cognitive_health`:

```json
{
  "episodic_persistence_rate": 0.98,
  "hebbian_consistency_check": true,
  "retention_pressure": "low"
}
```

- `hebbian_consistency_check: false` indica queda do grafo (Neo4j).
- Contadores permanecem **derivados do grafo** (não mantidos em RAM).

## 6. Troubleshooting — "Space Restarted"

| Sintoma | Diagnóstico | Ação |
|---|---|---|
| Working memory zerou | **esperado** (efêmera por design) | nenhum |
| JSONL volátil zerou | esperado (`$TMPDIR` efêmero; `data/` é read-only no Space) | nenhum |
| `episodes = 0` | **NÃO esperado** — Neo4j indisponível | checar `/api/metrics` (`hebbian_consistency_check`) e instância AuraDB; restabelecida a conexão, episódios e fatos **voltam sem ação manual** |

Evidência de produção: **422 episódios sobreviveram a um restart do Space**;
estresse de 1.000 nós (≈1.100 nós/s, leitura <0,2s) com retenção limpando
sintéticos corretamente (`scripts/stress_episodes.py`).

## 7. Testes relacionados

`tests/test_brain_memory.py`, `tests/test_graph_connector.py`,
`tests/test_memory.py` — todos rodam no CI lite (sem Neo4j real: mocks/fakes).
