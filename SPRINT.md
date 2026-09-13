# 🏁 Sprint Governance & Backlog Log — Nexus-Alpha

Este documento estabelece o escopo de execução exclusivo para a **Sprint Atual**.
Nenhum agente, modelo de IA ou desenvolvedor pode realizar alterações em arquivos
ou introduzir dependências que não estejam explicitamente mapeadas neste documento.

---

## 📅 Sprint Atual: `v1.4.0-alpha` — Expansão de Malha e Escalar Quórum

- **Status:** 🟢 Planejada / Em Execução
- **Impacto:** Alto (multiplicação dos fatos validados e verificação contínua de novos domínios)
- **Complexidade:** Baixa (configuração e adição de novos alvos de busca no orquestrador)

### 🎯 Funcionalidade Alvo e Escopo

Ampliar de 6 para 20+ o número de fontes (*seeds*) iniciais de mineração técnica e
acadêmica e ajustar o comportamento do RAG para cruzar dados mais profundos,
elevando a taxa de conversão de conceitos gerais para **Fatos Verificados** sem
corromper as travas de segurança (quórum mantido).

### 📋 Tarefas Mapeadas (Mapeamento de GitHub Issues)

#### [Issue #020] — Injeção de Novas Sementes (Seeds) Técnicas no Minerador
- **Descrição:** adicionar portais independentes e agregadores de documentação
  oficial de IA à lista de alvos iniciais, forçando o cruzamento de dados sobre os
  mesmos tópicos em locais diferentes.
- **Arquivos Afetados:** `scripts/worker_cycle.py` (seeds + `top_k`), executado por
  `.github/workflows/ai-cron.yml`.
- **Critérios de Conclusão:** o pipeline deve processar no mínimo 15 domínios
  únicos de tecnologia por rodada.

#### [Issue #021] — Otimização do Filtro de Quórum Dinâmico
- **Descrição:** tornar o parâmetro `NEXUS_VERIFY_QUORUM` modular (env + arquivo),
  permitindo testes estatísticos sem reescrever o motor de persistência.
- **Arquivos Afetados:** `config/settings.yaml` (`security_policy.triangulation.verify_quorum`),
  `src/database/graph_connector.py` (resolução env-first + validação + log).
- **Critérios de Conclusão:** alterar o quórum via variável de ambiente, com
  validação registrada nos logs do Space.

---

## 🛡️ Restrições de Deploy e Critérios de Aceitação (Definition of Done)

1. **Pass de Testes:** a suíte (97+) e a esteira de validação permanecem verdes.
2. **Taxa de Cruzamento:** o próximo ciclo deve comprovar o aumento nos
   `verified_facts` mantendo o quórum estável.

---

## 📜 Histórico de Sprints Concluídas

- `v1.2.0-alpha` — Correção de `/health` e TLS `neo4j+s://` do AuraDB.
- `v1.3.0-alpha` — Integração de tooling (MCP, subagents, Agent-Reach, browser-use, Strix).
- `v1.4.0-alpha` — Atendimento conversacional (`ChatService` + `/api/chat` + ChatWidget).
- `v1.5.0-alpha` — Hardening & eficiência (APOC-free, embeddings locais, singletons, `/api/metrics`).
- `v1.6.0-alpha` — Simulação de enxame (`/api/simulate`).
- `v1.7.0-alpha` — Qualidade de extração (spaCy pt) + memória vetorial.
- `v1.8.0-alpha` — Ruído, limpeza e corroboração real (`:Fato` + `verified_facts`).
- `v1.9.0-alpha` — Produção visual (scaffold Next.js, chat real, ForceGraph, CORS Vercel).
