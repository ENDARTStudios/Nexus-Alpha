# 📐 Arquitetura do Ecossistema Nexus-Alpha

Este documento descreve o fluxo de dados, a topologia de rede e os protocolos de
segurança do ecossistema **Nexus-Alpha**, uma inteligência artificial autônoma de
mineração semântica e auto-evolução operando em infraestrutura **Custo Zero**
(GitHub Actions grátis + Hugging Face Spaces + Qdrant Cloud + Neo4j AuraDB).

---

## 🔄 1. Pipeline de Dados e Fluxo Macroscópico

O ciclo de vida do conhecimento na Nexus-Alpha segue um fluxo unidirecional e
assíncrono dividido em 5 etapas:

```text
[ GitHub Actions ] (A cada 6 horas — cron '0 */6 * * *')
       │
       ▼ (Gera Cabeçalhos Furtivos: User-Agent/Referer rotativos + delay dinâmico)
[ AntiBlockSystem ] ───► [ Web Scraping ] (Coleta dados brutos)
                               │
                               ▼ (Gera Triplas {sujeito, predicado, objeto})
                        [ NLPExtractor ]  (spaCy + fallback heurístico)
                               │
                               ▼ (POST Seguro /api/ingest — X-Nexus-Token + Bearer HF)
                    [ Hugging Face Spaces ] (FastAPI Core — app.py)
                               │
             ┌─────────────────┴─────────────────┐
             ▼ (Memória Sementica)               ▼ (Córtex de Grafos Relacionais)
     [ Qdrant Cloud ]                     [ Neo4j AuraDB ]
(store_memory / vetor 384-dim)         (ingest_payload / nós + relações)
```

> **Nota de resiliência (verificado em 2026-09-09):** quando o Neo4j ou o Qdrant
> estão indisponíveis, o `app.py` degrada graciosamente. O loop de ingestão
> responde com `"db_status": "demo-memory"` (persistência em memória) e os fatos
> sem triangulação suficiente são enviados à **quarentena**, nunca descartados.

---

## 🗂️ 2. Topologia dos Módulos Core

O repositório é estritamente modularizado para garantir a manutenibilidade por
agentes independentes:

*   **`src/miner/` (Camada de Ingestão):** scripts de raspagem e o `anti_block.py`.
    É responsável por disfarçar as requisições mudando `User-Agents` e inserindo
    atrasos dinâmicos para evitar banimentos por IPs de nuvem. Ainda contém
    `web_miner.py` (scraper assíncrono), `quarantine.py` (fila local de rejeitados)
    e `security_protocol.py` (cálculo de confiança de domínio).

*   **`src/cognition/` (Camada Cognitiva):** Orquestra o *Chain-of-Thought*
    (`reasoning_engine.py` + `reasoning.py`), o processamento de linguagem natural
    (`nlp_extractor.py` com fallback heurístico do `extractor.py`), o RAG ativo
    (`rag_engine.py`), as memórias locais (`memory.py`) e a auto-reflexão noturna
    (`reflection.py`). Traduz blocos de texto bruto em relacionamentos semânticos
    `{sujeito, predicado, objeto}`.

*   **`src/security/` (Camada de Defesa):** executa a quarentena e a blindagem
    contra falsas informações por triangulação cruzada (`triangulation.py`),
    exigindo confirmação em múltiplos domínios independentes. Inclui o
    `log_sanitizer.py` (mascara credenciais com `[MASKED]` em logs públicos) e o
    `interceptor.py` (rejeita payloads >1MB e bloqueia brute-force).

*   **`src/database/` (Camada de Persistência):** conectores assíncronos oficiais —
    `graph_connector.py` (Neo4j / Cypher via `schema.cypher`) e `vector_connector.py`
    (Qdrant / fallback em memória). Traduzem os contratos de dados JSON-LD em
    queries estruturadas para os SGBDs em nuvem.

---

## 🔐 3. Protocolo Zero-Trust e Secrets Management

*   **Isolamento Estático:** nenhuma credencial de banco de dados (`NEO4J_PASSWORD`)
    ou token de comunicação de API (`NEXUS_API_TOKEN`) existe de forma literal no
    código do repositório — a leitura é sempre via `os.environ.get()`.

*   **Injeção Dinâmica:** o GitHub Actions consome chaves via *Repository Secrets*
    (`secrets.NEXUS_API_TOKEN`, `secrets.HF_SPACE_URL`, `secrets.HF_TOKEN`) e as
    injeta no processo do worker. O Hugging Face Docker consome variáveis de
    ambiente criptografadas do próprio Space.

*   **Sanitização Atômica:** o registrador do sistema (`log_sanitizer.py`) intercepta
    as mensagens de erro em tempo de execução e substitui qualquer padrão que
    lembre chaves privadas por `[MASKED]`, evitando vazamento acidental nos
    consoles de build públicos do GitHub Actions.

---

## 💾 4. Resiliência e Continuidade

*   **Gate de Qualidade (`ai-validation.yml`):** roda em cada `push` a `main`/`dev`
    e em `pull_request`. Impede merges que quebrem a integridade do código (pytest),
    que vazem segredos (auditoria anti-leak via `grep`) ou que violem a governança
    (checagem de conformidade com `SPRINT.md`).

*   **Estratégia de Redundância (`db-backup.yml`):** um worker autônomo executa
    dumps semanais automáticos das estruturas do Neo4j a cada domingo às 00:00
    (`0 0 * * 0`), gerando um snapshot JSON segura em `backups/` e efetuando o
    commit+push automático via *Nexus-Alpha Bot*, garantindo recuperação total.

---

## 🏗️ 5. Stack e Infraestrutura (Zero Cost)

| Componente | Papel | Camada/Arquivo |
|---|---|---|
| GitHub Actions | Agendador + runner do worker | `.github/workflows/ai-cron.yml` |
| Hugging Face Spaces | Core FastAPI (porta 7860) | `app.py`, `Dockerfile.hf` |
| Neo4j AuraDB | Grafo de conhecimento | `src/database/graph_connector.py` |
| Qdrant Cloud | Memória vetorial semântica | `src/database/vector_connector.py` |
| Next.js + Tailwind + Motion | Dashboard de monitoramento | `src/frontend/`, `dashboard/` |

---

## 📜 6. Como Executar

```bash
# Ciclo completo local
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
docker-compose up -d neo4j-db        # opcional
python -m src.main "Inteligência Artificial"

# Testes (35 casos)
python -m pytest tests/ -v
```

> O ciclo em produção é auto-acionado a cada 6 horas pelo cron do GitHub Actions
> (`ai-cron.yml`) e pode ser disparado manualmente via `workflow_dispatch`.
