# 📚 Documentação — Nexus-Alpha

> Índice central da documentação. Todo documento de projeto vive aqui; a
> governança de sprint permanece em `SPRINT.md` (raiz) e a arquitetura
> canônica em `ARCHITECTURE.md` (raiz) + [`ARCHITECTURE.md`](./ARCHITECTURE.md).

**Repositório:** ENDARTStudios/Nexus-Alpha (privado) · **Última revisão:** 2026-09-23

---

## 🧭 Como usar esta documentação

| Você quer… | Comece por |
|---|---|
| Entender o que o produto é | [`PRD.md`](./PRD.md) |
| rodar o projeto localmente | [`SETUP.md`](./SETUP.md) |
| entrar como novo dev/agente | [`ONBOARDING.md`](./ONBOARDING.md) |
| entender o fluxo de dados | [`ARCHITECTURE.md`](./ARCHITECTURE.md) |
| consumir a API | [`API.md`](./API.md) |
| contribuir com código | [`DEVELOPMENT.md`](./DEVELOPMENT.md) + [`STYLE_GUIDE.md`](./STYLE_GUIDE.md) |
| abrir/revisar PR | [`CODE_REVIEW.md`](./CODE_REVIEW.md) |
| publicar em produção | [`PRODUCTION_DEPLOY.md`](./PRODUCTION_DEPLOY.md) |

## 📖 Documentos de Produto

- [`PRD.md`](./PRD.md) — Requisitos de produto: visão, personas, funcionalidades e métricas.
- [`DEFINE_THE_USER.md`](./DEFINE_THE_USER.md) — Personas e público-alvo definidos.
- [`ROADMAP.md`](./ROADMAP.md) — Evolução planejada por versão (freeze v1.13.0, dívidas #053–#055).
- [`TASKS.md`](./TASKS.md) — Backlog ativo e rastreio de tarefas (espelho dos issues #036–#056).

## 🏗️ Técnica

- [`ARCHITECTURE.md`](./ARCHITECTURE.md) — Camadas, pipeline de dados, modelo cognitivo e stack.
- [`API.md`](./API.md) — Referência completa dos endpoints FastAPI (`app.py`).
- [`INTEGRATIONS.md`](./INTEGRATIONS.md) — Neo4j, Qdrant, HF Spaces, Actions, LLM, Jina Reader, LlamaFactory.
- [`MEMORY.md`](./MEMORY.md) — Modelo de memória (working/episódica/semântica), limites e troubleshooting.
- [`ANALYTICS.md`](./ANALYTICS.md) — Métricas de `/api/metrics`: cognitivas, extração, verificação, contabilidade.
- [`CONTENT.md`](./CONTENT.md) — Política de conteúdo minerado, seeds curados e qualidade semântica.
- [`ADR.md`](./ADR.md) — Registro de decisões de arquitetura (ADR-001…ADR-010).

## 🛡️ Qualidade e Operação

- [`RULES.md`](./RULES.md) — Regras invioláveis do projeto (governança, segurança, escopo).
- [`DESIGN.md`](./DESIGN.md) — Design system: tema grafite/roxo elétrico, Motion, componentes.
- [`STYLE_GUIDE.md`](./STYLE_GUIDE.md) — Estilo de código Python/TS e convenções de commit.
- [`TESTING.md`](./TESTING.md) — Suíte pytest (~195 testes), como rodar e o que cobre.
- [`SECURITY_REVIEW.md`](./SECURITY_REVIEW.md) — Auditoria anti-leak, zero-trust e checklist de segurança.
- [`CODE_REVIEW.md`](./CODE_REVIEW.md) — Checklist de revisão e gate de CI.
- [`ERROR_HANDLING.md`](./ERROR_HANDLING.md) — Degradação graciosa, fallbacks, quarentena e códigos de erro.
- [`BACKUP_DR.md`](./BACKUP_DR.md) — Backups semanais do Neo4j e recuperação de desastres.
- [`MONITORING.md`](./MONITORING.md) — Saúde: `/health`, `/api/metrics`, alertas e troubleshooting.
- [`PERFORMANCE.md`](./PERFORMANCE.md) — Orçamentos de performance, resultados de estresse e limites.
- [`ACCESSIBILITY.md`](./ACCESSIBILITY.md) — Acessibilidade do dashboard e do widget de chat.
- [`COMPLIANCE.md`](./COMPLIANCE.md) — Conformidade: LGPD, robots.txt, ética de mineração.
- [`SEO.md`](./SEO.md) — Blindagem anti-scraping, robots.txt e indexação controlada.
- [`AEO.md`](./AEO.md) — Answer Engine Optimization: respostas diretas (snippets/assistentes).
- [`GEO.md`](./GEO.md) — Generative Engine Optimization: citação em engines generativos.
- [`AIO.md`](./AIO.md) — AI Optimization: governança de crawlers de IA, llms.txt e legibilidade para agentes.
- [`CHANGELOG.md`](./CHANGELOG.md) — Histórico de versões v1.2.0-alpha → v1.14.0.

## 🔄 Processo de Trabalho

- [`ONBOARDING.md`](./ONBOARDING.md) — Onboarding de novos desenvolvedores/agentes.
- [`SETUP.md`](./SETUP.md) — Instalação passo a passo do ambiente.
- [`DEVELOPMENT.md`](./DEVELOPMENT.md) — Fluxo de desenvolvimento diário e regras de commit.
- [`TESTING.md`](./TESTING.md) — Estratégia de testes.
- [`TASK_BREAKING_DOWN.md`](./TASK_BREAKING_DOWN.md) — Como decompor funcionalidades em issues.
- [`SECURITY_REVIEW.md`](./SECURITY_REVIEW.md) — Processo de revisão de segurança.
- [`CODE_REVIEW.md`](./CODE_REVIEW.md) — Processo de code review.
- [`PREVIEW_DEPLOYMENT.md`](./PREVIEW_DEPLOYMENT.md) — Deploys de preview (Vercel/Space).
- [`QA_TESTING.md`](./QA_TESTING.md) — QA funcional antes de produção.
- [`PRODUCTION_DEPLOY.md`](./PRODUCTION_DEPLOY.md) — Deploy em produção (Space + Vercel + worker).
- [`MONITORING.md`](./MONITORING.md) — Monitoramento pós-deploy.
- [`ITERATION.md`](./ITERATION.md) — Ciclo de iteração/sprint e retroalimentação.
- [`RESEARCH.md`](./RESEARCH.md) — Pesquisas abertas e evidências (bottleneck semântico #048).

## ⚠️ Convenções

1. **Idioma:** toda a documentação é escrita em pt-BR.
2. **Verdade:** este índice não sobrepõe `SPRINT.md` — em conflito, vence a sprint vigente.
3. **Atualização:** qualquer PR que mude comportamento documentado deve atualizar o doc correspondente (o gate de CI valida `SPRINT.md`; os demais são responsabilidade do autor).
