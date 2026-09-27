# 🛠️ Setup — Ambiente Local (Nexus-Alpha)

Requisitos: **Python 3.10+**, **Git**, **Docker** (opcional, para Neo4j/Qdrant
locais), **Node 20** (opcional, para o frontend Next.js).

---

## 1. Clone e ambiente Python

```bash
git clone git@github.com:ENDARTStudios/Nexus-Alpha.git
cd Nexus-Alpha

python -m venv .venv
source .venv/bin/activate          # Git Bash/Linux/Mac
# .venv\Scripts\activate           # PowerShell/CMD

pip install -r requirements-dev.txt   # lite: suficiente para testes (sem torch/spacy)
```

> `requirements.txt` é o runtime completo (usado pelo worker no Actions).
> `requirements-tooling.txt` e `requirements-llamafactory.txt` são opt-in.

## 2. Variáveis de ambiente

```bash
cp .env.example .env    # .env é gitignored — NUNCA commite
```

Preencha conforme o cenário:

| Cenário | Mínimo necessário |
|---|---|
| Só testes | nada (suíte usa fakes) |
| Pipeline local com Neo4j docker | `NEO4J_URI=bolt://localhost:7687`, `NEO4J_USER`, `NEO4J_PASSWORD` |
| Ingest no Space de produção | `NEXUS_API_TOKEN`, `HF_SPACE_URL`, `HF_TOKEN` |
| Vetores persistentes | `QDRANT_HOST`, `QDRANT_API_KEY` |
| Chat com LLM | `NEXUS_LLM_BASE_URL`, `NEXUS_LLM_MODEL`, `NEXUS_LLM_API_KEY` (opcional — extrativo é o padrão) |

## 3. Infraestrutura local (opcional)

```bash
docker-compose up -d neo4j-db    # grafo local (bolt://neo4j-db:7687)
# Qdrant: via docker-compose ou Qdrant Cloud (QDRANT_HOST)
```

O app **não exige** bancos para subir: degrada para memória em processo
(`db_status: "demo-memory"`) — útil para desenvolver UI/chat.

## 4. spaCy (opcional, extração de melhor qualidade)

```bash
pip install spacy==3.7.2
python -m spacy download pt_core_news_sm
```
Sem spaCy, o `EntityExtractor` usa o fallback heurístico (`extractor.py`) —
o sistema continua funcionando.

## 5. Verificação

```bash
python -m pytest -q        # ~195 testes devem ficar verdes
python -m src.main "Inteligência Artificial"   # ciclo completo local (opcional)
```

## 6. Frontend Next.js (opcional)

```bash
npm install
npm run dev        # http://localhost:3000
```

- Sem `NEXT_PUBLIC_NEXUS_API_URL`, o frontend usa o **proxy server-side**
  (`/api/nexus/[...path]`) — que precisa de `NEXUS_SPACE_URL`, `HF_TOKEN`,
  `NEXUS_API_TOKEN` no `.env.local` (ou roteia para um Space vazio).
- Mock server para testes de UI sem backend:
  `python src/frontend/mock_server.py`.

## 7. Dashboard técnico (opcional)

```bash
pip install streamlit
streamlit run dashboard/app.py
```

## 8. Problemas comuns

| Sintoma | Causa provável | Solução |
|---|---|---|
| `pytest` falha por import | `PYTHONPATH` | `export PYTHONPATH=$(pwd)` |
| Neo4j auth error local | senha do container | ajuste `docker-compose.yml`/`.env` |
| Frontend sem dados | proxy sem segredos | preencha `NEXUS_SPACE_URL`/tokens ou use o mock |
| spaCy download falha | rede/proxy | siga com fallback heurístico (ok para desenvolver) |

Próximo passo: [`DEVELOPMENT.md`](./DEVELOPMENT.md) para o fluxo diário.
