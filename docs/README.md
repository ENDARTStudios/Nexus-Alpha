# 📚 Documentação — Nexus-Alpha

> Índice central da documentação. Todo documento de projeto vive aqui, sob as
> pastas numeradas abaixo; a governança de sprint permanece em `SPRINT.md`
> (raiz) e a arquitetura canônica em `ARCHITECTURE.md` (raiz) +
> [`02-architecture-design/ARCHITECTURE.md`](./02-architecture-design/ARCHITECTURE.md).

**Repositório:** ENDARTStudios/Nexus-Alpha (privado) · **Última revisão:** 2026-09-27

---

## 🧭 Como usar esta documentação

| Você quer… | Comece por |
|---|---|
| Entender o que o produto é | [`01-product-discovery/PRD.md`](./01-product-discovery/PRD.md) |
| rodar o projeto localmente | [`03-development-process/SETUP.md`](./03-development-process/SETUP.md) |
| entrar como novo dev/agente | [`08-knowledge-management/ONBOARDING.md`](./08-knowledge-management/ONBOARDING.md) |
| entender o fluxo de dados | [`02-architecture-design/ARCHITECTURE.md`](./02-architecture-design/ARCHITECTURE.md) |
| consumir a API | [`04-api-integrations/API.md`](./04-api-integrations/API.md) |
| contribuir com código | [`03-development-process/DEVELOPMENT.md`](./03-development-process/DEVELOPMENT.md) + [`02-architecture-design/STYLE_GUIDE.md`](./02-architecture-design/STYLE_GUIDE.md) |
| abrir/revisar PR | [`06-devops-deployment/CODE_REVIEW.md`](./06-devops-deployment/CODE_REVIEW.md) |
| publicar em produção | [`06-devops-deployment/PRODUCTION_DEPLOY.md`](./06-devops-deployment/PRODUCTION_DEPLOY.md) |

## 📖 01 — Descoberta de Produto (`01-product-discovery/`)

