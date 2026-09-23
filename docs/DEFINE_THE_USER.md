# 👤 Define the User — Personas do Nexus-Alpha

Quem usa o Nexus-Alpha e o que cada um precisa. Este documento fundamenta
prioridades do [`PRD.md`](./PRD.md) e decisões de UX do [`DESIGN.md`](./DESIGN.md).

---

## Persona 1 — Operadora do ecossistema (ENDARTStudios) 🧑‍💻

| | |
|---|---|
| **Quem é** | desenvolvedora/governadora do projeto; mantém sprints, seeds e infra free tier |
| **Objetivo** | ecossistema saudável rodando sozinho; detectar degradação antes que vire perda de conhecimento |
| **Superfícies** | Dashboard Streamlit, `/api/metrics`, logs do GitHub Actions, `SPRINT.md` |
| **Dores** | free tier pausa AuraDB; métricas que superestimam (lição #049); gargalos silenciosos |
| **Critério de sucesso** | `cognitive_health` verde sem intervenção semanal; auditorias com números claros |
| **O que ela NÃO quer** | métrica vaidosa; fallback silencioso; ter que reingestionar por causa de restart |

## Persona 2 — Visitante do site (consumidor do chat) 💬

| | |
|---|---|
| **Quem é** | pessoa leiga ou entusiasta que chega ao site (ex.: fã de futebol, curiosos de IA) |
| **Objetivo** | perguntar e receber uma resposta factual confiável, sem enrolação |
| **Superfície** | `ChatWidget` (bolha no site, tema grafite/roxo, pt-BR) |
| **Dores** | respostas genéricas/alucinadas de bots comuns; não sabe de onde vem a informação |
| **Critério de sucesso** | resposta extrativa rastreável ao grafo; "não sei" honesto quando não há fato verificado |
| **O que ele NÃO quer** | cadastro, pop-up, espera sem feedback, jargão técnico |

**Implicação de produto:** o chat **nunca** inventa — responde apenas com
fatos recuperados (extrativo padrão). "Nexus não sabe" é resposta válida.

## Persona 3 — Agente autônomo (worker) 🤖

| | |
|---|---|
| **Quem é** | o próprio sistema operando sem humano: cron 6h no GitHub Actions |
| **Objetivo** | completar ciclo minerar→extrair→ingest→consolidar dentro do window grátis |
| **Superfícies** | `scripts/worker_cycle.py`, `AntiBlockSystem`, `/api/ingest` |
| **Dores** | bloqueio de IP de datacenter; páginas JS sem conteúdo declarativo; payload >1MB |
| **Critério de sucesso** | job verde; `unaccounted_raw = 0`; quarentena crescendo com motivos legítimos |
| **Restrição** | delays anti-bloqueio são parte do design — nunca otimizar cortando-os |

## Persona 4 — Pesquisador de conhecimento / treino 🧪

| | |
|---|---|
| **Quem é** | a própria operadora em "modo pesquisa": exportar conhecimento para SFT/LoRA, rodar auditorias |
| **Objetivo** | dataset limpo de fatos verificados; entender por que o grafo tem o tamanho que tem |
| **Superfícies** | `scripts/train_lora.py`, `scripts/audit_post_clean.py`, `audit_cross_source.py`, `/api/extract` |
| **Critério de sucesso** | gate de treino (`records≥50`, `verified_facts≥10`) atingido honestamente |
| **O que ela NÃO quer** | dataset inflado por duplicatas de mesma fonte (por isso `verified_facts` é por domínio) |

## Anti-personas (fora de escopo de propósito)

- **Gestor de tráfego/SEO:** o site não é produto de conteúdo (ver
  [`SEO.md`](./SEO.md)); não otimizamos pageviews.
- **Consumidor de API pública de terceiros:** não expomos API pública
  estável/SLA — o proxy existe para o nosso frontend.
- **Usuário rastreável:** não perfis, não cookies de marketing
  ([`COMPLIANCE.md`](./COMPLIANCE.md)).

## Hierarquia de prioridades derivada

1. Integridade do conhecimento (Persona 3 correto > Persona 2 encantado).
2. Observabilidade honesta (Persona 1 decide tudo a partir de métricas).
3. Simplicidade do chat (Persona 2: rápido, honesto, sem cadastro).
4. Reprodutibilidade da pesquisa (Persona 4: seed determinística, export limpo).
