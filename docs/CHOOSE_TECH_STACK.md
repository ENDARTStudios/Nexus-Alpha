# 🧱 Choose Tech Stack — Justificativas (Nexus-Alpha)

Cada escolha abaixo foi feita sob três restrições simultâneas: **custo zero**,
**autonomia** (roda sozinho) e **verificabilidade** (anti-fake-news). "Alternativa
rejeitada" registra por que não.

---

## Backend core

| Escolha | Por quê | Alternativa rejeitada |
|---|---|---|
| **Python 3.10 + FastAPI** | async nativo (httpx/asyncio), tipagem pydantic, roda no HF Space com Docker | Node/Express (ecossistema de NLP em Python é superior); Flask (síncrono) |
| **Hugging Face Spaces** | free tier com Docker, domínio público, integração com HF Inference | Render/Railway (free tier instável/limitado); VPS (custo) |
| **Dockerfile.hf com deps lite** | `requirements-hf.txt` sem torch/spacy — boot rápido, memória dentro do free | imagem cheia (estoura RAM do free tier; treino é opt-in externo) |

## Persistência

| Escolha | Por quê | Alternativa rejeitada |
|---|---|---|
| **Neo4j AuraDB Free** | grafo nativo com Cypher; memória durável (`:Episodio`/`:Fato`) sobrevive a restart | Postgres+adjacency (queries de grafo verbosas); MongoDB (sem semântica de grafo); SQLite (sem serviço gerenciado grátis) |
| **Cypher puro sem APOC** | APOC não está garantido no AuraDB free — portabilidade | plugins (dependência de plano pago) |
| **Qdrant Cloud free + fallback in-memory** | vetores 384-dim gerenciados; degradação sem rede | Pinecone (sem free tier robusto); pgvector (exigiria Postgres gerenciado) |
| **Feature hashing para embeddings** | geração **local e gratuita**, determinística, sem API de embedding | OpenAI/HF embedding API (custo + chave + latência; e embedding nunca promove fato — ADR-003) |

## Coleta e NLP

| Escolha | Por quê | Alternativa rejeitada |
|---|---|---|
| **httpx + asyncio + BeautifulSoup** | scraping assíncrono leve, controle de delay/UA | Playwright no runtime (pesado para free tier; browser-use é opt-in) |
| **spaCy `pt_core_news_sm` + fallback heurístico** | NER/POS de qualidade no worker; fallback mantém o sistema de pé | LLM para tudo (custo, não-determinismo no refino — ADR-004) |
| **Refino determinístico (canonicalizer, predicate_mapper, span_validator)** | testável, auditável, barato no choke point do ingest | regras via LLM (não reproduzível); nada (fragmentos entravam no grafo — #046) |
| **Jina Reader / feedparser / yt-dlp (Agent Reach)** | converte JS-heavy/RSS/YouTube em texto sem chave e sem browser | browser-use por padrão (precisa LLM key + recursos) |

## Frontend

| Escolha | Por quê | Alternativa rejeitada |
|---|---|---|
| **Next.js 14 + Vercel** | proxy serverless server-side (esconde segredos do Space), free tier generoso | SPA falando direto no Space (expõe segredos); SSR próprio (custo) |
| **Tailwind + Framer Motion** | tema grafite/roxo consistente e movimento leve sem webfont | CSS-in-JS pesado; bibliotecas de animação maiores |
| **react-force-graph-2d** | visualização de grafo interativa client-side barata | D3 puro (mais código para o mesmo efeito); Neo4j Bloom (pago) |
| **Streamlit (dashboard operador)** | painel técnico em horas, reusa o runtime Python | segundo app Next.js (custo de manutenção duplicado) |

## CI/CD e Qualidade

| Escolha | Por quê | Alternativa rejeitada |
|---|---|---|
| **GitHub Actions** | cron 6h + gate de PR + backups semanais no mesmo lugar, grátis para repo privado (limites respeitados) | cron externo (outro ponto de falha); GitLab CI (repo já no GitHub) |
| **pytest (CI lite: `requirements-dev.txt`)** | suíte rápida (~195 testes) sem torch/spacy | CI com runtime completo (lento, caro, frágil) |
| **Anti-leak por grep no gate** | simples, auditável, zero dependência | secret-scanner pesado (falso positivo bloqueando tudo) |

## LLM e Treino

| Escolha | Por quê | Alternativa rejeitada |
|---|---|---|
| **Extrativo por padrão; LLM plugável (`NEXUS_LLM_BASE_URL`)** | chat honesto sem chave; quem quiser, conecta HF/OpenRouter/Ollama | LLM obrigatório (acopla o produto a custo/chave) |
| **LlamaFactory opt-in no Kaggle** | GPU grátis 30h/semana; fora do runtime e do CI | treinar no Space (impossível no free); LoRA no CI (estoura limites) |

## Regra de avaliação para o futuro

Toda proposta nova precisa responder: (1) cabe no free tier? (2) degrada
graciosamente sem serviço? (3) mantém determinismo/verificabilidade? Três
simes → registra em [`INTEGRATIONS.md`](./INTEGRATIONS.md) + ADR.