- [`PRD.md`](./01-product-discovery/PRD.md) — Requisitos de produto: visão, personas, funcionalidades e métricas.
- [`DEFINE_THE_USER.md`](./01-product-discovery/DEFINE_THE_USER.md) — Personas e público-alvo definidos.
- [`ROADMAP.md`](./01-product-discovery/ROADMAP.md) — Evolução planejada por versão (freeze v1.13.0, dívidas #053–#055).
- [`LEGAL_TERMS.md`](./01-product-discovery/LEGAL_TERMS.md) — Termos legais _(esqueleto)_.
- [`PRICING_MONETIZATION.md`](./01-product-discovery/PRICING_MONETIZATION.md) — Precificação e monetização _(esqueleto)_.

## 🏗️ 02 — Arquitetura e Design (`02-architecture-design/`)

- [`ARCHITECTURE.md`](./02-architecture-design/ARCHITECTURE.md) — Camadas, pipeline de dados, modelo cognitivo e stack.
- [`ADR.md`](./02-architecture-design/ADR.md) — Registro de decisões de arquitetura (ADR-001…ADR-010).
- [`CHOOSE_TECH_STACK.md`](./02-architecture-design/CHOOSE_TECH_STACK.md) — Escolha da stack tecnológica.
- [`DATA_MODEL.md`](./02-architecture-design/DATA_MODEL.md) — Modelo de dados _(esqueleto)_.
- [`DESIGN.md`](./02-architecture-design/DESIGN.md) — Design system: tema grafite/roxo elétrico, Motion, componentes.
- [`GREEN_COMPUTING.md`](./02-architecture-design/GREEN_COMPUTING.md) — Computação verde _(esqueleto)_.
- [`STYLE_GUIDE.md`](./02-architecture-design/STYLE_GUIDE.md) — Estilo de código Python/TS e convenções de commit.
- [`UML.md`](./02-architecture-design/UML.md) — Diagramas UML _(esqueleto)_.

## 🔄 03 — Processo de Desenvolvimento (`03-development-process/`)

- [`TASKS.md`](./03-development-process/TASKS.md) — Backlog ativo e rastreio de tarefas (espelho dos issues #036–#056).
- [`RULES.md`](./03-development-process/RULES.md) — Regras invioláveis do projeto (governança, segurança, escopo).
- [`DEVELOPMENT.md`](./03-development-process/DEVELOPMENT.md) — Fluxo de desenvolvimento diário e regras de commit.
- [`TESTING.md`](./03-development-process/TESTING.md) — Suíte pytest (700+ testes), como rodar e o que cobre.
- [`SETUP.md`](./03-development-process/SETUP.md) — Instalação passo a passo do ambiente.
- [`TASK_BREAKING_DOWN.md`](./03-development-process/TASK_BREAKING_DOWN.md) — Como decompor funcionalidades em issues.

## 🔌 04 — APIs e Integrações (`04-api-integrations/`)

- [`API.md`](./04-api-integrations/API.md) — Referência completa dos endpoints FastAPI (`app.py`).
- [`CONTENT.md`](./04-api-integrations/CONTENT.md) — Política de conteúdo minerado, seeds curados e qualidade semântica.
- [`INTEGRATIONS.md`](./04-api-integrations/INTEGRATIONS.md) — Neo4j, Qdrant, HF Spaces, Actions, LLM, Jina Reader, LlamaFactory.

## 🛡️ 05 — Segurança e Compliance (`05-security-compliance/`)

- [`COMPLIANCE.md`](./05-security-compliance/COMPLIANCE.md) — Conformidade: LGPD, robots.txt, ética de mineração.
- [`SECURITY_REVIEW.md`](./05-security-compliance/SECURITY_REVIEW.md) — Auditoria anti-leak, zero-trust e checklist de segurança.
- [`IAM_IGA.md`](./05-security-compliance/IAM_IGA.md) — IAM e IGA _(esqueleto)_.
- [`INCIDENT_RESPONSE.md`](./05-security-compliance/INCIDENT_RESPONSE.md) — Resposta a incidentes _(esqueleto)_.
- [`MFA.md`](./05-security-compliance/MFA.md) — Autenticação multifator _(esqueleto)_.
- [`NAC.md`](./05-security-compliance/NAC.md) — Controle de acesso à rede _(esqueleto)_.
- [`RBAC.md`](./05-security-compliance/RBAC.md) — Controle de acesso baseado em papéis _(esqueleto)_.
- [`RLS.md`](./05-security-compliance/RLS.md) — Segurança em nível de linha _(esqueleto)_.
- [`THREAT_MODELING.md`](./05-security-compliance/THREAT_MODELING.md) — Modelagem de ameaças _(esqueleto)_.
- [`VULNERABILITY_DISCLOSURE.md`](./05-security-compliance/VULNERABILITY_DISCLOSURE.md) — Divulgação de vulnerabilidades _(esqueleto)_.
- [`ZTNA.md`](./05-security-compliance/ZTNA.md) — Acesso zero-trust _(esqueleto)_.

## 🚀 06 — DevOps e Deploy (`06-devops-deployment/`)

- [`BACKUP_DR.md`](./06-devops-deployment/BACKUP_DR.md) — Backups semanais do Neo4j e recuperação de desastres.
- [`CI_CD_PIPELINE.md`](./06-devops-deployment/CI_CD_PIPELINE.md) — Pipeline CI/CD _(esqueleto)_.
- [`CODE_REVIEW.md`](./06-devops-deployment/CODE_REVIEW.md) — Checklist de revisão e gate de CI.
- [`FINOPS.md`](./06-devops-deployment/FINOPS.md) — FinOps _(esqueleto)_.
- [`PREVIEW_DEPLOYMENT.md`](./06-devops-deployment/PREVIEW_DEPLOYMENT.md) — Deploys de preview (Vercel/Space).
- [`PRODUCTION_DEPLOY.md`](./06-devops-deployment/PRODUCTION_DEPLOY.md) — Deploy em produção (Space + Vercel + worker).
- [`QA_TESTING.md`](./06-devops-deployment/QA_TESTING.md) — QA funcional antes de produção.

## 📊 07 — Operações e Marketing (`07-operations-marketing/`)

- [`ACCESSIBILITY.md`](./07-operations-marketing/ACCESSIBILITY.md) — Acessibilidade do dashboard e do widget de chat.
- [`AEO.md`](./07-operations-marketing/AEO.md) — Answer Engine Optimization: respostas diretas (snippets/assistentes).
- [`AIO.md`](./07-operations-marketing/AIO.md) — AI Optimization: governança de crawlers de IA, llms.txt e legibilidade para agentes.
- [`ANALYTICS.md`](./07-operations-marketing/ANALYTICS.md) — Métricas de `/api/metrics`: cognitivas, extração, verificação, contabilidade.
- [`ERROR_HANDLING.md`](./07-operations-marketing/ERROR_HANDLING.md) — Degradação graciosa, fallbacks, quarentena e códigos de erro.
- [`GEO.md`](./07-operations-marketing/GEO.md) — Generative Engine Optimization: citação em engines generativos.
- [`MONITORING.md`](./07-operations-marketing/MONITORING.md) — Saúde: `/health`, `/api/metrics`, alertas e troubleshooting.
- [`PERFORMANCE.md`](./07-operations-marketing/PERFORMANCE.md) — Orçamentos de performance, resultados de estresse e limites.
- [`SEO.md`](./07-operations-marketing/SEO.md) — Blindagem anti-scraping, robots.txt e indexação controlada.

## 🧠 08 — Gestão do Conhecimento (`08-knowledge-management/`)

- [`MEMORY.md`](./08-knowledge-management/MEMORY.md) — Modelo de memória (working/episódica/semântica), limites e troubleshooting.
- [`ONBOARDING.md`](./08-knowledge-management/ONBOARDING.md) — Onboarding de novos desenvolvedores/agentes.
- [`HANDOVER_PROMPT.md`](./08-knowledge-management/HANDOVER_PROMPT.md) — Contexto de continuidade para agentes.
- [`ITERATION.md`](./08-knowledge-management/ITERATION.md) — Ciclo de iteração/sprint e retroalimentação.
- [`RESEARCH.md`](./08-knowledge-management/RESEARCH.md) — Pesquisas abertas e evidências (bottleneck semântico #048).
- [`INSPECTION_2_FINDINGS.md`](./08-knowledge-management/INSPECTION_2_FINDINGS.md) — Achados da inspeção de colapso cross-lingual PT vs EN.
- [`AUTONOMOUS_RUN_REPORT.md`](./08-knowledge-management/AUTONOMOUS_RUN_REPORT.md) — Relatório de execução autônoma.
- [`CHANGELOG.md`](./08-knowledge-management/CHANGELOG.md) — Histórico de versões v1.2.0-alpha → v1.14.0.
- [`CODE_OF_CONDUCT.md`](./08-knowledge-management/CODE_OF_CONDUCT.md) — Código de conduta _(esqueleto)_.
- [`CONTRIBUTING.md`](./08-knowledge-management/CONTRIBUTING.md) — Guia de contribuição _(esqueleto)_.
- [`DEPRECATION_POLICY.md`](./08-knowledge-management/DEPRECATION_POLICY.md) — Política de depreciação _(esqueleto)_.

## ⚠️ Convenções

1. **Idioma:** toda a documentação é escrita em pt-BR.
2. **Verdade:** este índice não sobrepõe `SPRINT.md` — em conflito, vence a sprint vigente.
3. **Atualização:** qualquer PR que mude comportamento documentado deve atualizar o doc correspondente (o gate de CI valida `SPRINT.md`; os demais são responsabilidade do autor).
